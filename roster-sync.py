from datetime import datetime, timezone
import json
import os
from pathlib import Path
from pymlb_statsapi import api

from db import get_connection, ensure_identities

PHILLIES_TEAM_ID = 143


def load_roster_fixture(fixtures_dir, roster_date):
    if not fixtures_dir:
        return None
    date_str = roster_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    roster_path = Path(fixtures_dir) / "roster" / f"{date_str}.json"
    if not roster_path.exists():
        return None
    data = json.loads(roster_path.read_text(encoding="utf-8"))
    return data


def sync_phillies_40_man(roster_date=None, fixtures_dir=None):
    conn = get_connection()
    cursor = conn.cursor()
    ensure_identities(conn, ["players"])

    # Track active MLB IDs this sync
    active_mlb_ids = set()

    # -------------------------
    # 1. Fetch 40-man roster
    # -------------------------
    fixtures_dir = fixtures_dir or os.getenv("FIXTURES_DIR")
    roster_fixture = load_roster_fixture(fixtures_dir, roster_date)
    roster_rows = []
    people_map = {}
    if roster_fixture:
        roster_rows = roster_fixture.get("roster", [])
        people_map = {
            int(person["id"]): person for person in roster_fixture.get("people", [])
        }
    else:
        roster_params = {
            "teamId": PHILLIES_TEAM_ID,
            "rosterType": "40Man",
        }
        if roster_date:
            roster_params["date"] = roster_date
        roster_resp = api.Team.roster(**roster_params)
        roster_json = roster_resp.json()
        roster_rows = roster_json.get("roster", [])

    # -------------------------
    # 2. Process each player
    # -------------------------
    for r in roster_rows:
        mlb_id = int(r["person"]["id"])
        active_mlb_ids.add(mlb_id)

        # Fetch full player record
        person = people_map.get(mlb_id)
        if person is None:
            person_resp = api.Person.person(personIds=[mlb_id])
            person = person_resp.json()["people"][0]

        # Parse fields
        first_name = person.get("firstName")
        last_name = person.get("lastName")
        name = person.get("fullName")
        name_slug = person.get("nameSlug")

        position = person.get("primaryPosition", {})
        bat_side = person.get("batSide", {})
        throw_side = person.get("pitchHand", {})

        cursor.execute("""
        INSERT INTO players (
            mlb_id,
            name,
            first_name,
            last_name,
            name_slug,
            position_code,
            position_name,
            position_type,
            bat_side,
            throw_side,
            jersey_number,
            status,
            birth_date,
            birth_city,
            birth_state,
            birth_country,
            height,
            weight,
            is_active,
            last_updated
        )
        VALUES (
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s
        )
        ON CONFLICT(mlb_id) DO UPDATE SET
            name              = excluded.name,
            first_name        = excluded.first_name,
            last_name         = excluded.last_name,
            name_slug         = excluded.name_slug,
            position_code     = excluded.position_code,
            position_name     = excluded.position_name,
            position_type     = excluded.position_type,
            bat_side          = excluded.bat_side,
            throw_side        = excluded.throw_side,
            jersey_number     = excluded.jersey_number,
            status            = excluded.status,
            birth_date        = excluded.birth_date,
            birth_city        = excluded.birth_city,
            birth_state       = excluded.birth_state,
            birth_country     = excluded.birth_country,
            height            = excluded.height,
            weight            = excluded.weight,
            is_active         = 1,
            last_updated      = excluded.last_updated;
        """, (
            mlb_id,
            name,
            first_name,
            last_name,
            name_slug,
            position.get("code"),
            position.get("name"),
            position.get("type"),
            bat_side.get("code"),
            throw_side.get("code"),
            int(person["primaryNumber"]) if person.get("primaryNumber") else None,
            person.get("status", {}).get("description"),
            person.get("birthDate"),
            person.get("birthCity"),
            person.get("birthStateProvince"),
            person.get("birthCountry"),
            person.get("height"),
            int(person["weight"]) if person.get("weight") else None,
            datetime.now(timezone.utc).isoformat(sep=" ")
        ))

    # -------------------------
    # 3. Deactivate removed players
    # -------------------------
    if active_mlb_ids:
        placeholders = ",".join(["%s"] * len(active_mlb_ids))
        deactivated_at = datetime.now(timezone.utc).isoformat(sep=" ")
        cursor.execute(
            f"""
            UPDATE players
            SET is_active = 0,
                last_updated = %s
            WHERE is_active = 1
              AND mlb_id NOT IN ({placeholders})
            RETURNING id
            """,
            (deactivated_at, *active_mlb_ids),
        )
        removed_player_ids = [row["id"] for row in cursor.fetchall()]
        if removed_player_ids:
            removed_placeholders = ",".join(["%s"] * len(removed_player_ids))
            cursor.execute(
                f"""
                SELECT player_id, team_id
                FROM team_player
                WHERE player_id IN ({removed_placeholders})
                """,
                removed_player_ids,
            )
            assignments = cursor.fetchall()
            if assignments:
                cursor.executemany(
                    """
                    INSERT INTO alumni (player_id, team_id, deactivated_at)
                    VALUES (%s, %s, %s)
                    """,
                    [
                        (row["player_id"], row["team_id"], deactivated_at)
                        for row in assignments
                    ],
                )
            cursor.execute(
                f"""
                UPDATE teams
                SET has_empty_roster_spot = 1
                WHERE id IN (
                    SELECT team_id
                    FROM team_player
                    WHERE player_id IN ({removed_placeholders})
                )
                """,
                removed_player_ids,
            )

    conn.commit()
    conn.close()

    print(f"Roster sync complete: {len(active_mlb_ids)} active players.")

if __name__ == "__main__":
    roster_date = None
    while True:
        roster_input = input("Roster date (YYYY-MM-DD, blank for today): ").strip()
        if not roster_input:
            break
        try:
            datetime.strptime(roster_input, "%Y-%m-%d")
        except ValueError:
            print("Invalid date format. Use YYYY-MM-DD.")
            continue
        roster_date = roster_input
        break
    sync_phillies_40_man(roster_date=roster_date)
