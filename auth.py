"""
Run this once to authorise your personal Google account:
    python auth.py

Opens a browser, asks you to sign in and grant access, then writes token.json.
The app auto-refreshes the token when it expires — you won't need to run this again
unless you revoke access or delete token.json.
"""
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CREDENTIALS_PATH = Path(__file__).parent / "credentials.json"
TOKEN_PATH = Path(__file__).parent / "token.json"


def main():
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            "credentials.json not found.\n"
            "Download it from Google Cloud Console → APIs & Services → Credentials → "
            "your OAuth 2.0 Client ID → Download JSON, and place it here."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)
    TOKEN_PATH.write_text(creds.to_json())
    print(f"✓ Authorised. Token saved to {TOKEN_PATH}")


if __name__ == "__main__":
    main()
