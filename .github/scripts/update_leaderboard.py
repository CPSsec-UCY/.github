#!/usr/bin/env python3
"""Regenerate the CPSEC-UCY contribution leaderboard in profile/README.md."""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = Path(os.environ.get("README_PATH", ROOT / "profile/README.md"))
MEMBERS_FILE = Path(
    os.environ.get("MEMBERS_FILE", ROOT / ".github" / "leaderboard-members.txt")
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
    }


def status_for(rank, item):
    if rank == 1:
        return "LEAD", "00FF41"
    if item["current_streak"] > 0:
        return "ACTIVE", "00CC33"
    return "IDLE", "8B949E"


def render_card(item, rank):
    login = item["login"]
    status, status_color = status_for(rank, item)
    rank_color = {1: "FFD700", 2: "C0C0C0", 3: "CD7F32"}.get(rank, "00FF41")
    avatar_size = 112 if rank <= 3 else 88
    return f"""<td align="center" width="33%">
<a href="https://github.com/{login}"><img src="https://github.com/{login}.png?size=160" width="{avatar_size}" height="{avatar_size}" alt="{login}" /></a>
<br/>
<img src="https://img.shields.io/badge/RANK-{rank:02d}-{rank_color}?style=for-the-badge&amp;labelColor=0d1117" alt="rank {rank}" />
<br/>
<b><a href="https://github.com/{login}">@{login}</a></b>
<br/>
<img src="https://img.shields.io/badge/COMMITS%2FDAY-{item['commits_per_day']:.2f}-00FF41?style=flat-square&amp;labelColor=0d1117" alt="commits per day" />
<img src="https://img.shields.io/badge/TOTAL-{item['total_commits']:,}-00FF41?style=flat-square&amp;labelColor=0d1117" alt="total commits" />
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
        '<img src="https://img.shields.io/badge/TELEMETRY-TRAILING_365_DAYS-00FF41?style=for-the-badge&amp;labelColor=0d1117" alt="telemetry window" />',
        f'<img src="https://img.shields.io/badge/SNAPSHOT-{snapshot.replace("-", "--")}-00FF41?style=for-the-badge&amp;labelColor=0d1117" alt="snapshot date" />',
        f'<img src="https://img.shields.io/badge/OPERATORS-{len(metrics)}-00FF41?style=for-the-badge&amp;labelColor=0d1117" alt="operator count" />',
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


def render_activity(metrics):
    top = metrics[0]
    login = top["login"]
    return "\n".join(
        [
            ACTIVITY_START,
            '<div align="center">',
            "",
            f'<img src="https://github-readme-activity-graph.vercel.app/graph?username={login}&amp;theme=react-dark&amp;bg_color=0d1117&amp;color=00ff41&amp;line=00ff41&amp;point=ffffff&amp;area=true&amp;hide_border=true" width="100%" alt="Contribution activity for @{login}" />',
            "",
            f'<sub>Activity graph · top operator <a href="https://github.com/{login}">@{login}</a></sub>',
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
    activity = render_activity(metrics)
    text = README.read_text(encoding="utf-8")

    updated = replace_marked(text, START, END, block)
    updated = replace_marked(updated, ACTIVITY_START, ACTIVITY_END, activity)
    if updated == text:
        print("Leaderboard already up to date.")
        return

    README.write_text(updated, encoding="utf-8")
    print(f"Updated leaderboard for {len(metrics)} members in {README}.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
