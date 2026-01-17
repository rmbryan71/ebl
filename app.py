from collections import defaultdict, deque
from datetime import date, datetime, timedelta
import os
from pathlib import Path
import subprocess
import sys
from functools import wraps
import time
from zoneinfo import ZoneInfo

from flask import Flask, abort, redirect, render_template, request
import markdown
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.security import check_password_hash

from db import get_connection, set_audit_user_id

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
app.config["REMEMBER_COOKIE_DURATION"] = timedelta(days=30)

login_manager = LoginManager()
login_manager.login_view = "login_view"
login_manager.init_app(app)

class AuthUser(UserMixin):
    def __init__(self, user_id, email, role, team_id=None, is_active=True):
        self.id = user_id
        self.email = email
        self.role = role
        self.team_id = team_id
        self.active = bool(is_active)

    @property
    def is_active(self):
        return self.active


@login_manager.user_loader
def load_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, email, role, team_id, is_active
        FROM user_accounts
        WHERE id = %s
        """,
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return AuthUser(row["id"], row["email"], row["role"], row["team_id"], row["is_active"])


def owner_or_admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if current_user.role not in {"admin", "owner"}:
            abort(403)
        return view_func(*args, **kwargs)

    return wrapper


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if current_user.role != "admin":
            abort(403)
        return view_func(*args, **kwargs)

    return wrapper

RATE_LIMITS = {
    "default": (120, 60),
    "audit": (30, 60),
}
REQUEST_HISTORY = defaultdict(deque)
ENFORCE_HTTPS = os.getenv("FORCE_HTTPS", "").lower() in {"1", "true", "yes"}
AUTO_BUILD_NEWS = os.getenv("AUTO_BUILD_NEWS", "").lower() in {"1", "true", "yes"}
EASTERN_TZ = ZoneInfo("America/New_York")

RULES_PATH = Path(__file__).resolve().parent / "rules.md"


def get_client_ip():
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr or "unknown"


def apply_rate_limit(bucket, max_requests, window_seconds):
    now = time.time()
    history = REQUEST_HISTORY[bucket]
    while history and now - history[0] > window_seconds:
        history.popleft()
    if len(history) >= max_requests:
        abort(429)
    history.append(now)


@app.before_request
def enforce_https_and_rate_limit():
    if request.path.startswith("/static/"):
        return None

    if ENFORCE_HTTPS and not request.is_secure:
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
        if forwarded_proto == "http":
            return redirect(request.url.replace("http://", "https://", 1), code=301)

    ip = get_client_ip()
    limit_key = "audit" if request.path == "/audit" else "default"
    max_requests, window_seconds = RATE_LIMITS[limit_key]
    apply_rate_limit(f"{limit_key}:{ip}", max_requests, window_seconds)
    return None


def should_build_news():
    if os.getenv("DISABLE_NEWS_BUILD", "").lower() in {"1", "true", "yes"}:
        return False
    return True


NEWS_BUILT = False


@app.before_request
def build_news_on_startup():
    global NEWS_BUILT
    if NEWS_BUILT or not should_build_news():
        return None
    script_path = Path(__file__).resolve().parent / "scripts" / "build_news.py"
    if not script_path.exists():
        NEWS_BUILT = True
        return None
    try:
        subprocess.run([sys.executable, str(script_path)], check=True)
    except subprocess.CalledProcessError:
        print("Warning: scripts/build_news.py failed to run on startup.")
    NEWS_BUILT = True
    return None


@app.after_request
def add_security_headers(response):
    csp = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "script-src 'self'; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "upgrade-insecure-requests"
    )
    response.headers.setdefault("Content-Security-Policy", csp)
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    if request.is_secure or request.headers.get("X-Forwarded-Proto", "") == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def load_roster():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            t.name AS team_name,
            t.id AS team_id,
            p.mlb_id AS player_id,
            p.name,
            p.position_name,
            p.is_active
        FROM players p
        LEFT JOIN team_player tp ON tp.player_mlb_id = p.mlb_id
        LEFT JOIN teams t ON t.id = tp.team_id
        WHERE p.is_active = 1
        ORDER BY t.name IS NULL, t.name, p.name
    """)
    rows = cursor.fetchall()
    conn.close()

    grouped = defaultdict(list)
    for row in rows:
        if row["team_name"] is None:
            continue
        position_name = row["position_name"] or ""
        display_position = "Pitcher" if position_name == "Pitcher" else "Hitter"
        row_dict = dict(row)
        row_dict["display_position"] = display_position
        grouped[row["team_name"]].append(row_dict)

    teams = []
    for name in sorted(grouped.keys()):
        team_id = grouped[name][0].get("team_id")
        teams.append({"id": team_id, "name": name, "players": grouped[name]})
    total_players = sum(len(team["players"]) for team in teams)

    return teams, total_players


def load_team_stats(team_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name FROM teams ORDER BY name")
    teams = cursor.fetchall()
    if not teams:
        conn.close()
        return [], None, [], None

    selected_team_id = team_id or teams[0]["id"]
    params = [selected_team_id]
    date_filter = ""
    cursor.execute(
        """
        SELECT
            s.date,
            s.offense,
            s.pitching,
            p.mlb_id AS player_id,
            p.name AS player_name
        FROM stats s
        JOIN players p ON p.mlb_id = s.player_mlb_id
        WHERE s.team_id = %s
          AND (COALESCE(s.offense, 0) != 0 OR COALESCE(s.pitching, 0) != 0)
        """ + date_filter + """
        ORDER BY s.date DESC, p.name
        """,
        params,
    )
    rows = cursor.fetchall()
    for row in rows:
        value = row["date"]
        if isinstance(value, datetime):
            row["date"] = value.date().strftime("%b %-d, %Y")
        elif isinstance(value, date):
            row["date"] = value.strftime("%b %-d, %Y")
        else:
            try:
                row["date"] = datetime.strptime(value, "%Y-%m-%d").strftime("%b %-d, %Y")
            except (TypeError, ValueError):
                row["date"] = value

    cursor.execute(
        """
        SELECT
            p.mlb_id AS player_id,
            p.name AS player_name,
            COALESCE(SUM(s.offense), 0) AS total_offense,
            COALESCE(SUM(s.pitching), 0) AS total_pitching
        FROM team_player tp
        JOIN players p ON p.mlb_id = tp.player_mlb_id
        LEFT JOIN stats s
            ON s.player_mlb_id = p.mlb_id AND s.team_id = tp.team_id
        WHERE tp.team_id = %s
        GROUP BY p.mlb_id
        ORDER BY p.name
        """,
        (selected_team_id,),
    )
    player_totals = cursor.fetchall()

    totals_params = [selected_team_id]
    totals_filter = ""
    cursor.execute(
        """
        SELECT
            SUM(offense) AS total_offense,
            SUM(pitching) AS total_pitching
        FROM stats
        WHERE team_id = %s
        """ + totals_filter,
        totals_params,
    )
    totals = cursor.fetchone()

    conn.close()
    selected_team_name = None
    for team in teams:
        if team["id"] == selected_team_id:
            selected_team_name = team["name"]
            break

    return teams, selected_team_id, selected_team_name, rows, totals, player_totals


def load_team_roster_history(team_id):
    conn = get_connection()
    cursor = conn.cursor()
    history = []

    cursor.execute(
        """
        SELECT MIN(submitted) AS first_submitted
        FROM roster_move_requests
        WHERE team_id = %s
        """,
        (team_id,),
    )
    first_submitted = cursor.fetchone()["first_submitted"]

    if first_submitted:
        cursor.execute(
            """
            SELECT
                a.datetime AS event_time,
                p.name AS player_name
            FROM audit a
            JOIN players p
              ON p.mlb_id = (a.new_value::json->>'player_mlb_id')::int
            WHERE a.table_name = 'team_player'
              AND a.operation = 'INSERT'
              AND (a.new_value::json->>'team_id')::int = %s
              AND a.datetime < %s
            """,
            (team_id, first_submitted),
        )
    else:
        cursor.execute(
            """
            SELECT
                a.datetime AS event_time,
                p.name AS player_name
            FROM audit a
            JOIN players p
              ON p.mlb_id = (a.new_value::json->>'player_mlb_id')::int
            WHERE a.table_name = 'team_player'
              AND a.operation = 'INSERT'
              AND (a.new_value::json->>'team_id')::int = %s
            """,
            (team_id,),
        )
    for row in cursor.fetchall():
        history.append(
            {
                "event_time": row["event_time"],
                "player_name": row["player_name"],
                "action": "Added",
                "reason": "Purchased at auction",
            }
        )

    cursor.execute(
        """
        SELECT r.submitted AS event_time,
               rmp.action,
               p.name AS player_name
        FROM roster_move_requests r
        JOIN roster_move_request_players rmp ON rmp.roster_move_request_id = r.id
        JOIN players p ON p.mlb_id = rmp.player_mlb_id
        WHERE r.team_id = %s AND r.status = 'processed'
        """,
        (team_id,),
    )
    for row in cursor.fetchall():
        history.append(
            {
                "event_time": row["event_time"],
                "player_name": row["player_name"],
                "action": "Added" if row["action"] == "add" else "Dropped",
                "reason": "Roster move processed",
            }
        )

    cursor.execute(
        """
        SELECT a.deactivated_at AS event_time,
               p.name AS player_name
        FROM alumni a
        JOIN players p ON p.mlb_id = a.player_mlb_id
        WHERE a.team_id = %s
        """,
        (team_id,),
    )
    for row in cursor.fetchall():
        history.append(
            {
                "event_time": row["event_time"],
                "player_name": row["player_name"],
                "action": "Dropped",
                "reason": "Removed from MLB 40-man",
            }
        )

    conn.close()

    def to_sort_key(value):
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except (TypeError, ValueError):
            return datetime.min

    history.sort(key=lambda item: to_sort_key(item["event_time"]), reverse=True)

    for entry in history:
        value = entry["event_time"]
        if isinstance(value, datetime):
            entry["event_time"] = value.date().strftime("%b %-d, %Y")
        elif isinstance(value, date):
            entry["event_time"] = value.strftime("%b %-d, %Y")
        else:
            try:
                entry["event_time"] = datetime.strptime(value, "%Y-%m-%d").strftime(
                    "%b %-d, %Y"
                )
            except (TypeError, ValueError):
                entry["event_time"] = value
    return history


@app.route("/")
def roster_view():
    teams, total_players = load_roster()
    return render_template(
        "roster.html",
        teams=teams,
        total_players=total_players,
        team_count=len(teams),
    )


@app.route("/team")
def team_stats():
    team_id = request.args.get("team_id", type=int)
    if team_id is not None and team_id <= 0:
        abort(400)
    teams, selected_team_id, selected_team_name, rows, totals, player_totals = load_team_stats(
        team_id=team_id
    )
    roster_history = []
    if selected_team_id:
        roster_history = load_team_roster_history(selected_team_id)
    show_roster_move = False
    if current_user.is_authenticated:
        if current_user.role == "admin":
            show_roster_move = True
        elif current_user.role == "owner" and current_user.team_id == selected_team_id:
            show_roster_move = True
    return render_template(
        "team-stats.html",
        teams=teams,
        selected_team_id=selected_team_id,
        selected_team_name=selected_team_name,
        rows=rows,
        totals=totals,
        player_totals=player_totals,
        roster_history=roster_history,
        show_roster_move=show_roster_move,
    )


def load_leaderboard(week_start=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT date FROM stats ORDER BY date DESC")
    dates = []
    for row in cursor.fetchall():
        value = row["date"]
        if isinstance(value, datetime):
            dates.append(value.date())
            continue
        if isinstance(value, date):
            dates.append(value)
            continue
        try:
            dates.append(datetime.strptime(value, "%Y-%m-%d").date())
        except (TypeError, ValueError):
            continue
    week_starts = sorted({date - timedelta(days=date.weekday()) for date in dates}, reverse=True)

    selected_week_start = None
    if week_start:
        try:
            parsed = datetime.strptime(week_start, "%Y-%m-%d").date()
            if parsed in week_starts:
                selected_week_start = parsed
        except ValueError:
            selected_week_start = None
    if selected_week_start is None and week_starts:
        selected_week_start = week_starts[0]

    params = []
    join_filter = ""
    selected_week_end = None
    if selected_week_start:
        selected_week_end = selected_week_start + timedelta(days=6)
        join_filter = "AND s.date BETWEEN %s AND %s"
        params.extend([selected_week_start.isoformat(), selected_week_end.isoformat()])

    cursor.execute(
        f"""
        SELECT
            t.id AS team_id,
            t.name AS team_name,
            COALESCE(SUM(s.offense), 0) AS total_offense
        FROM teams t
        LEFT JOIN stats s
            ON s.team_id = t.id
            {join_filter}
        GROUP BY t.id
        ORDER BY total_offense DESC, t.name
        """,
        params,
    )
    offense_rows = cursor.fetchall()

    cursor.execute(
        f"""
        SELECT
            t.id AS team_id,
            t.name AS team_name,
            COALESCE(SUM(s.pitching), 0) AS total_pitching
        FROM teams t
        LEFT JOIN stats s
            ON s.team_id = t.id
            {join_filter}
        GROUP BY t.id
        ORDER BY total_pitching DESC, t.name
        """,
        params,
    )
    pitching_rows = cursor.fetchall()

    offense_points = {}
    pitching_points = {}
    if selected_week_end and selected_week_end < date.today():
        cursor.execute(
            """
            SELECT team_id, value
            FROM points
            WHERE date = %s AND type = 'offense'
            """,
            (selected_week_end.isoformat(),),
        )
        offense_points = {row["team_id"]: row["value"] for row in cursor.fetchall()}

        cursor.execute(
            """
            SELECT team_id, value
            FROM points
            WHERE date = %s AND type = 'defense'
            """,
            (selected_week_end.isoformat(),),
        )
        pitching_points = {row["team_id"]: row["value"] for row in cursor.fetchall()}

    conn.close()
    return (
        offense_rows,
        pitching_rows,
        week_starts,
        selected_week_start,
        offense_points,
        pitching_points,
    )


@app.route("/week")
def week_view():
    week_start = request.args.get("week_start")
    (
        offense_rows,
        pitching_rows,
        week_starts,
        selected_week_start,
        offense_points,
        pitching_points,
    ) = load_leaderboard(week_start=week_start)
    if week_start and selected_week_start is None and week_starts:
        abort(400)
    return render_template(
        "leaderboard.html",
        offense_rows=offense_rows,
        pitching_rows=pitching_rows,
        week_starts=week_starts,
        selected_week_start=selected_week_start,
        offense_points=offense_points,
        pitching_points=pitching_points,
        timedelta=timedelta,
    )


def load_player_details(player_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            p.mlb_id,
            p.name,
            p.birth_date,
            p.position_name,
            t.id AS team_id,
            t.name AS team_name
        FROM players p
        LEFT JOIN team_player tp ON tp.player_mlb_id = p.mlb_id
        LEFT JOIN teams t ON t.id = tp.team_id
        WHERE p.mlb_id = %s
        """,
        (player_id,),
    )
    player = cursor.fetchone()
    if not player:
        conn.close()
        return None, [], None
    position_name = player.get("position_name") or ""
    player["display_position"] = "Pitcher" if position_name == "Pitcher" else "Hitter"

    cursor.execute(
        "SELECT MIN(date) AS first_date FROM stats WHERE player_mlb_id = %s",
        (player_id,),
    )
    first_row = cursor.fetchone()
    year = None
    if first_row and first_row["first_date"]:
        value = first_row["first_date"]
        if isinstance(value, datetime):
            year = value.year
        elif isinstance(value, date):
            year = value.year
        else:
            try:
                year = datetime.strptime(value, "%Y-%m-%d").year
            except (TypeError, ValueError):
                year = None

    stats_rows = []
    if year:
        cursor.execute(
            """
            SELECT date, offense, pitching
            FROM stats
            WHERE player_mlb_id = %s AND date::text LIKE %s
              AND (COALESCE(offense, 0) != 0 OR COALESCE(pitching, 0) != 0)
            ORDER BY date DESC
            """,
            (player_id, f"{year}-%"),
        )
        stats_rows = cursor.fetchall()
        for row in stats_rows:
            value = row["date"]
            if isinstance(value, datetime):
                row["date"] = value.date().strftime("%b %-d, %Y")
            elif isinstance(value, date):
                row["date"] = value.strftime("%b %-d, %Y")
            else:
                try:
                    row["date"] = datetime.strptime(value, "%Y-%m-%d").strftime("%b %-d, %Y")
                except (TypeError, ValueError):
                    row["date"] = value

    conn.close()
    return player, stats_rows, year


@app.route("/player")
def player_view():
    player_id = request.args.get("player_id", type=int)
    if player_id is not None and player_id <= 0:
        abort(400)
    if not player_id:
        return render_template("player.html", player=None, stats_rows=[], year=None)

    player, stats_rows, year = load_player_details(player_id)
    return render_template(
        "player.html",
        player=player,
        stats_rows=stats_rows,
        year=year,
    )


def load_season_totals():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            t.id AS team_id,
            t.name AS team_name,
            COALESCE(SUM(CASE WHEN p.type = 'offense' THEN p.value ELSE 0 END), 0) AS offense_points,
            COALESCE(SUM(CASE WHEN p.type = 'defense' THEN p.value ELSE 0 END), 0) AS pitching_points,
            COALESCE(SUM(p.value), 0) AS total_points
        FROM teams t
        LEFT JOIN points p ON p.team_id = t.id
        GROUP BY t.id
        ORDER BY total_points DESC, t.name
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


@app.route("/season")
def season_view():
    rows = load_season_totals()
    return render_template("season.html", rows=rows)


def load_available_players():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            p.mlb_id,
            p.name,
            p.position_name,
            p.birth_date
        FROM players p
        LEFT JOIN team_player tp ON tp.player_mlb_id = p.mlb_id
        WHERE p.is_active = 1 AND tp.player_mlb_id IS NULL
        ORDER BY p.name
        """
    )
    rows = cursor.fetchall()
    for row in rows:
        position_name = row["position_name"] or ""
        row["display_position"] = "Pitcher" if position_name == "Pitcher" else "Hitter"
    conn.close()
    return rows


@app.route("/available")
def available_view():
    rows = load_available_players()
    return render_template("available.html", rows=rows)


def load_audit(page, page_size=50):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS count FROM audit")
    total = cursor.fetchone()["count"]

    offset = (page - 1) * page_size
    cursor.execute(
        """
        SELECT datetime, table_name, operation, old_value, new_value
        FROM audit
        ORDER BY datetime DESC, id DESC
        LIMIT %s OFFSET %s
        """,
        (page_size, offset),
    )
    rows = cursor.fetchall()
    conn.close()

    total_pages = max(1, (total + page_size - 1) // page_size)
    return rows, total_pages


@app.route("/audit")
@login_required
@owner_or_admin_required
def audit_view():
    page = request.args.get("page", type=int) or 1
    if page < 1:
        abort(400)
    rows, total_pages = load_audit(page)
    return render_template(
        "audit.html",
        rows=rows,
        page=page,
        total_pages=total_pages,
    )


@app.route("/login", methods=["GET", "POST"])
def login_view():
    error = None
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        remember = bool(request.form.get("remember"))
        if email and password:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, email, password_hash, role, team_id, is_active
                FROM user_accounts
                WHERE email = %s
                """,
                (email,),
            )
            row = cursor.fetchone()
            if row and row["is_active"] and check_password_hash(row["password_hash"], password):
                cursor.execute(
                    """
                    INSERT INTO user_login_history (user_id, ip_address, user_agent)
                    VALUES (%s, %s, %s)
                    """,
                    (
                        row["id"],
                        request.headers.get("X-Forwarded-For", request.remote_addr),
                        request.headers.get("User-Agent"),
                    ),
                )
                conn.commit()
            conn.close()
            if row and row["is_active"] and check_password_hash(row["password_hash"], password):
                login_user(
                    AuthUser(
                        row["id"],
                        row["email"],
                        row["role"],
                        row["team_id"],
                        row["is_active"],
                    ),
                    remember=remember,
                )
                return redirect(request.args.get("next") or "/")
        error = "Invalid email or password."
    return render_template("login.html", error=error)


@app.route("/logout")
@login_required
def logout_view():
    logout_user()
    return redirect("/")


@app.route("/profile")
@login_required
def profile_view():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT logged_in_at, ip_address, user_agent
        FROM user_login_history
        WHERE user_id = %s
        ORDER BY logged_in_at DESC
        LIMIT 50
        """,
        (current_user.id,),
    )
    rows = cursor.fetchall()
    conn.close()
    for row in rows:
        value = row["logged_in_at"]
        if isinstance(value, datetime):
            row["logged_in_display"] = value.strftime("%b %-d, %Y %I:%M %p")
        else:
            row["logged_in_display"] = value
    return render_template("profile.html", rows=rows)


@app.route("/roster-move", methods=["GET", "POST"])
@login_required
@owner_or_admin_required
def roster_move_view():
    if current_user.role == "admin":
        team_id = request.args.get("team_id", type=int) or request.form.get("team_id", type=int)
    else:
        team_id = current_user.team_id
    if not team_id:
        abort(403)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT t.name
        FROM teams t
        WHERE t.id = %s
        """,
        (team_id,),
    )
    team_row = cursor.fetchone()
    if not team_row:
        conn.close()
        abort(404)
    team_name = team_row["name"]

    cursor.execute(
        "SELECT has_empty_roster_spot FROM teams WHERE id = %s",
        (team_id,),
    )
    team_flags = cursor.fetchone()
    has_empty_roster_spot = bool(team_flags["has_empty_roster_spot"]) if team_flags else False

    cursor.execute("SELECT id, name FROM teams ORDER BY name")
    teams = cursor.fetchall()

    cursor.execute(
        """
        SELECT p.mlb_id, p.name, p.position_name
        FROM team_player tp
        JOIN players p ON p.mlb_id = tp.player_mlb_id
        WHERE tp.team_id = %s
        ORDER BY p.name
        """,
        (team_id,),
    )
    team_players = cursor.fetchall()
    for row in team_players:
        position_name = row["position_name"] or ""
        row["display_position"] = "Pitcher" if position_name == "Pitcher" else "Hitter"

    cursor.execute(
        """
        SELECT p.mlb_id, p.name, p.position_name
        FROM players p
        LEFT JOIN team_player tp ON tp.player_mlb_id = p.mlb_id
        WHERE p.is_active = 1 AND tp.player_mlb_id IS NULL
        ORDER BY p.name
        """
    )
    available_players = cursor.fetchall()
    for row in available_players:
        position_name = row["position_name"] or ""
        row["display_position"] = "Pitcher" if position_name == "Pitcher" else "Hitter"

    error = None
    success = None
    if request.method == "POST":
        drop_player_id = request.form.get("drop_player_id", type=int)
        choice_map = {}
        for key, value in request.form.items():
            if not key.startswith("choice_") or not value:
                continue
            try:
                player_id = int(key.split("_", 1)[1])
            except ValueError:
                continue
            choice_map[int(value)] = player_id

        if not drop_player_id and not has_empty_roster_spot:
            error = "Select a player to drop."
        elif drop_player_id and drop_player_id not in {row["mlb_id"] for row in team_players}:
            error = "Selected drop player is not on your team."
        elif not choice_map:
            error = "Select at least one add player."
        elif not set(choice_map.values()).issubset({row["mlb_id"] for row in available_players}):
            error = "Selected add player is not available."
        else:
            try:
                set_audit_user_id(conn, current_user.id)
                if current_user.role == "owner":
                    submitted_at = datetime.now(EASTERN_TZ).replace(tzinfo=None)
                    week_start = submitted_at.date() - timedelta(days=submitted_at.date().weekday())
                    week_start_dt = datetime.combine(week_start, datetime.min.time())
                    week_end_dt = week_start_dt + timedelta(days=7)
                    cursor.execute(
                        """
                        SELECT COUNT(*) AS count
                        FROM roster_move_requests
                        WHERE team_id = %s
                          AND submitted >= %s
                          AND submitted < %s
                        """,
                        (team_id, week_start_dt, week_end_dt),
                    )
                    if cursor.fetchone()["count"] >= 50:
                        error = "You have reached your limit of 50 roster move requests per week."
                if error:
                    conn.rollback()
                else:
                    cursor.execute(
                        """
                        UPDATE roster_move_requests
                        SET status = 'superseded'
                        WHERE team_id = %s AND status = 'pending'
                        """,
                        (team_id,),
                    )
                    submitted_at = datetime.now(EASTERN_TZ).replace(tzinfo=None).isoformat(sep=" ")
                    cursor.execute(
                        """
                        INSERT INTO roster_move_requests (team_id, submitted, status)
                        VALUES (%s, %s, 'pending')
                        RETURNING id
                        """,
                        (team_id, submitted_at),
                    )
                    request_id = cursor.fetchone()["id"]
                    if drop_player_id:
                        cursor.execute(
                            """
                            INSERT INTO roster_move_request_players (roster_move_request_id, player_mlb_id, action)
                            VALUES (%s, %s, 'drop')
                            """,
                            (request_id, drop_player_id),
                        )
                    for priority in sorted(choice_map.keys()):
                        cursor.execute(
                            """
                            INSERT INTO roster_move_request_players (
                                roster_move_request_id,
                                player_mlb_id,
                                action,
                                priority
                            )
                            VALUES (%s, %s, 'add', %s)
                            """,
                            (request_id, choice_map[priority], priority),
                        )
                    conn.commit()
                    success = "Roster move submitted."
            except Exception:
                conn.rollback()
                raise

    conn.close()
    return render_template(
        "roster-move.html",
        team_name=team_name,
        team_players=team_players,
        available_players=available_players,
        error=error,
        success=success,
        has_empty_roster_spot=has_empty_roster_spot,
        teams=teams,
        selected_team_id=team_id,
    )


@app.route("/pending-roster-moves", methods=["GET", "POST"])
@login_required
@owner_or_admin_required
def pending_roster_moves_view():
    if request.method == "POST":
        request_id = request.form.get("request_id", type=int)
        if not request_id:
            abort(400)
        conn = get_connection()
        cursor = conn.cursor()
        if current_user.role == "owner":
            cursor.execute(
                """
                UPDATE roster_move_requests
                SET status = 'superseded'
                WHERE id = %s AND team_id = %s AND status = 'pending'
                """,
                (request_id, current_user.team_id),
            )
        else:
            cursor.execute(
                """
                UPDATE roster_move_requests
                SET status = 'superseded'
                WHERE id = %s AND status = 'pending'
                """,
                (request_id,),
            )
        conn.commit()
        conn.close()
    if current_user.role == "owner" and current_user.team_id:
        team_filter = "AND r.team_id = %s"
        params = [current_user.team_id]
    else:
        team_filter = ""
        params = []
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT r.id, r.team_id, r.submitted, t.name AS team_name
        FROM roster_move_requests r
        JOIN teams t ON t.id = r.team_id
        WHERE r.status = 'pending'
        {team_filter}
        ORDER BY r.submitted DESC
        """,
        params,
    )
    requests = cursor.fetchall()
    request_ids = [row["id"] for row in requests]
    players_by_request = {}
    if request_ids:
        cursor.execute(
            """
            SELECT
                rmp.roster_move_request_id,
                rmp.action,
                rmp.priority,
                p.name AS player_name
            FROM roster_move_request_players rmp
            JOIN players p ON p.mlb_id = rmp.player_mlb_id
            WHERE rmp.roster_move_request_id = ANY(%s)
            ORDER BY rmp.roster_move_request_id, rmp.action, rmp.priority NULLS LAST
            """,
            (request_ids,),
        )
        for row in cursor.fetchall():
            players_by_request.setdefault(row["roster_move_request_id"], []).append(row)
    conn.close()

    for row in requests:
        value = row["submitted"]
        if isinstance(value, datetime):
            row["submitted_display"] = value.strftime("%b %-d, %Y %I:%M %p")
        else:
            row["submitted_display"] = value
        row["players"] = players_by_request.get(row["id"], [])

    return render_template("pending-roster-moves.html", requests=requests)


@app.route("/rules")
def rules_view():
    if not RULES_PATH.exists():
        abort(404)
    rules_text = RULES_PATH.read_text(encoding="utf-8")
    rules_html = markdown.markdown(rules_text, extensions=["extra", "sane_lists"])
    return render_template("rules.html", rules_html=rules_html)


@app.route("/news")
def news_view():
    return render_template("news.html")


if __name__ == "__main__":
    app.run(debug=False)
