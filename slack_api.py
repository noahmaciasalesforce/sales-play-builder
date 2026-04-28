import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

SLACK_USER_ID = os.environ.get("SLACK_USER_ID", "U06G91AS63X")


def send_dm(play_name: str, presentation_url: str):
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not token:
        raise ValueError("SLACK_BOT_TOKEN env var not set")

    client = WebClient(token=token)

    # Open a DM channel with the user
    response = client.conversations_open(users=[SLACK_USER_ID])
    channel_id = response["channel"]["id"]

    message = (
        f":white_check_mark: New play created: *{play_name}*.\n"
        f"Check the copy here: {presentation_url}\n"
        f"Added to the play library and audit sheet."
    )

    client.chat_postMessage(channel=channel_id, text=message)
