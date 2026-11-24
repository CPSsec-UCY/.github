#!/usr/bin/env python3
"""Regenerate the CPSEC-UCY contribution leaderboard in profile/README.md."""

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = Path(os.environ.get("README_PATH", ROOT / "profile/README.md"))
MEMBERS_FILE = Path(
    os.environ.get("MEMBERS_FILE", ROOT / ".github" / "leaderboard-members.txt")
)
ACTIVITY_SVG = Path(
    os.environ.get("ACTIVITY_SVG", ROOT / "profile" / "assets" / "combined-activity.svg")
)
START = "<!-- LEADERBOARD:START -->"
END = "<!-- LEADERBOARD:END -->"
ACTIVITY_START = "<!-- ACTIVITY:START -->"
ACTIVITY_END = "<!-- ACTIVITY:END -->"
WINDOW_DAYS = 365
API = "https://api.github.com"
GRAPHQL = f"{API}/graphql"
TOKEN = os.environ.get("LEADERBOARD_TOKEN") or os.environ.get("GITHUB_TOKEN")

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      contributionCalendar {
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""


def http_json(url, payload=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "cpsec-leaderboard",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")
        raise RuntimeError(f"{url} returned {error.code}: {body}") from error


def read_members():
    if MEMBERS_FILE.exists():
        members = [
            line.strip()
            for line in MEMBERS_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        if members:
            return members

    repo = os.environ.get("GITHUB_REPOSITORY", "CPSsec-UCY/.github")
    org = os.environ.get("ORG") or repo.split("/")[0]
    data = http_json(f"{API}/orgs/{org}/public_members?per_page=100")
    members = [user["login"] for user in data]
    if not members:
        raise RuntimeError(
            f"No members found for {org}. Populate {MEMBERS_FILE} with GitHub logins."
        )
    return members


def fetch_metrics(login):
    payload = http_json(GRAPHQL, {"query": QUERY, "variables": {"login": login}})
    if payload.get("errors"):
        raise RuntimeError(f"GraphQL error for {login}: {payload['errors']}")

    user = payload.get("data", {}).get("user")
    if not user:
        print(f"warning: GitHub user not found, skipping: {login}", file=sys.stderr)
        return None

    collection = user["contributionsCollection"]
    days = [
        day
        for week in collection["contributionCalendar"]["weeks"]
        for day in week["contributionDays"]
    ]
    counts = [day["contributionCount"] for day in days]
    total_commits = collection.get("totalCommitContributions") or 0

    longest = run = 0
    for count in counts:
        if count > 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0

    index = len(counts) - 1
    if index >= 0 and counts[index] == 0:
        index -= 1
    current = 0
    while index >= 0 and counts[index] > 0:
        current += 1
        index -= 1

    return {
        "login": login,
        "total_commits": total_commits,
        "commits_per_day": total_commits / WINDOW_DAYS,
        "current_streak": current,
        "longest_streak": longest,
        "days": [(day["date"], day["contributionCount"]) for day in days],
    }


def status_for(rank, item):
    if rank == 1:
        return "LEAD", "7ee787"
    if item["current_streak"] > 0:
        return "ACTIVE", "7ee787"
    return "IDLE", "30363d"


def render_card(item, rank):
    login = item["login"]
    status, status_color = status_for(rank, item)
    rank_color = {1: "FFD700", 2: "C0C0C0", 3: "e0a96d"}.get(rank, "7ee787")
    avatar_size = 112 if rank <= 3 else 88
    return f"""<td align="center" width="33%">
<a href="https://github.com/{login}"><img src="https://github.com/{login}.png?size=160" width="{avatar_size}" height="{avatar_size}" alt="{login}" /></a>
<br/>
<img src="https://img.shields.io/badge/RANK-{rank:02d}-{rank_color}?style=for-the-badge&amp;labelColor=0d1117" alt="rank {rank}" />
<br/>
<b><a href="https://github.com/{login}">@{login}</a></b>
<br/>
<img src="https://img.shields.io/badge/COMMITS%2FDAY-{item['commits_per_day']:.2f}-7ee787?style=flat-square&amp;labelColor=0d1117" alt="commits per day" />
<img src="https://img.shields.io/badge/TOTAL-{item['total_commits']:,}-7ee787?style=flat-square&amp;labelColor=0d1117" alt="total commits" />
<br/>
<img src="https://img.shields.io/badge/STREAK-{item['current_streak']}d-{status_color}?style=flat-square&amp;labelColor=0d1117" alt="current streak" />
<img src="https://img.shields.io/badge/BEST-{item['longest_streak']}d-{status_color}?style=flat-square&amp;labelColor=0d1117" alt="longest streak" />
<br/>
<sub><code>{status}</code></sub>
</td>"""


def render(metrics, snapshot):
    metrics.sort(
        key=lambda item: (
            -item["commits_per_day"],
            -item["longest_streak"],
            -item["current_streak"],
            item["login"].lower(),
        )
    )

    lines = [
        START,
        '<div align="center">',
        "",
        '<img src="https://img.shields.io/badge/TELEMETRY-TRAILING_365_DAYS-7ee787?style=for-the-badge&amp;labelColor=0d1117" alt="telemetry window" />',
        f'<img src="https://img.shields.io/badge/SNAPSHOT-{snapshot.replace("-", "--")}-7ee787?style=for-the-badge&amp;labelColor=0d1117" alt="snapshot date" />',
        f'<img src="https://img.shields.io/badge/OPERATORS-{len(metrics)}-7ee787?style=for-the-badge&amp;labelColor=0d1117" alt="operator count" />',
        "",
        "<table>",
    ]

    for start in range(0, len(metrics), 3):
        chunk = metrics[start : start + 3]
        lines.append("<tr>")
        if len(chunk) == 1:
            lines.append('<td width="33%"></td>')
        for offset, item in enumerate(chunk, start=start + 1):
            lines.append(render_card(item, offset))
        if len(chunk) < 3:
            lines.append('<td width="33%"></td>')
        lines.append("</tr>")

    velocity = metrics[0]
    streak = max(
        metrics,
        key=lambda item: (
            item["current_streak"],
            item["longest_streak"],
            item["total_commits"],
        ),
    )
    if streak["current_streak"] > 0:
        streak_text = f"{streak['current_streak']}-day active streak"
    else:
        streak_text = f"{streak['longest_streak']}-day longest streak"

    lines.extend(
        [
            "</table>",
            "",
            f'<p><b>VELOCITY LEADER</b> &rarr; <a href="https://github.com/{velocity["login"]}">@{velocity["login"]}</a> · {velocity["commits_per_day"]:.2f} commits/day<br/>',
            f'<b>STREAK LEADER</b> &rarr; <a href="https://github.com/{streak["login"]}">@{streak["login"]}</a> · {streak_text}</p>',
            "",
            "<sub>Metrics are computed from public contribution telemetry over the last 365 days. Private",
            "contributions may be undercounted. Streaks count consecutive days with at least one commit.",
            "Operators with no commits in the window are hidden.</sub>",
            "</div>",
            END,
        ]
    )
    return "\n".join(lines)


LEVEL_COLORS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]


def activity_level(count, peak):
    if count <= 0:
        return 0
    ratio = count / peak
    if ratio >= 0.75:
        return 4
    if ratio >= 0.5:
        return 3
    if ratio >= 0.25:
        return 2
    return 1


def render_activity(metrics, raw_url):
    daily = defaultdict(int)
    for item in metrics:
        for day, count in item["days"]:
            daily[day] += count

    if not daily:
        return None

    end = date.fromisoformat(max(daily))
    start = end - timedelta(days=364)
    grid_start = start - timedelta(days=(start.weekday() + 1) % 7)
    total_days = (end - grid_start).days + 1
    weeks = (total_days + 6) // 7

    peak = max(daily.values()) or 1
    total = sum(daily.values())
    active = sum(1 for count in daily.values() if count > 0)

    cell = 12
    gap = 3
    step = cell + gap
    left = 56
    top = 74
    right = 24
    bottom = 46
    width = left + weeks * step + right
    height = top + 7 * step + bottom
    font = "JetBrains Mono, Fira Code, monospace"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Combined contribution activity">',
        "<defs>",
        '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0d1117"/><stop offset="1" stop-color="#08110c"/></linearGradient>',
        "</defs>",
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="12" fill="url(#bg)" stroke="#00ff41" stroke-opacity="0.35"/>',
        f'<text x="{left}" y="30" fill="#00ff41" font-family="{font}" font-size="16" font-weight="700" letter-spacing="2">COMBINED ACTIVITY</text>',
        f'<text x="{left}" y="50" fill="#8b949e" font-family="{font}" font-size="10" letter-spacing="1">TRAILING 365 DAYS · {len(metrics)} OPERATORS · {total:,} CONTRIBUTIONS · {active} ACTIVE DAYS</text>',
        f'<circle cx="{width - right - 6}" cy="26" r="4" fill="#00ff41"><animate attributeName="opacity" values="0.25;1;0.25" dur="2.4s" repeatCount="indefinite"/></circle>',
    ]

    for row, label in ((1, "MON"), (3, "WED"), (5, "FRI")):
        y = top + row * step + cell - 3
        parts.append(
            f'<text x="{left - 10}" y="{y}" fill="#8b949e" font-family="{font}" font-size="8" text-anchor="end">{label}</text>'
        )

    last_label = -999
    for offset in range(total_days):
        current = grid_start + timedelta(days=offset)
        if current.day == 1 or offset == 0:
            week = offset // 7
            x = left + week * step
            if x - last_label >= 30:
                parts.append(
                    f'<text x="{x}" y="{top - 10}" fill="#8b949e" font-family="{font}" font-size="8">{current.strftime("%b").upper()}</text>'
                )
                last_label = x

    for offset in range(total_days):
        current = grid_start + timedelta(days=offset)
        key = current.isoformat()
        count = daily.get(key, 0)
        week = offset // 7
        row = offset % 7
        x = left + week * step
        y = top + row * step
        parts.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{LEVEL_COLORS[activity_level(count, peak)]}"><title>{key} · {count} contributions</title></rect>'
        )

    scan_end = left + weeks * step
    parts.append(
        f'<rect x="{left}" y="{top}" width="2" height="{7 * step - gap}" fill="#00ff41" opacity="0.10"><animate attributeName="x" from="{left}" to="{scan_end}" dur="9s" repeatCount="indefinite"/></rect>'
    )

    legend_y = height - 24
    legend_x = width - right - 5 * step - 58
    parts.append(
        f'<text x="{legend_x}" y="{legend_y + 9}" fill="#8b949e" font-family="{font}" font-size="8">LESS</text>'
    )
    for index, color in enumerate(LEVEL_COLORS):
        x = legend_x + 34 + index * step
        parts.append(
            f'<rect x="{x}" y="{legend_y}" width="{cell}" height="{cell}" rx="2" fill="{color}"/>'
        )
    parts.append(
        f'<text x="{legend_x + 34 + len(LEVEL_COLORS) * step + 4}" y="{legend_y + 9}" fill="#8b949e" font-family="{font}" font-size="8">MORE</text>'
    )
    parts.append("</svg>")

    svg = "\n".join(parts)
    digest = hashlib.sha256(svg.encode("utf-8")).hexdigest()[:12]
    ACTIVITY_SVG.parent.mkdir(parents=True, exist_ok=True)
    if not ACTIVITY_SVG.exists() or ACTIVITY_SVG.read_text(encoding="utf-8") != svg:
        ACTIVITY_SVG.write_text(svg, encoding="utf-8")

    return "\n".join(
        [
            ACTIVITY_START,
            '<div align="center">',
            "",
            f'<img src="{raw_url}?v={digest}" width="100%" alt="Combined contribution activity across CPSEC-UCY operators" />',
            "",
            f"<sub>Combined public contribution activity · {len(metrics)} operators · trailing 365 days</sub>",
            "</div>",
            ACTIVITY_END,
        ]
    )


def replace_marked(text, start, end, block):
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if not pattern.search(text):
        raise RuntimeError(f"Markers not found: {start} / {end}")
    return pattern.sub(lambda _: block, text)


def main():
    members = read_members()
    metrics = []
    for login in members:
        item = fetch_metrics(login)
        if item and item["total_commits"] > 0:
            metrics.append(item)

    if not metrics:
        raise RuntimeError("No contribution metrics could be collected.")

    snapshot = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    block = render(metrics, snapshot)
    repo = os.environ.get("GITHUB_REPOSITORY", "CPSsec-UCY/.github")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    asset_path = ACTIVITY_SVG.relative_to(ROOT).as_posix()
    raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{asset_path}"
    activity = render_activity(metrics, raw_url)
    if not activity:
        raise RuntimeError("No activity data could be aggregated.")
    text = README.read_text(encoding="utf-8")

    updated = replace_marked(text, START, END, block)
    updated = replace_marked(updated, ACTIVITY_START, ACTIVITY_END, activity)
    if updated == text:
        print("Leaderboard already up to date.")
        return

    README.write_text(updated, encoding="utf-8")
    print(f"Updated leaderboard for {len(metrics)} members and {ACTIVITY_SVG}.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
