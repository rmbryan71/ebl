import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from db import get_connection, set_audit_user_id


EASTERN_TZ = ZoneInfo("America/New_York")
LOGS_DIR = Path(__file__).resolve().parent / "logs"



def load_team_points(cursor):
    cursor.execute(
        """
        SELECT t.id AS team_id, COALESCE(SUM(p.value), 0) AS total_points
        FROM teams t
        LEFT JOIN points p ON p.team_id = t.id
        GROUP BY t.id
        """
    )
    return {row["team_id"]: row["total_points"] for row in cursor.fetchall()}


def load_pending_requests(cursor):
    cursor.execute(
        """
        SELECT r.id, r.team_id, r.submitted, t.name AS team_name, t.has_empty_roster_spot
        FROM roster_move_requests r
        JOIN teams t ON t.id = r.team_id
        WHERE r.status = 'pending'
        ORDER BY r.submitted DESC
        """
    )
    requests = cursor.fetchall()
    by_team = {}
    for row in requests:
        by_team.setdefault(row["team_id"], []).append(row)
    return by_team


def load_request_players(cursor, request_id):
    cursor.execute(
        """
        SELECT rmp.player_id, rmp.action, rmp.priority, p.name AS player_name
        FROM roster_move_request_players rmp
        JOIN players p ON p.id = rmp.player_id
        WHERE rmp.roster_move_request_id = %s
        ORDER BY rmp.action, rmp.priority NULLS LAST
        """,
        (request_id,),
    )
    return cursor.fetchall()


def load_available_players(cursor):
    cursor.execute(
        """
        SELECT p.id
        FROM players p
        LEFT JOIN team_player tp ON tp.player_id = p.id
        WHERE p.is_active = 1 AND tp.player_id IS NULL
        """
    )
    return {row["id"] for row in cursor.fetchall()}


def load_team_roster(cursor, team_id):
    cursor.execute(
        """
        SELECT p.id, p.name
        FROM team_player tp
        JOIN players p ON p.id = tp.player_id
        WHERE tp.team_id = %s
        ORDER BY p.name
        """,
        (team_id,),
    )
    return cursor.fetchall()


def order_teams(team_info):
    empty_groups = {}
    full_groups = {}
    for info in team_info:
        key = info["points"]
        if info["has_empty_roster_spot"]:
            empty_groups.setdefault(key, []).append(info)
        else:
            full_groups.setdefault(key, []).append(info)

    ordered = []
    for points in sorted(empty_groups.keys()):
        group = empty_groups[points]
        group.sort(key=lambda item: item["submitted"] or "")
        ordered.extend(group)
    for points in sorted(full_groups.keys()):
        group = full_groups[points]
        group.sort(key=lambda item: item["submitted"] or "")
        ordered.extend(group)
    return ordered


def write_log(entries, processed_count):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(EASTERN_TZ).date().isoformat()
    log_path = LOGS_DIR / f"roster-moves-{today}.md"
    lines = [
        f"# Roster move processing: {today}",
        "",
        f"- Processed requests: {processed_count}",
        "",
    ]
    lines.extend(entries)
    log_path.write_text("\n".join(lines), encoding="utf-8")
    return log_path


def main():
    if not os.getenv("DATABASE_URL"):
        raise SystemExit("DATABASE_URL is not set.")

    log_entries = []
    processed = 0

    with get_connection() as conn:
        cursor = conn.cursor()
        set_audit_user_id(conn, 0)

        points_by_team = load_team_points(cursor)
        pending_by_team = load_pending_requests(cursor)
        if not pending_by_team:
            write_log(["No pending roster move requests."], 0)
            print("No pending roster move requests.")
            return

        team_info = []
        for team_id, requests in pending_by_team.items():
            request = requests[0]
            team_info.append(
                {
                    "team_id": team_id,
                    "team_name": request["team_name"],
                    "request_id": request["id"],
                    "submitted": request["submitted"],
                    "has_empty_roster_spot": bool(request["has_empty_roster_spot"]),
                    "points": points_by_team.get(team_id, 0),
                }
            )

        ordered = order_teams(team_info)
        log_entries.append("## Processing order")
        for idx, info in enumerate(ordered, start=1):
            log_entries.append(
                f"{idx}. {info['team_name']} (points: {info['points']}, empty: {int(info['has_empty_roster_spot'])})"
            )
        log_entries.append("")

        available_players = load_available_players(cursor)
        for info in ordered:
            request_id = info["request_id"]
            team_id = info["team_id"]
            team_name = info["team_name"]
            roster = load_team_roster(cursor, team_id)
            roster_ids = {row["id"] for row in roster}
            players = load_request_players(cursor, request_id)
            drop = next((p for p in players if p["action"] == "drop"), None)
            add_choices = [p for p in players if p["action"] == "add"]

            log_entries.append(f"## {team_name}")
            log_entries.append(f"- Request ID: {request_id}")
            log_entries.append(f"- Submitted: {info['submitted']}")
            if drop:
                log_entries.append(f"- Drop: {drop['player_name']}")
                if drop["player_id"] not in roster_ids:
                    cursor.execute(
                        "UPDATE roster_move_requests SET status = 'failed' WHERE id = %s",
                        (request_id,),
                    )
                    log_entries.append("- Result: failed (drop player not on team)")
                    log_entries.append("")
                    processed += 1
                    continue
            else:
                if not info["has_empty_roster_spot"]:
                    cursor.execute(
                        "UPDATE roster_move_requests SET status = 'failed' WHERE id = %s",
                        (request_id,),
                    )
                    log_entries.append("- Drop: none")
                    log_entries.append("- Result: failed (drop required)")
                    log_entries.append("")
                    processed += 1
                    continue
                log_entries.append("- Drop: none (empty roster spot)")

            selected_add = None
            for choice in add_choices:
                if choice["player_id"] in available_players:
                    selected_add = choice
                    break

            if not selected_add:
                cursor.execute(
                    "UPDATE roster_move_requests SET status = 'failed' WHERE id = %s",
                    (request_id,),
                )
                cursor.execute(
                    "UPDATE teams SET has_empty_roster_spot = 1 WHERE id = %s",
                    (team_id,),
                )
                log_entries.append("- Add choices: none available")
                log_entries.append("- Result: failed (no available adds)")
                log_entries.append("")
                processed += 1
                continue

            if drop:
                cursor.execute(
                    "DELETE FROM team_player WHERE team_id = %s AND player_id = %s",
                    (team_id, drop["player_id"]),
                )
            cursor.execute(
                "INSERT INTO team_player (team_id, player_id) VALUES (%s, %s)",
                (team_id, selected_add["player_id"]),
            )
            available_players.discard(selected_add["player_id"])
            if drop:
                available_players.add(drop["player_id"])

            cursor.execute(
                "UPDATE roster_move_requests SET status = 'processed' WHERE id = %s",
                (request_id,),
            )
            cursor.execute(
                "UPDATE teams SET has_empty_roster_spot = 0 WHERE id = %s",
                (team_id,),
            )
            log_entries.append(f"- Add: {selected_add['player_name']} (priority {selected_add['priority']})")
            log_entries.append("- Result: processed")
            log_entries.append("")
            processed += 1

        conn.commit()

    log_path = write_log(log_entries, processed)
    print(f"Processed {processed} roster move requests.")
    print(f"Wrote log to {log_path}")


if __name__ == "__main__":
    main()
