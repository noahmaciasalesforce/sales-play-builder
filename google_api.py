from pathlib import Path
from typing import Optional
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

TOKEN_PATH = Path(__file__).parent / "token.json"
TEMPLATE_ID = "1GB4ONf8eN4mX4iYlBCXmauX9ogHtNnHQg30ztkymfHw"


def _creds():
    # On Streamlit Cloud: use service account stored in st.secrets
    try:
        import streamlit as st
        if "gcp_service_account" in st.secrets:
            return service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=SCOPES,
            )
    except Exception:
        pass

    # Local dev: fall back to OAuth token.json
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


def _drive():
    return build("drive", "v3", credentials=_creds())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _shape_full_text(shape: dict) -> str:
    return "".join(
        te.get("textRun", {}).get("content", "")
        for te in shape.get("text", {}).get("textElements", [])
    )


def _element_contains(el: dict, needle: str) -> bool:
    if "shape" in el:
        return needle in _shape_full_text(el["shape"])
    if "table" in el:
        for row in el["table"].get("tableRows", []):
            for cell in row.get("tableCells", []):
                text = "".join(
                    te.get("textRun", {}).get("content", "")
                    for te in cell.get("text", {}).get("textElements", [])
                )
                if needle in text:
                    return True
    if "elementGroup" in el:
        return any(_element_contains(child, needle) for child in el["elementGroup"].get("children", []))
    return False


def _utf16_len(s: str) -> int:
    """Return UTF-16 code unit count — the Slides API uses these for text offsets."""
    return len(s.encode("utf-16-le")) // 2


# ---------------------------------------------------------------------------
# Step 1 — copy template to a brand-new file, strip non-template slides
# ---------------------------------------------------------------------------

def create_play_slides(play_name: str):
    """
    Copies the template to a new file owned by the authenticated Google account,
    deletes all slides that don't contain {{PLAY_NAME}}, and returns (new_id, url).
    """
    drive = _drive()
    slides_svc = _slides()

    copy = drive.files().copy(
        fileId=TEMPLATE_ID,
        body={"name": f"{play_name} - Sales Play"},
        supportsAllDrives=True,
    ).execute()
    new_id = copy["id"]

    pres = slides_svc.presentations().get(presentationId=new_id).execute()
    slides = pres.get("slides", [])

    keep_ids = {
        s["objectId"]
        for s in slides
        if any(_element_contains(el, "{{PLAY_NAME}}") for el in s.get("pageElements", []))
    }
    delete_ids = [s["objectId"] for s in slides if s["objectId"] not in keep_ids]

    if delete_ids:
        slides_svc.presentations().batchUpdate(
            presentationId=new_id,
            body={"requests": [{"deleteObject": {"objectId": sid}} for sid in delete_ids]},
        ).execute()

    url = f"https://docs.google.com/presentation/d/{new_id}/edit"
    return new_id, url


DESTINATION_FOLDER_ID = "17xFdO-SybxvP7CgpqYHXdTxN0H2GGqbS"


def share_file_public(file_id: str):
    """Make the file viewable by anyone with the link."""
    drive = _drive()
    drive.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"},
        supportsAllDrives=True,
    ).execute()


def move_to_salesforce_drive(file_id: str):
    """Move the file into the Salesforce Shared Drive folder and remove it from personal Drive."""
    drive = _drive()
    file_meta = drive.files().get(
        fileId=file_id,
        fields="parents",
        supportsAllDrives=True,
    ).execute()
    current_parents = ",".join(file_meta.get("parents", []))
    drive.files().update(
        fileId=file_id,
        addParents=DESTINATION_FOLDER_ID,
        removeParents=current_parents,
        supportsAllDrives=True,
        fields="id, parents",
    ).execute()


# ---------------------------------------------------------------------------
# Step 2 — replace placeholders, apply links and bullets
# ---------------------------------------------------------------------------

def replace_placeholders(
    pres_id: str,
    replacements: dict,
    link_map: Optional[dict] = None,
    bullet_placeholders: Optional[set] = None,
    step_links: Optional[dict] = None,
):
    """
    pres_id:             the new (copied) presentation to operate on
    replacements:        {"{{PLAY_NAME}}": "...", ...}
    link_map:            {"{{TOP_LINK_1}}": "https://...", ...}  whole-shape links
    bullet_placeholders: {"{{DISCOVERY_QUESTIONS}}", ...}
    step_links:          {"{{TARGET_ACCOUNTS}}": [{"text": "...", "url": "..."}, ...], ...}
    """
    slides_svc = _slides()
    link_map = link_map or {}
    bullet_placeholders = bullet_placeholders or set()
    step_links = step_links or {}

    # --- pre-scan: inspect the presentation BEFORE replacement so we can map
    # placeholders → exact objectIds. This prevents cross-matching issues where
    # a post-replacement text value accidentally matches a different shape.
    pres_before = slides_svc.presentations().get(presentationId=pres_id).execute()

    # objectId -> url  (shapes containing a top-link placeholder)
    top_link_shape_map = {}
    # objectIds of shapes that should receive bullet formatting
    bullet_shape_ids = []
    # "{{PLACEHOLDER}}" -> {table_obj_id, row, col}  for step link cells
    placeholder_cell_map = {}
    # (table_obj_id, row, col) tuples for cells that CONTAIN a replaceable placeholder.
    # All other table cells will have bullets deleted in the cleanup pass.
    placeholder_table_cells = set()

    for slide in pres_before.get("slides", []):
        for el in slide.get("pageElements", []):
            shape = el.get("shape")
            if shape:
                text = _shape_full_text(shape)
                obj_id = el["objectId"]
                for ph, url in link_map.items():
                    if ph in text:
                        top_link_shape_map[obj_id] = url
                for ph in bullet_placeholders:
                    if ph in text:
                        bullet_shape_ids.append(obj_id)
            elif "table" in el:
                table_obj_id = el["objectId"]
                for ri, trow in enumerate(el["table"].get("tableRows", [])):
                    for ci, cell in enumerate(trow.get("tableCells", [])):
                        cell_text = "".join(
                            te.get("textRun", {}).get("content", "")
                            for te in cell.get("text", {}).get("textElements", [])
                        )
                        for placeholder in replacements:
                            if placeholder in cell_text:
                                placeholder_table_cells.add((table_obj_id, ri, ci))
                        for placeholder in step_links:
                            if placeholder in cell_text:
                                placeholder_cell_map[placeholder] = {
                                    "table_obj_id": table_obj_id,
                                    "row": ri,
                                    "col": ci,
                                }

    # --- pass 1: text replacement across entire new presentation ---
    slides_svc.presentations().batchUpdate(
        presentationId=pres_id,
        body={"requests": [
            {
                "replaceAllText": {
                    "containsText": {"text": placeholder, "matchCase": True},
                    "replaceText": value,
                }
            }
            for placeholder, value in replacements.items()
        ]},
    ).execute()

    # Re-read after replacement for subsequent passes
    pres = slides_svc.presentations().get(presentationId=pres_id).execute()

    # --- pass 2: whole-shape hyperlinks on top resource link shapes ---
    link_requests = []
    for obj_id, url in top_link_shape_map.items():
        link_requests.append({
            "updateTextStyle": {
                "objectId": obj_id,
                "textRange": {"type": "ALL"},
                "style": {"link": {"url": url}},
                "fields": "link",
            }
        })
    if link_requests:
        slides_svc.presentations().batchUpdate(
            presentationId=pres_id, body={"requests": link_requests}
        ).execute()

    # --- pass 2b: bullet formatting on messaging shapes ---
    if bullet_shape_ids:
        slides_svc.presentations().batchUpdate(
            presentationId=pres_id,
            body={"requests": [
                {
                    "createParagraphBullets": {
                        "objectId": obj_id,
                        "textRange": {"type": "ALL"},
                        "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
                    }
                }
                for obj_id in bullet_shape_ids
            ]},
        ).execute()

    # --- pass 3: per-title hyperlinks inside table cells ---
    # For each step placeholder we pre-recorded the exact (table, row, col).
    # After replacement, we read that cell's text and compute UTF-16 offsets
    # for each resource title. We search starting at rep_start — the position
    # where the replacement text begins — so we never accidentally hyperlink
    # text in the step label portion of the same cell.
    if step_links and placeholder_cell_map:
        table_elements = {
            el["objectId"]: el
            for slide in pres.get("slides", [])
            for el in slide.get("pageElements", [])
            if "table" in el
        }

        table_link_requests = []
        for placeholder, rows in step_links.items():
            cell_info = placeholder_cell_map.get(placeholder)
            if not cell_info:
                continue

            table_el = table_elements.get(cell_info["table_obj_id"])
            if not table_el:
                continue

            ri, ci = cell_info["row"], cell_info["col"]
            cell = table_el["table"]["tableRows"][ri]["tableCells"][ci]
            cell_text = "".join(
                te.get("textRun", {}).get("content", "")
                for te in cell.get("text", {}).get("textElements", [])
            )

            # Find where the replacement text starts so we don't match within
            # any step-label text that lives earlier in the same cell.
            replacement_text = replacements.get(placeholder, "")
            rep_start = cell_text.find(replacement_text) if replacement_text else 0
            if rep_start == -1:
                rep_start = 0

            for row in rows:
                title = row["text"].strip()
                url = row.get("url", "").strip()
                if not title or not url:
                    continue

                py_idx = cell_text.find(title, rep_start)
                if py_idx == -1:
                    continue

                start = _utf16_len(cell_text[:py_idx])
                end = start + _utf16_len(title)

                table_link_requests.append({
                    "updateTextStyle": {
                        "objectId": cell_info["table_obj_id"],
                        "cellLocation": {"rowIndex": ri, "columnIndex": ci},
                        "textRange": {
                            "type": "FIXED_RANGE",
                            "startIndex": start,
                            "endIndex": end,
                        },
                        "style": {"link": {"url": url}},
                        "fields": "link",
                    }
                })

        if table_link_requests:
            slides_svc.presentations().batchUpdate(
                presentationId=pres_id, body={"requests": table_link_requests}
            ).execute()

    # --- pass 4: bullet cleanup ---
    # Remove bullets from table cells that are not resource-content cells (e.g.
    # step-label column, header row) and from top-resource-link shapes. This
    # ensures the output matches the template formatting regardless of whether
    # the template copy inherited any accidental bullet styling.
    cleanup_requests = []

    for slide in pres.get("slides", []):
        for el in slide.get("pageElements", []):
            if "table" not in el:
                continue
            table_obj_id = el["objectId"]
            for ri, trow in enumerate(el["table"].get("tableRows", [])):
                for ci in range(len(trow.get("tableCells", []))):
                    if (table_obj_id, ri, ci) not in placeholder_table_cells:
                        cleanup_requests.append({
                            "deleteParagraphBullets": {
                                "objectId": table_obj_id,
                                "cellLocation": {"rowIndex": ri, "columnIndex": ci},
                                "textRange": {"type": "ALL"},
                            }
                        })

    for obj_id in top_link_shape_map:
        cleanup_requests.append({
            "deleteParagraphBullets": {
                "objectId": obj_id,
                "textRange": {"type": "ALL"},
            }
        })

    if cleanup_requests:
        slides_svc.presentations().batchUpdate(
            presentationId=pres_id, body={"requests": cleanup_requests}
        ).execute()
