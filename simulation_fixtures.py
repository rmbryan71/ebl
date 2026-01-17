from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

SCHEMA_VERSION = 1

MANIFEST_FIELDS = ("schema_version", "season", "start_date", "end_date", "captured_at", "source", "notes")
ROSTER_FIELDS = ("date", "team_id", "mlb_player_ids", "players")
ROSTER_PLAYER_FIELDS = (
    "mlb_player_id",
    "name",
    "position_code",
    "position_name",
    "position_type",
)
STATS_FIELDS = ("date", "players")
STATS_PLAYER_FIELDS = ("mlb_player_id", "outs", "offense")


def load_json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def require_local_simulation() -> None:
    if os.getenv("SIMULATION_MODE") != "1":
        raise SystemExit("SIMULATION_MODE=1 is required for simulation scripts.")

    if os.getenv("RENDER") or os.getenv("RENDER_SERVICE_NAME"):
        raise SystemExit("Simulation scripts are blocked on Render.")

    database_url = os.getenv("DATABASE_URL", "")
    if database_url:
        parsed = urlparse(database_url)
        host = parsed.hostname or ""
        query = parsed.query or ""
        if "host=/tmp" in query:
            return
        if host and host not in {"localhost", "127.0.0.1"}:
            raise SystemExit("Simulation scripts are blocked on non-local DATABASE_URL.")


def validate_manifest(data: dict[str, Any]) -> None:
    _require_fields(data, MANIFEST_FIELDS, "manifest")
    if data["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"manifest.schema_version must be {SCHEMA_VERSION}")
    if not isinstance(data["season"], int):
        raise ValueError("manifest.season must be an int")
    _parse_date_str(data["start_date"], "manifest.start_date")
    _parse_date_str(data["end_date"], "manifest.end_date")
    _parse_iso_datetime(data["captured_at"], "manifest.captured_at")
    _require_nonempty_str(data["source"], "manifest.source")
    if not isinstance(data["notes"], str):
        raise ValueError("manifest.notes must be a string")


def validate_roster_fixture(data: dict[str, Any]) -> None:
    _require_fields(data, ROSTER_FIELDS, "roster")
    _parse_date_str(data["date"], "roster.date")
    if not isinstance(data["team_id"], int):
        raise ValueError("roster.team_id must be an int")
    mlb_player_ids = data["mlb_player_ids"]
    if not isinstance(mlb_player_ids, list):
        raise ValueError("roster.mlb_player_ids must be a list")
    if any(not isinstance(item, int) for item in mlb_player_ids):
        raise ValueError("roster.mlb_player_ids must contain ints")
    if len(set(mlb_player_ids)) != len(mlb_player_ids):
        raise ValueError("roster.mlb_player_ids must be unique")
    players = data["players"]
    if not isinstance(players, list):
        raise ValueError("roster.players must be a list")
    seen_ids = set()
    for entry in players:
        if not isinstance(entry, dict):
            raise ValueError("roster.players entries must be objects")
        _require_fields(entry, ROSTER_PLAYER_FIELDS, "roster.players entry")
        if not isinstance(entry["mlb_player_id"], int):
            raise ValueError("roster.players.mlb_player_id must be an int")
        if not isinstance(entry["name"], str) or not entry["name"].strip():
            raise ValueError("roster.players.name must be a non-empty string")
        for field in ("position_code", "position_name", "position_type"):
            if entry[field] is not None and not isinstance(entry[field], str):
                raise ValueError(f"roster.players.{field} must be a string or null")
        if entry["mlb_player_id"] in seen_ids:
            raise ValueError("roster.players.mlb_player_id must be unique")
        seen_ids.add(entry["mlb_player_id"])
    if seen_ids != set(mlb_player_ids):
        raise ValueError("roster.players must match roster.mlb_player_ids")


def validate_stats_fixture(data: dict[str, Any]) -> None:
    _require_fields(data, STATS_FIELDS, "stats")
    _parse_date_str(data["date"], "stats.date")
    players = data["players"]
    if not isinstance(players, list):
        raise ValueError("stats.players must be a list")
    for entry in players:
        if not isinstance(entry, dict):
            raise ValueError("stats.players entries must be objects")
        _require_fields(entry, STATS_PLAYER_FIELDS, "stats.players entry")
        if not isinstance(entry["mlb_player_id"], int):
            raise ValueError("stats.players.mlb_player_id must be an int")
        if not isinstance(entry["outs"], int):
            raise ValueError("stats.players.outs must be an int")
        if not isinstance(entry["offense"], int):
            raise ValueError("stats.players.offense must be an int")
        if entry["outs"] < 0 or entry["offense"] < 0:
            raise ValueError("stats.players values must be >= 0")


def _require_fields(data: dict[str, Any], fields: tuple[str, ...], label: str) -> None:
    missing = [field for field in fields if field not in data]
    if missing:
        missing_list = ", ".join(missing)
        raise ValueError(f"{label} missing fields: {missing_list}")


def _parse_date_str(value: Any, field: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a YYYY-MM-DD string")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{field} must be a YYYY-MM-DD string") from exc
    if value != parsed.isoformat():
        raise ValueError(f"{field} must be a YYYY-MM-DD string")


def _parse_iso_datetime(value: Any, field: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO datetime string")
    try:
        datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO datetime string") from exc


def _require_nonempty_str(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
