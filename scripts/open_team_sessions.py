import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from db import get_connection

TEST_LEAGUE_PATH = ROOT / "test-league.md"


def load_test_league(path):
    sections = {"team names": [], "emails": [], "passwords": []}
    current = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            current = line[3:].strip().lower()
            continue
        if current in sections and line.startswith("- "):
            sections[current].append(line[2:].strip())
    return sections


def main():
    base_url = os.getenv("BASE_URL", "http://127.0.0.1:5000")
    if not TEST_LEAGUE_PATH.exists():
        raise SystemExit("test-league.md not found.")

    data = load_test_league(TEST_LEAGUE_PATH)
    team_names = data["team names"]
    emails = data["emails"]
    passwords = data["passwords"]
    if not (len(team_names) == len(emails) == len(passwords) == 8):
        raise SystemExit("test-league.md must define 8 team names, emails, and passwords.")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT ua.email, ua.team_id
            FROM user_accounts ua
            WHERE ua.email = ANY(%s)
            """,
            (emails,),
        )
        team_by_email = {row["email"]: row["team_id"] for row in cursor.fetchall()}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        contexts = []
        for idx, email in enumerate(emails):
            context = browser.new_context()
            page = context.new_page()
            page.goto(f"{base_url}/login", wait_until="domcontentloaded")
            page.fill('input[name="email"]', email)
            page.fill('input[name="password"]', passwords[idx])
            page.click('button[type="submit"]')
            page.wait_for_load_state("domcontentloaded")
            team_id = team_by_email.get(email)
            if team_id:
                page.goto(f"{base_url}/team?team_id={team_id}", wait_until="domcontentloaded")
            safe_name = re.sub(r"[^A-Za-z0-9_-]+", "-", team_names[idx]).strip("-")
            page.evaluate(f"document.title = 'EBL {safe_name}'")
            contexts.append(context)

        print("Launched sessions for all teams. Close the browser to exit.")
        browser.wait_for_event("disconnected")


if __name__ == "__main__":
    main()
