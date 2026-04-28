"""
Run: python3 debug_links.py [slide_id]

Without a slide_id: scans ALL slides and prints every shape including empty ones.
With a slide_id: prints full detail for that slide only.
"""
import sys
from google_api import _slides, TEMPLATE_ID

def scan_slide(slide, verbose=True):
    sid = slide["objectId"]
    print(f"\n{'='*60}")
    print(f"SLIDE: {sid}")
    for element in slide.get("pageElements", []):
        shape = element.get("shape")
        if not shape:
            continue
        text_elements = shape.get("text", {}).get("textElements", [])
        full = "".join(te.get("textRun", {}).get("content", "") for te in text_elements)
        obj_id = element["objectId"]
        has_placeholder = "{{" in full

        if verbose:
            marker = " <<< PLACEHOLDER" if has_placeholder else ""
            print(f"\n  shape {obj_id}: {repr(full[:120])}{marker}")
            for te in text_elements:
                start = te.get("startIndex", 0)
                end = te.get("endIndex", "?")
                if "textRun" in te:
                    print(f"    [{start}:{end}] textRun: {repr(te['textRun']['content'])}")
                elif "paragraphMarker" in te:
                    print(f"    [{start}:{end}] paragraphMarker")
        else:
            marker = " *** PLACEHOLDER ***" if has_placeholder else ""
            empty_note = " [EMPTY]" if not full.strip() else ""
            print(f"  {obj_id}: {repr(full[:80])}{marker}{empty_note}")

def main():
    svc = _slides()
    pres = svc.presentations().get(presentationId=TEMPLATE_ID).execute()

    if len(sys.argv) >= 2:
        slide_id = sys.argv[1]
        slide = next((s for s in pres["slides"] if s["objectId"] == slide_id), None)
        if not slide:
            print(f"Slide '{slide_id}' not found. IDs: {[s['objectId'] for s in pres['slides']]}")
            sys.exit(1)
        scan_slide(slide, verbose=True)
    else:
        print("=== ALL SLIDES (including empty shapes) ===")
        for slide in pres["slides"]:
            scan_slide(slide, verbose=False)

if __name__ == "__main__":
    main()
