import requests
import sqlite3
from datetime import datetime

PHILLIES_TEAM_ID = 143

def sync_phillies_40_man(db_path="ebl.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Track active MLB IDs this sync
    active_mlb_ids = set()

    # -------------------------
    # 1. Fetch 40-man roster
    # -------------------------
    roster_url = "https://lookup-service-prod.mlb.com/json/named.roster_40.bam"
    roster_resp = requests.get(roster_url, params={"team_id": PHILLIES_TEAM_ID})
    roster_resp.raise_for_status()

    roster_json = roster_resp.json()
    roster_rows = roster_json["roster_40"]["queryResults"]["row"]

    if isinstance(roster_rows, dict):
        roster_rows = [roster_rows]

    # -------------------------
    # 2. Process each player
    # -------------------------
    for r in roster_rows:
        mlb_id = int(r["player_id"])
        active_mlb_ids.add(mlb_id)

        # Fetch full player record
        person_url = f"https://statsapi.mlb.com/api/v1/people/{mlb_id}"
        person_resp = requests.get(person_url)
        person_resp.raise_for_status()

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
            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?
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
            datetime.utcnow().isoformat(sep=" ")
        ))

    # -------------------------
    # 3. Deactivate removed players
    # -------------------------
    cursor.execute("""
    UPDATE players
    SET is_active = 0,
        last_updated = ?
    WHERE mlb_id NOT IN ({})
    """.format(",".join("?" * len(active_mlb_ids))),
    (datetime.utcnow().isoformat(sep=" "), *active_mlb_ids))

    conn.commit()
    conn.close()

    print(f"Roster sync complete: {len(active_mlb_ids)} active players.")

sync_phillies_40_man("ebl.db")