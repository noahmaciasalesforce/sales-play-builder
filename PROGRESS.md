# Sales Play Builder — Project Progress

## What We Built

A local Streamlit web app that lets you fill out a form and automatically:
1. Duplicates template slides within the master Google Slides deck
2. Replaces all `{{PLACEHOLDER}}` text with submitted values
3. Applies hyperlinks to Top Resource Links and 10-step resource cells
4. Applies bullet formatting to designated messaging fields
5. Positions the new slides after the "AI Play Outputs" slide in the deck
6. Sends a Slack DM with a link to the new slides

## Files

| File | Purpose |
|------|---------|
| `app.py` | Streamlit UI — form, session state, submission logic |
| `google_api.py` | All Google Slides API logic (duplicate, replace, link, bullet) |
| `slack_api.py` | Slack DM via bot token |
| `auth.py` | One-time OAuth 2.0 flow — run once to generate `token.json` |
| `debug_links.py` | Diagnostic tool — inspect slide shapes/tables/text elements |
| `requirements.txt` | Python dependencies |
| `credentials.json` | OAuth client secrets (gitignored, not committed) |
| `token.json` | Saved OAuth token, auto-refreshes (gitignored, not committed) |

## Google Slides Deck Structure (discovered via API)

**Presentation ID:** `1GB4ONf8eN4mX4iYlBCXmauX9ogHtNnHQg30ztkymfHw`

| Slide Object ID | Role |
|----------------|------|
| `g3d9d902cf0d_0_1590` | Template slide 1 — "Key Resources" / promo / top links / 10-step table |
| `g3d9d902cf0d_0_1612` | Template slide 2 — Messaging (elevator pitch, discovery, etc.) |
| `g3d9d902cf0d_0_5298` | "AI Play Outputs" divider slide — new plays are inserted after this |

**Key discovery:** The 10-step resources live inside a **table element** (`g3d9d902cf0d_0_1597`), an 11×2 grid — not regular text shapes. This is why hyperlink attempts failed until pass 3 was rewritten to scan table cells.

## Auth

- OAuth 2.0 with personal Google credentials (no service account, no external sharing needed)
- `python3 auth.py` opens browser, grants access, writes `token.json`
- Token auto-refreshes on expiry
- Run `streamlit run app.py` after auth

## What's Working

- ✅ Form UI — all fields, dynamic add/remove rows for 10-step resources
- ✅ Slide duplication — template slides duplicated in-deck, scoped so original template is never modified
- ✅ Slide positioning — new slides inserted after "AI Play Outputs"
- ✅ Placeholder replacement — all `{{PLACEHOLDERS}}` replaced, scoped to new slide IDs only
- ✅ Original template text formatting preserved (font size pass removed)
- ✅ Bullet formatting on 6 messaging fields (everything except Elevator Pitch)
- ✅ Top Resource Links — whole-shape hyperlinks working
- ✅ Slack DM notification
- ✅ Google OAuth (personal credentials, no service account)

## What's Not Working / Open Issues

- ❌ **10-step resource hyperlinks** — the links are not appearing in the table cells despite the latest rewrite (pass 3 in `google_api.py`). The table cell `cellLocation` + `FIXED_RANGE` approach is correct per API docs, but links are still not showing. Needs a live test of the latest code to confirm if the rewrite fixed it.

## Key Technical Notes

- `replaceAllText` is scoped using `pageObjectIds` to prevent touching the original template slides
- The 10-step table object ID on new slides follows the pattern `SLIDES_API{n}_6` (e.g. `SLIDES_API800490886_6`)
- Table cells use `cellLocation: {rowIndex, columnIndex}` on `updateTextStyle` — different from shape text styling
- The `startIndex` in textRun elements is the character offset within the whole text body of the cell, not within the run itself — using `te.get("startIndex", 0) + content.find(title)` is correct
- Python 3.9 is in use — use `Optional[x]` not `x | None` syntax

## To Run

```bash
cd /Users/noah.macia/claude
python3 -m streamlit run app.py
```
