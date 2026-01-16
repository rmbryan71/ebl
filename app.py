from collections import defaultdict, deque
from datetime import date, datetime, timedelta
import os
from pathlib import Path
import subprocess
import sys
from functools import wraps
import time

from flask import Flask, abort, redirect, render_template, request
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.security import check_password_hash

from db import get_connection

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

RATE_LIMITS = {
    "default": (120, 60),
    "audit": (30, 60),
}
REQUEST_HISTORY = defaultdict(deque)
ENFORCE_HTTPS = os.getenv("FORCE_HTTPS", "").lower() in {"1", "true", "yes"}
AUTO_BUILD_NEWS = os.getenv("AUTO_BUILD_NEWS", "").lower() in {"1", "true", "yes"}

RULES_CHANGELOG = [
    {
        "date": "January 13, 2026",
        "version": "1.00",
        "items": [
            "Removes the comms plan, tech plan, roadmap, and lists.",
            "Removes the privacy and audit trail requirements.",
            "Fixes pitching scoring to outs, not innings pitched.",
            "Clarifies scoring for ties of zero stats.",
            "Simplifies the wording for scoring.",
            "Adds link to the live prototype.",
        ],
    },
    {
        "date": "January 10, 2026",
        "version": "0.04",
        "items": [
            "Overhauls wording throughout.",
            "Updates formatting for readability.",
            "Adds 40-man roster requirement.",
        ],
    },
    {
        "date": "January 9, 2026",
        "version": "0.04",
        "items": [
            "Overhaul, move to web.",
            "Removes implementation section to tech plan.",
            "Removes irrelevant conversational tangents.",
            "Removes communications plan to comms plan.",
        ],
    },
    {
        "date": "January 8, 2026",
        "version": "0.03",
        "items": [
            "Overhauls the auction.",
            "Removes unhelpful strategy note from roster section.",
            "Adds special case to roster move processing order.",
            "Clarifies how empty roster spots can happen.",
            "Specifies lack of remedy for injuries or suspensions.",
        ],
    },
    {
        "date": "January 7, 2026",
        "version": "0.02",
        "items": [
            "Adds stolen bases to offense.",
            "Changes auction order to nominations.",
            "Specifies whole dollar amounts for bids.",
            "Overhauls ties.",
            "Adds missing headings.",
            "Adds future features section.",
            "Changes roster moves from daily to weekly.",
            "Specifies that ties during roster moves are handled randomly.",
            "Adds note about documentation to implementation section.",
            "Adds privacy requirement to implementation section.",
            "Adds audit trail requirement to implementation section.",
            "Adds communication plan to implementation section.",
        ],
    },
    {
        "date": "January 6, 2026",
        "version": "0.01",
        "items": ["Initial release."],
    },
]

RULES_SECTIONS = [
    {
        "title": "Introduction",
        "items": [
            "Phillies players only.",
            "A live auction for players.",
            "Scores tallied weekly.",
        ],
    },
    {
        "title": "General Rules",
        "items": [
            "Participation is free, and there is no prize money.",
            "There are 8 teams in our league.",
            "Each team has 4 roster spots.",
            "Pitching is measured by Outs.",
            "Offense is measured by the sum of Total Bases + Walks + HBP + Steals.",
        ],
    },
    {
        "title": "Scoring",
        "items": [
            "Each week, teams earn points in pitching and offense: 1st place gets 10 points, 2nd gets 8, and 3rd gets 4.",
            "Partial weeks at the beginning of the year, the all-star break, and the end of the year all get the same points awarded as full weeks.",
            "If a pitcher gets on base, that counts as offense.",
            "If a hitter gets pitching outs, those count.",
        ],
    },
    {
        "title": "Ties",
        "items": [
            "All teams tied for a position get all the points for that spot as if there were no tie.",
            "No points are awarded for second place if two teams tie for first place.",
            "No points are awarded for third place if two or more teams tie for second place.",
            "If there is a three-way tie for first place, all three teams get first place points, and there are no other points awarded.",
            "If there is a six-way tie for third, all six teams get third place points.",
            "If only one team records any offense/pitching in a week, they get 10 points. Nobody else gets any points. No points are awarded for second or third place if everyone ties at zero.",
        ],
    },
    {
        "title": "Rosters",
        "items": [
            "Only players on the Phillies 40-man roster can be on teams in our league.",
            "If a player on your team gets traded away from the Phillies, retires, dies, gets picked up by another team on waivers, or leaves the organization for any reason, you have an empty roster spot to fill.",
            "There is specifically no remedy for suspensions or injuries. Those do not create empty roster spots.",
            "You do not have to fill empty roster spots immediately, or ever.",
            "Only major league production counts.",
            "If you have a player that gets sent down or called up, you do not have to do anything.",
            "If you want all pitchers, all hitters, or any mix of hitters and pitchers, that is fine.",
        ],
    },
    {
        "title": "Roster Moves",
        "items": [
            "You can make a maximum of 1 roster move attempt per week.",
            "Even if you have more than one open roster spot, you only get one roster move attempt per week.",
            "Roster moves happen Sunday night after points are awarded.",
            "Your roster move attempt includes the name of the player you want to drop and the name of the player you want to add.",
            "You cannot submit a roster move for a player on another team in our league in the hope that the player gets dropped before your turn in the roster move process.",
            "Teams with empty roster spots go first in the roster move process. If more than one team has an empty roster spot, the lower-ranking teams go first.",
            "Aside from teams with empty roster spots, roster move attempts are processed in reverse order of the current league standings. In the case of ties in the league standings, roster move attempts will happen between the tied franchises randomly.",
            "If the player you attempt to add is not available when it comes to your turn in the roster moves process, nothing happens. You do not lose the player you tried to drop. You can try again next week.",
            "When the Phillies add a player, they become available at the end of week they are acquired.",
            "If there is a tie in the standings and two teams try to acquire the same player, the player is assigned randomly.",
            "There is no trading players between teams.",
        ],
    },
    {
        "title": "The Auction",
        "items": [
            "This will be a Zoom call at 6:00 PM on Sunday, March 22, 2026.",
            "Every team gets $100 to field their team.",
            "All bids are whole-dollar values, no pennies.",
            "You must fill all 4 roster spots on your team during the auction.",
            "Owners will nominate players to be auctioned.",
            "When you nominate a player, you automatically start the bidding for that player at $1.",
            "You must save enough money to be able to fill all your roster spots. You cannot spend all your money without filling all of your roster spots.",
            "When it is your turn to nominate, you just say what player you want to come up for auction next.",
            "Owners will nominate in a random order that is not decided until the auction starts.",
            "At the end of each player auction, we will know which team in our league that player is on and how much the owner paid for them.",
            "If you have extra money left over at the end of the auction, that is fine, it was not really money anyway.",
            "We will have exactly 32 auctions.",
            "If an auction starts with two owners simultaneously bidding $97 for a player, the older owner gets the player.",
            "Otherwise, it is an open auction, so owners just shout out how much they are willing to pay and that is the going price.",
            "Ownership of players is for the 2026 season only.",
        ],
    },
]


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
    if os.getenv("RENDER") or os.getenv("RENDER_SERVICE_ID") or os.getenv("RENDER_INSTANCE_ID"):
        return False
    return AUTO_BUILD_NEWS or os.getenv("FLASK_ENV") == "development"


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
            p.id AS player_id,
            p.name,
            p.position_name,
            p.is_active
        FROM players p
        LEFT JOIN team_player tp ON tp.player_id = p.id
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
            p.id AS player_id,
            p.name AS player_name
        FROM stats s
        JOIN players p ON p.id = s.player_id
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
            p.id AS player_id,
            p.name AS player_name,
            COALESCE(SUM(s.offense), 0) AS total_offense,
            COALESCE(SUM(s.pitching), 0) AS total_pitching
        FROM team_player tp
        JOIN players p ON p.id = tp.player_id
        LEFT JOIN stats s
            ON s.player_id = p.id AND s.team_id = tp.team_id
        WHERE tp.team_id = %s
        GROUP BY p.id
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
    show_roster_move = (
        current_user.is_authenticated
        and current_user.role == "owner"
        and current_user.team_id == selected_team_id
    )
    return render_template(
        "team-stats.html",
        teams=teams,
        selected_team_id=selected_team_id,
        selected_team_name=selected_team_name,
        rows=rows,
        totals=totals,
        player_totals=player_totals,
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
    date_filter = ""
    selected_week_end = None
    if selected_week_start:
        selected_week_end = selected_week_start + timedelta(days=6)
        date_filter = "WHERE s.date BETWEEN %s AND %s"
        params.extend([selected_week_start.isoformat(), selected_week_end.isoformat()])

    cursor.execute(
        f"""
        SELECT
            t.id AS team_id,
            t.name AS team_name,
            SUM(s.offense) AS total_offense
        FROM stats s
        JOIN teams t ON t.id = s.team_id
        {date_filter}
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
            SUM(s.pitching) AS total_pitching
        FROM stats s
        JOIN teams t ON t.id = s.team_id
        {date_filter}
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
            p.id,
            p.name,
            p.birth_date,
            p.position_name,
            t.id AS team_id,
            t.name AS team_name
        FROM players p
        LEFT JOIN team_player tp ON tp.player_id = p.id
        LEFT JOIN teams t ON t.id = tp.team_id
        WHERE p.id = %s
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
        "SELECT MIN(date) AS first_date FROM stats WHERE player_id = %s",
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
            WHERE player_id = %s AND date::text LIKE %s
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
            SUM(CASE WHEN p.type = 'offense' THEN p.value ELSE 0 END) AS offense_points,
            SUM(CASE WHEN p.type = 'defense' THEN p.value ELSE 0 END) AS pitching_points,
            SUM(p.value) AS total_points
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
            p.id,
            p.name,
            p.position_name,
            p.birth_date
        FROM players p
        LEFT JOIN team_player tp ON tp.player_id = p.id
        WHERE p.is_active = 1 AND tp.player_id IS NULL
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


@app.route("/roster-move")
@login_required
@owner_or_admin_required
def roster_move_view():
    return render_template("roster-move.html")


@app.route("/rules")
def rules_view():
    return render_template(
        "rules.html",
        changelog=RULES_CHANGELOG,
        sections=RULES_SECTIONS,
    )


@app.route("/news")
def news_view():
    return render_template("news.html")


if __name__ == "__main__":
    app.run(debug=False)
