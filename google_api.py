import os
from pathlib import Path
from typing import Optional
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive",
]

TOKEN_PATH = Path(__file__).parent / "token.json"

TEMPLATE_ID = "1GB4ONf8eN4mX4iYlBCXmauX9ogHtNnHQg30ztkymfHw"
# Slides are inserted immediately after this slide ("AI Play Outputs")
INSERT_AFTER_SLIDE_ID = "g3d9d902cf0d_0_1590"


def _creds() -> Credentials:
    if not TOKEN_PATH.exists():
        raise FileNotFoundError(
            "token.json not found. Run `python3 auth.py` once to authorise your Google account."
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
    return creds


def _slides():
    return build("slides", "v1", credentials=_creds())


# ---------------------------------------------------------------------------
# Step 1 — duplicate template slides in-deck and position after "AI Play Outputs"
# ---------------------------------------------------------------------------

def create_play_slides(play_name: str):
    """
    Finds slides containing {{PLAY_NAME}}, duplicates them within the same
    presentation, moves the copies right after INSERT_AFTER_SLIDE_ID.
    Returns (new_slide_ids, url_to_first_new_slide).
    """
    slides_svc = _slides()
    pres = slides_svc.presentations().get(presentationId=TEMPLATE_ID).execute()

    # Identify template slides by the presence of {{PLAY_NAME}}
    template_slide_ids = []
    for slide in pres.get("slides", []):
        for element in slide.get("pageElements", []):
            shape = element.get("shape", {})
            full_text = "".join(
                te.get("textRun", {}).get("content", "")
                for te in shape.get("text", {}).get("textElements", [])
            )
            if "{{PLAY_NAME}}" in full_text:
                template_slide_ids.append(slide["objectId"])
                break

    if not template_slide_ids:
        raise ValueError(
            "No template slides found — the presentation must contain a text box "
            "with {{PLAY_NAME}}."
        )

    # Duplicate each template slide (copies appear right after their source)
    dup_response = slides_svc.presentations().batchUpdate(
        presentationId=TEMPLATE_ID,
        body={"requests": [
            {"duplicateObject": {"objectId": sid}} for sid in template_slide_ids
        ]},
    ).execute()

    new_slide_ids = [
        reply["duplicateObject"]["objectId"]
        for reply in dup_response.get("replies", [])
        if "duplicateObject" in reply
    ]

    # Re-fetch to get the updated slide order, then find insert position
    pres2 = slides_svc.presentations().get(presentationId=TEMPLATE_ID).execute()
    updated_slides = pres2.get("slides", [])
    insert_after_idx = next(
        (i for i, s in enumerate(updated_slides) if s["objectId"] == INSERT_AFTER_SLIDE_ID),
        len(updated_slides) - 1,
    )

    # Move new slides to right after "AI Play Outputs"
    slides_svc.presentations().batchUpdate(
        presentationId=TEMPLATE_ID,
        body={"requests": [{
            "updateSlidesPosition": {
                "slideObjectIds": new_slide_ids,
                "insertionIndex": insert_after_idx + 1,
            }
        }]},
    ).execute()

    url = (
        f"https://docs.google.com/presentation/d/{TEMPLATE_ID}"
        f"/edit#slide=id.{new_slide_ids[0]}"
    )
    return new_slide_ids, url


# ---------------------------------------------------------------------------
# Step 2 — replace placeholders, apply links and bullets (scoped to new slides)
# ---------------------------------------------------------------------------

def _shape_full_text(shape: dict) -> str:
    return "".join(
        te.get("textRun", {}).get("content", "")
        for te in shape.get("text", {}).get("textElements", [])
    )


def replace_placeholders(
    new_slide_ids: list,
    replacements: dict,
    link_map: Optional[dict] = None,
    bullet_placeholders: Optional[set] = None,
    step_links: Optional[dict] = None,
):
    """
    All operations are scoped to new_slide_ids so the original template slides
    are never touched.

    replacements:        {"{{PLAY_NAME}}": "...", ...}
    link_map:            {"{{TOP_LINK_1}}": "https://...", ...}  whole-shape links
    bullet_placeholders: {"{{DISCOVERY_QUESTIONS}}", ...}
    step_links:          {"{{TARGET_ACCOUNTS}}": [{"text": "...", "url": "..."}, ...], ...}
    """
    slides_svc = _slides()
    link_map = link_map or {}
    bullet_placeholders = bullet_placeholders or set()
    step_links = step_links or {}
    new_slide_id_set = set(new_slide_ids)

    def _get_target_slides(pres):
        return [s for s in pres.get("slides", []) if s["objectId"] in new_slide_id_set]

    # --- pass 1: text replacement, scoped to new slides only ---
    slides_svc.presentations().batchUpdate(
        presentationId=TEMPLATE_ID,
        body={"requests": [
            {
                "replaceAllText": {
                    "containsText": {"text": placeholder, "matchCase": True},
                    "replaceText": value,
                    "pageObjectIds": new_slide_ids,
                }
            }
            for placeholder, value in replacements.items()
        ]},
    ).execute()

    # Re-read the new slides for subsequent passes
    pres = slides_svc.presentations().get(presentationId=TEMPLATE_ID).execute()
    target_slides = _get_target_slides(pres)

    # --- pass 2: whole-shape hyperlinks (top resource links) and bullet detection ---
    text_to_url = {}
    for placeholder, url in link_map.items():
        display_text = replacements.get(placeholder, "").strip()
        if display_text and url:
            text_to_url[display_text] = url

    link_requests = []
    bullet_object_ids = []
    value_to_placeholder = {v.strip(): k for k, v in replacements.items() if v}

    for slide in target_slides:
        for element in slide.get("pageElements", []):
            shape = element.get("shape")
            if not shape:
                continue
            full_text = _shape_full_text(shape).strip()
            obj_id = element["objectId"]

            url = text_to_url.get(full_text)
            if url:
                link_requests.append({
                    "updateTextStyle": {
                        "objectId": obj_id,
                        "textRange": {"type": "ALL"},
                        "style": {"link": {"url": url}},
                        "fields": "link",
                    }
                })

            placeholder_key = value_to_placeholder.get(full_text)
            if placeholder_key in bullet_placeholders:
                bullet_object_ids.append(obj_id)

    if link_requests:
        slides_svc.presentations().batchUpdate(
            presentationId=TEMPLATE_ID, body={"requests": link_requests}
        ).execute()

    if bullet_object_ids:
        slides_svc.presentations().batchUpdate(
            presentationId=TEMPLATE_ID,
            body={"requests": [
                {
                    "createParagraphBullets": {
                        "objectId": obj_id,
                        "textRange": {"type": "ALL"},
                        "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
                    }
                }
                for obj_id in bullet_object_ids
            ]},
        ).execute()

    # --- pass 3: per-title hyperlinks inside table cells for 10-step resources ---
    # The step placeholders live in an 11x2 table (column 1 = resource links).
    # We find the table on each new slide, locate the cell whose text contains
    # each resource title, then use the textRun's API-provided startIndex to
    # apply a FIXED_RANGE link — no manual offset math needed.
    if step_links:
        # Build lookup: display text of step → rows with {text, url}
        display_to_rows = {}
        for placeholder, rows in step_links.items():
            display_text = replacements.get(placeholder, "")
            if display_text:
                display_to_rows[display_text.strip()] = rows

        table_link_requests = []

        for slide in target_slides:
            for element in slide.get("pageElements", []):
                if "table" not in element:
                    continue
                table_obj_id = element["objectId"]
                for row in element["table"].get("tableRows", []):
                    for cell in row.get("tableCells", []):
                        text_elements = cell.get("text", {}).get("textElements", [])
                        cell_text = "".join(
                            te.get("textRun", {}).get("content", "")
                            for te in text_elements
                        )

                        # Find which step's titles live in this cell
                        matched_rows = None
                        for display_text, step_rows in display_to_rows.items():
                            # Each resource title is in the cell after replacement
                            for step_row in step_rows:
                                if step_row["text"].strip() in cell_text:
                                    matched_rows = step_rows
                                    break
                            if matched_rows:
                                break

                        if not matched_rows:
                            continue

                        for step_row in matched_rows:
                            title = step_row["text"].strip()
                            url = step_row.get("url", "").strip()
                            if not title or not url:
                                continue
                            # Find the exact textRun that contains this title
                            for te in text_elements:
                                content = te.get("textRun", {}).get("content", "")
                                if title in content:
                                    api_start = te.get("startIndex", 0)
                                    offset = content.find(title)
                                    table_link_requests.append({
                                        "updateTextStyle": {
                                            "objectId": table_obj_id,
                                            "cellLocation": cell.get("location"),
                                            "textRange": {
                                                "type": "FIXED_RANGE",
                                                "startIndex": api_start + offset,
                                                "endIndex": api_start + offset + len(title),
                                            },
                                            "style": {"link": {"url": url}},
                                            "fields": "link",
                                        }
                                    })
                                    break

        if table_link_requests:
            slides_svc.presentations().batchUpdate(
                presentationId=TEMPLATE_ID, body={"requests": table_link_requests}
            ).execute()
