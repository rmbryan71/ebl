from datetime import datetime, timezone
from pymlb_statsapi import api

from db import ensure_identities

PHILLIES_TEAM_ID = 143


def fetch_roster_mlb_ids(roster_date=None):
    roster_params = {
        "teamId": PHILLIES_TEAM_ID,
        "rosterType": "40Man",
    }
    if roster_date:
        roster_params["date"] = roster_date
    roster_resp = api.Team.roster(**roster_params)
    roster_json = roster_resp.json()
    roster_rows = roster_json.get("roster", [])
    return [int(row["person"]["id"]) for row in roster_rows]


def load_active_mlb_ids(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT mlb_id FROM players WHERE is_active = 1")
    return {row["mlb_id"] for row in cursor.fetchall()}


def insert_new_player(cursor, person):
    position = person.get("primaryPosition", {})
    bat_side = person.get("batSide", {})
    throw_side = person.get("pitchHand", {})
    cursor.execute(
        """
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
        ON CONFLICT(mlb_id) DO NOTHING
        """,
        (
            int(person["id"]),
            person.get("fullName"),
            person.get("firstName"),
            person.get("lastName"),
            person.get("nameSlug"),
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
            int(person.get("weight") or 0) if person.get("weight") else None,
            datetime.now(timezone.utc).isoformat(sep=" "),
        ),
    )


def sync_players(conn, roster_date=None, roster_ids=None):
    cursor = conn.cursor()
    ensure_identities(conn, ["players"])
    roster_ids = roster_ids or fetch_roster_mlb_ids(roster_date)
    roster_ids_set = set(roster_ids)

    cursor.execute("SELECT mlb_id FROM players")
    existing_ids = {row["mlb_id"] for row in cursor.fetchall()}
    new_ids = roster_ids_set - existing_ids

    for mlb_id in sorted(new_ids):
        person_resp = api.Person.person(personIds=mlb_id)
        people = person_resp.json().get("people", [])
        if not people:
            continue
        insert_new_player(cursor, people[0])

    now = datetime.now(timezone.utc).isoformat(sep=" ")
    if roster_ids:
        cursor.execute(
            """
            UPDATE players
            SET is_active = 1,
                last_updated = %s
            WHERE mlb_id = ANY(%s)
            """,
            (now, roster_ids),
        )
        cursor.execute(
            """
            UPDATE players
            SET is_active = 0,
                last_updated = %s
            WHERE is_active = 1
              AND NOT (mlb_id = ANY(%s))
            """,
            (now, roster_ids),
        )

    return roster_ids_set


def apply_mlb_roster_changes(conn, before_set, after_set, change_date, source="snapshot"):
    cursor = conn.cursor()
    added = sorted(after_set - before_set)
    removed = sorted(before_set - after_set)

    change_rows = []
    for mlb_id in added:
        change_rows.append((mlb_id, change_date, "add", source, None))
    for mlb_id in removed:
        change_rows.append((mlb_id, change_date, "remove", source, None))
    if change_rows:
        cursor.executemany(
            """
            INSERT INTO mlb_roster_changes (
                player_mlb_id,
                change_date,
                change_type,
                source,
                notes
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (player_mlb_id, change_date, change_type) DO NOTHING
            """,
            change_rows,
        )

    if not removed:
        return

    cursor.execute(
        """
        SELECT player_mlb_id, team_id
        FROM team_player
        WHERE player_mlb_id = ANY(%s)
        """,
        (removed,),
    )
    assignments = cursor.fetchall()
    if assignments:
        deactivated_at = datetime.now(timezone.utc).isoformat(sep=" ")
        cursor.executemany(
            """
            INSERT INTO alumni (player_mlb_id, team_id, deactivated_at)
            VALUES (%s, %s, %s)
            """,
            [
                (row["player_mlb_id"], row["team_id"], deactivated_at)
                for row in assignments
            ],
        )
        cursor.execute(
            """
            UPDATE teams
            SET has_empty_roster_spot = 1
            WHERE id = ANY(%s)
            """,
            ([row["team_id"] for row in assignments],),
        )
    cursor.execute(
        "DELETE FROM team_player WHERE player_mlb_id = ANY(%s)",
        (removed,),
    )


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

    from db import get_connection

    with get_connection() as conn:
        before_set = load_active_mlb_ids(conn)
        after_set = sync_players(conn, roster_date=roster_date)
        change_date = roster_date or datetime.now(timezone.utc).date().isoformat()
        apply_mlb_roster_changes(
            conn,
            before_set,
            after_set,
            change_date,
            source="manual",
        )
        conn.commit()

    print("Roster sync complete (players + roster changes).")
