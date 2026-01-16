from datetime import date, datetime, timedelta, timezone
import json

import requests
from pymlb_statsapi import api

from db import get_connection, ensure_identities

PHILLIES_TEAM_ID = 143
TRANSACTION_ADD_PATTERNS = (
    "added to 40-man roster",
    "selected from",
    "signed and added to 40-man roster",
)
TRANSACTION_REMOVE_PATTERNS = (
    "designated for assignment",
    "outrighted",
    "released",
    "traded",
    "claimed off waivers",
    "removed from 40-man roster",
)


def transaction_matches(patterns, description):
    if not description:
        return False
    lowered = description.lower()
    return any(pattern in lowered for pattern in patterns)


def fetch_transactions(start_date, end_date):
    params = {
        "teamId": PHILLIES_TEAM_ID,
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
    }
    response = requests.get(
        "https://statsapi.mlb.com/api/v1/transactions",
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("transactions", [])


def upsert_player(cursor, person):
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
            int(person["weight"]) if person.get("weight") else None,
            datetime.now(timezone.utc).isoformat(sep=" "),
        ),
    )


def deactivate_player(cursor, player_id, deactivated_at):
    cursor.execute(
        """
        UPDATE players
        SET is_active = 0,
            last_updated = %s
        WHERE id = %s
          AND is_active = 1
        """,
        (deactivated_at, player_id),
    )
    cursor.execute(
        "SELECT player_id, team_id FROM team_player WHERE player_id = %s",
        (player_id,),
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
        """
        UPDATE teams
        SET has_empty_roster_spot = 1
        WHERE id IN (
            SELECT team_id
            FROM team_player
            WHERE player_id = %s
        )
        """,
        (player_id,),
    )
    cursor.execute(
        "DELETE FROM team_player WHERE player_id = %s",
        (player_id,),
    )


def sync_phillies_40_man(end_date=None, window_days=7):
    conn = get_connection()
    cursor = conn.cursor()
    ensure_identities(conn, ["players", "mlb_transactions"])

    end_day = end_date or date.today()
    start_day = end_day - timedelta(days=window_days - 1)
    transactions = fetch_transactions(start_day, end_day)
    processed = 0

    for txn in transactions:
        txn_id = txn.get("transactionId") or txn.get("id")
        if not txn_id:
            continue
        txn_id = str(txn_id)
        person = txn.get("person") or {}
        player_mlb_id = person.get("id")
        description = txn.get("description", "")
        type_desc = txn.get("typeDesc", "")
        type_code = txn.get("typeCode", "")
        transaction_date = txn.get("date") or txn.get("transactionDate")
        effective_date = txn.get("effectiveDate")
        cursor.execute(
            """
            INSERT INTO mlb_transactions (
                mlb_transaction_id,
                player_mlb_id,
                player_name,
                transaction_date,
                effective_date,
                type_code,
                type_desc,
                description,
                raw_payload
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (mlb_transaction_id) DO NOTHING
            RETURNING id
            """,
            (
                txn_id,
                int(player_mlb_id) if player_mlb_id else None,
                person.get("fullName"),
                transaction_date,
                effective_date,
                type_code,
                type_desc,
                description,
                json.dumps(txn),
            ),
        )
        inserted = cursor.fetchone()
        if not inserted:
            continue
        processed += 1
        if not player_mlb_id:
            continue
        player_mlb_id = int(player_mlb_id)
        person_resp = api.Person.person(personIds=player_mlb_id)
        person_data = person_resp.json().get("people", [])
        if person_data:
            upsert_player(cursor, person_data[0])

        if transaction_matches(TRANSACTION_REMOVE_PATTERNS, description) or transaction_matches(
            TRANSACTION_REMOVE_PATTERNS, type_desc
        ):
            cursor.execute("SELECT id FROM players WHERE mlb_id = %s", (player_mlb_id,))
            row = cursor.fetchone()
            if row:
                deactivate_player(cursor, row["id"], datetime.now(timezone.utc).isoformat(sep=" "))

        if transaction_matches(TRANSACTION_ADD_PATTERNS, description) or transaction_matches(
            TRANSACTION_ADD_PATTERNS, type_desc
        ):
            cursor.execute(
                "UPDATE players SET is_active = 1 WHERE mlb_id = %s",
                (player_mlb_id,),
            )

    cursor.execute(
        """
        UPDATE teams
        SET has_empty_roster_spot = 1
        WHERE id IN (
            SELECT tp.team_id
            FROM team_player tp
            JOIN players p ON p.id = tp.player_id
            WHERE p.is_active = 0
        )
        """
    )
    cursor.execute(
        """
        DELETE FROM team_player
        WHERE player_id IN (
            SELECT id
            FROM players
            WHERE is_active = 0
        )
        """
    )

    conn.commit()
    conn.close()

    print(
        f"Transactions sync complete: {processed} new transactions from "
        f"{start_day.isoformat()} to {end_day.isoformat()}."
    )


if __name__ == "__main__":
    window_input = input("Window days (default 7): ").strip()
    end_input = input("End date (YYYY-MM-DD, blank for today): ").strip()
    window_days = int(window_input) if window_input else 7
    end_date = None
    if end_input:
        try:
            end_date = datetime.strptime(end_input, "%Y-%m-%d").date()
        except ValueError as exc:
            raise SystemExit("Invalid date format. Use YYYY-MM-DD.") from exc
    sync_phillies_40_man(end_date=end_date, window_days=window_days)
