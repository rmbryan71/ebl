import os
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from db import get_connection

TEST_LEAGUE_PATH = ROOT / "test-league.md"
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "adminpass")


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


def login_and_open(page, base_url, email, password, destination, title):
    page.goto(f"{base_url}/login", wait_until="domcontentloaded")
    page.fill('input[name="email"]', email)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_load_state("domcontentloaded")
    page.goto(f"{base_url}{destination}", wait_until="domcontentloaded")
    safe_title = re.sub(r"[^A-Za-z0-9_-]+", "-", title).strip("-")
    page.evaluate(f"document.title = '{safe_title}'")


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

        admin_context = browser.new_context()
        admin_page = admin_context.new_page()
        login_and_open(
            admin_page,
            base_url,
            ADMIN_EMAIL,
            ADMIN_PASSWORD,
            "/pending-roster-moves",
            "EBL Admin",
        )
        contexts.append(admin_context)

        for idx, email in enumerate(emails):
            context = browser.new_context()
            page = context.new_page()
            team_id = team_by_email.get(email)
            destination = f"/team?team_id={team_id}" if team_id else "/"
            login_and_open(
                page,
                base_url,
                email,
                passwords[idx],
                destination,
                f"EBL {team_names[idx]}",
            )
            contexts.append(context)

        print("Launched sessions for all teams plus admin. Press Ctrl+C to close.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return


if __name__ == "__main__":
    main()
