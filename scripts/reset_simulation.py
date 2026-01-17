from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from db import get_connection
from simulation_fixtures import require_local_simulation


def remove_simulation_files(fixtures_dir: Path, logs_dir: Path) -> None:
    if fixtures_dir.exists():
        shutil.rmtree(fixtures_dir)

    if logs_dir.exists():
        errors_dir = logs_dir / "errors"
        for path in logs_dir.iterdir():
            if path == errors_dir:
                continue
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    logs_root = Path("logs")
    if logs_root.exists():
        for path in logs_root.glob("roster-moves-*.md"):
            path.unlink()


def reset_database() -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("TRUNCATE stats")
        cursor.execute("TRUNCATE points")
        cursor.execute("TRUNCATE roster_move_request_players")
        cursor.execute("TRUNCATE roster_move_requests")
        cursor.execute("TRUNCATE mlb_roster_changes")
        cursor.execute("TRUNCATE alumni")
        cursor.execute("TRUNCATE team_player")
        cursor.execute("UPDATE teams SET has_empty_roster_spot = 0")
        conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset simulation artifacts and DB data.")
    parser.add_argument("--fixtures", default="fixtures/2025", help="Fixture directory.")
    parser.add_argument("--logs", default="logs/simulations", help="Simulation logs directory.")
    args = parser.parse_args()

    require_local_simulation()

    remove_simulation_files(Path(args.fixtures), Path(args.logs))
    reset_database()
    print("Simulation reset complete.")


if __name__ == "__main__":
    main()
