import os
import uuid
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from google_api import (
    create_play_slides,
    replace_placeholders,
    share_file_public,
    move_to_salesforce_drive,
)

st.set_page_config(page_title="New Sales Play", layout="wide")
st.title("Create a New Sales Play")
st.markdown(
    "Welcome to the sales play builder for Agentforce Sales. Simply input the right details, "
    "and this app will build you a fresh new sales play in our current FY27 format. "
    "For questions or concerns, please reach out to Noah Macia in Slack."
)

STEP_KEYS = [
    ("TARGET_ACCOUNTS", "1. Target Accounts"),
    ("BOOK_A_MEETING", "2. Book a Meeting"),
    ("PREPARE_FOR_CALL", "3. Prepare for Call"),
    ("DELIVER_PITCH", "4. Deliver Pitch"),
    ("CUSTOMER_PROOF", "5. Customer Proof"),
    ("RUN_DEMO", "6. Run Demo"),
    ("ACCELERATE_DEAL", "7. Upcoming Events"),
    ("BUSINESS_CASE", "8. Business Case"),
    ("PRESENT_PRICING", "9. Present Pricing"),
    ("VALID_PROMOS", "10. Valid Promos"),
]

for key, _ in STEP_KEYS:
    if f"step_rows_{key}" not in st.session_state:
        st.session_state[f"step_rows_{key}"] = [
            {"id": str(uuid.uuid4()), "text": "", "url": ""}
        ]

# ---------------------------------------------------------------------------
# Play Details
# ---------------------------------------------------------------------------
st.subheader("Play Details")
col1, col2 = st.columns(2)
with col1:
    play_name = st.text_input("Play Name *", key="play_name", placeholder="e.g. Q2 Enterprise Upsell")
    play_type = st.selectbox("Type of Play *", ["New Logo", "Upgrade", "Add-On"], key="play_type")
    avg_deal = st.text_input("Average Deal Amount *", key="avg_deal", placeholder="e.g. $50,000")
    days_to_close = st.text_input("Average Days to Close *", key="days_to_close", placeholder="e.g. 45")
with col2:
    promo_headline = st.text_input(
        "Promo Headline (if valid promo exists)", key="promo_headline", placeholder="e.g. 30%"
    )
    promo_description = st.text_input(
        "Promo Description (if valid promo exists)", key="promo_description",
        placeholder="e.g. To Upgrade From Enterprise To Unlimited Edition",
    )

# ---------------------------------------------------------------------------
# Messaging
# ---------------------------------------------------------------------------
st.subheader("Messaging")
st.info(
    "Keep each field as concise as possible — the play template has fixed sizing "
    "constraints. Shorter, punchy copy fits best.",
    icon="✏️",
)

elevator_pitch = st.text_area("Elevator Pitch *", key="elevator_pitch", height=100, max_chars=600)
st.caption("600 character limit (including spaces and punctuation).")

BULLET_DISCLAIMER = (
    "We recommend no more than 4 single-line bullets for this field. "
    "Each new line you enter will become a separate bullet point on the slide."
)

discovery_questions = st.text_area("Discovery Questions *", key="discovery_questions", height=100)
st.caption(BULLET_DISCLAIMER)

signs_to_pitch = st.text_area("Signs You Should Pitch *", key="signs_to_pitch", height=100)
st.caption("Each new line will become a separate bullet point on the slide.")

problems_solutions = st.text_area("Problems and Solutions *", key="problems_solutions", height=100)
st.caption(BULLET_DISCLAIMER)

key_competitors = st.text_area("Agentforce Sales vs. Key Competitors *", key="key_competitors", height=100)
st.caption(BULLET_DISCLAIMER)

target_buyers = st.text_area("Target Buyers *", key="target_buyers", height=100)
st.caption("Each new line will become a separate bullet point on the slide.")

objection_handling = st.text_area("Objection Handling *", key="objection_handling", height=100)
st.caption(BULLET_DISCLAIMER)

# ---------------------------------------------------------------------------
# 10-Step Resources
# ---------------------------------------------------------------------------
st.subheader("10-Step Resources")
st.caption("Add one or more resources per step. Each title will be a clickable link on the slide if you provide a URL.")

for step_key, step_label in STEP_KEYS:
    st.markdown(f"**{step_label}**")
    rows = st.session_state[f"step_rows_{step_key}"]
    to_remove = None

    h1, h2, h3 = st.columns([4, 5, 1])
    h1.caption("Resource title")
    h2.caption("URL (optional)")

    for row in rows:
        c1, c2, c3 = st.columns([4, 5, 1])
        with c1:
            row["text"] = st.text_input(
                "title", value=row["text"],
                key=f"{step_key}_{row['id']}_text",
                placeholder="e.g. Q2 Target Account List",
                label_visibility="collapsed",
            )
        with c2:
            row["url"] = st.text_input(
                "url", value=row["url"],
                key=f"{step_key}_{row['id']}_url",
                placeholder="https://...",
                label_visibility="collapsed",
            )
        with c3:
            st.write("")
            if len(rows) > 1 and st.button("✕", key=f"remove_{step_key}_{row['id']}", help="Remove this resource"):
                to_remove = row["id"]

    if to_remove:
        st.session_state[f"step_rows_{step_key}"] = [
            r for r in st.session_state[f"step_rows_{step_key}"] if r["id"] != to_remove
        ]
        st.rerun()

    if st.button(f"＋ Add resource", key=f"add_{step_key}"):
        st.session_state[f"step_rows_{step_key}"].append(
            {"id": str(uuid.uuid4()), "text": "", "url": ""}
        )
        st.rerun()

    st.divider()

# ---------------------------------------------------------------------------
# Top Resource Links
# ---------------------------------------------------------------------------
st.subheader("Top Resource Links")
top_col1, top_col2, top_col3 = st.columns(3)
with top_col1:
    top_link_1_text = st.text_input("Top Resource Link 1 *", key="top_link_1_text")
    top_link_1_url = st.text_input("↳ URL", key="top_link_1_url", placeholder="https://...")
with top_col2:
    top_link_2_text = st.text_input("Top Resource Link 2 *", key="top_link_2_text")
    top_link_2_url = st.text_input("↳ URL", key="top_link_2_url", placeholder="https://...")
with top_col3:
    top_link_3_text = st.text_input("Help Sell Channel *", key="top_link_3_text")
    top_link_3_url = st.text_input("↳ URL", key="top_link_3_url", placeholder="https://...")

st.divider()
submitted = st.button("Create Sales Play", type="primary")

# ---------------------------------------------------------------------------
# Submission handler
# ---------------------------------------------------------------------------
if submitted:
    required = {
        "Play Name": play_name,
        "Average Deal Amount": avg_deal,
        "Average Days to Close": days_to_close,
        "Elevator Pitch": elevator_pitch,
        "Discovery Questions": discovery_questions,
        "Signs You Should Pitch": signs_to_pitch,
        "Problems and Solutions": problems_solutions,
        "Agentforce Sales vs. Key Competitors": key_competitors,
        "Target Buyers": target_buyers,
        "Objection Handling": objection_handling,
        "Top Resource Link 1": top_link_1_text,
        "Top Resource Link 1 URL": top_link_1_url,
        "Top Resource Link 2": top_link_2_text,
        "Top Resource Link 2 URL": top_link_2_url,
        "Help Sell Channel": top_link_3_text,
        "Help Sell Channel URL": top_link_3_url,
    }
    missing = [k for k, v in required.items() if not v.strip()]
    if missing:
        st.error(f"Please fill in: {', '.join(missing)}")
        st.stop()

    # Collect step rows (skip blank-title entries)
    step_data = {
        key: [r for r in st.session_state[f"step_rows_{key}"] if r["text"].strip()]
        for key, _ in STEP_KEYS
    }

    replacements = {
        "{{PLAY_NAME}}": play_name,
        "{{PLAY_TYPE}}": play_type,
        "{{AVG_DEAL_SIZE}}": avg_deal,
        "{{DAYS_TO_CLOSE}}": days_to_close,
        "{{PROMO_HEADLINE}}": promo_headline,
        "{{PROMO_DESCRIPTION}}": promo_description,
        "{{TARGET_ACCOUNTS}}": ", ".join(r["text"] for r in step_data["TARGET_ACCOUNTS"]),
        "{{BOOK_A_MEETING}}": ", ".join(r["text"] for r in step_data["BOOK_A_MEETING"]),
        "{{PREPARE_FOR_CALL}}": ", ".join(r["text"] for r in step_data["PREPARE_FOR_CALL"]),
        "{{DELIVER_PITCH}}": ", ".join(r["text"] for r in step_data["DELIVER_PITCH"]),
        "{{CUSTOMER_PROOF}}": ", ".join(r["text"] for r in step_data["CUSTOMER_PROOF"]),
        "{{RUN_DEMO}}": ", ".join(r["text"] for r in step_data["RUN_DEMO"]),
        "{{ACCELERATE_DEAL}}": ", ".join(r["text"] for r in step_data["ACCELERATE_DEAL"]),
        "{{BUSINESS_CASE}}": ", ".join(r["text"] for r in step_data["BUSINESS_CASE"]),
        "{{PRESENT_PRICING}}": ", ".join(r["text"] for r in step_data["PRESENT_PRICING"]),
        "{{VALID_PROMOS}}": ", ".join(r["text"] for r in step_data["VALID_PROMOS"]),
        "{{TOP_LINK_1}}": top_link_1_text,
        "{{TOP_LINK_2}}": top_link_2_text,
        "{{TOP_LINK_3}}": top_link_3_text,
        "{{ELEVATOR_PITCH}}": elevator_pitch,
        "{{DISCOVERY_QUESTIONS}}": discovery_questions,
        "{{SIGNS_TO_PITCH}}": signs_to_pitch,
        "{{PROBLEMS_SOLUTIONS}}": problems_solutions,
        "{{KEY_COMPETITORS}}": key_competitors,
        "{{TARGET_BUYERS}}": target_buyers,
        "{{OBJECTION_HANDLING}}": objection_handling,
    }

    step_links = {
        f"{{{{{key}}}}}": step_data[key]
        for key, _ in STEP_KEYS
        if any(r.get("url", "").strip() for r in step_data[key])
    }

    link_map = {
        "{{TOP_LINK_1}}": top_link_1_url,
        "{{TOP_LINK_2}}": top_link_2_url,
        "{{TOP_LINK_3}}": top_link_3_url,
    }

    bullet_placeholders = {
        "{{DISCOVERY_QUESTIONS}}",
        "{{SIGNS_TO_PITCH}}",
        "{{PROBLEMS_SOLUTIONS}}",
        "{{KEY_COMPETITORS}}",
        "{{TARGET_BUYERS}}",
        "{{OBJECTION_HANDLING}}",
    }

    with st.status("Creating sales play...", expanded=True) as status:
        try:
            st.write("Duplicating template slides...")
            new_id, new_url = create_play_slides(play_name)
            st.write("New presentation created.")

            st.write("Replacing placeholders and applying links...")
            replace_placeholders(new_id, replacements, link_map, bullet_placeholders, step_links)
            st.write("Content filled in.")

            status.update(label="Sales play created!", state="complete")
            folder_url = "https://drive.google.com/drive/folders/1M9q0f3JQLufJASXuAZ8PB86TfkGJDted"
            st.success(
                f"Your new Sales Play can be found here: [Sales Play Library]({folder_url})"
            )
        except Exception as e:
            status.update(label="Error", state="error")
            st.error(f"Something went wrong: {e}")
            raise
