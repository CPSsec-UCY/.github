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
        f"`telemetry window: trailing {WINDOW_DAYS} days` · `snapshot: {snapshot}` · `scope: CPSEC-UCY operators`",
        "",
        "| RANK | OPERATIVE | COMMITS / DAY | TOTAL COMMITS | CURRENT STREAK | LONGEST STREAK | STATUS |",
        "|:----:|:----------|--------------:|--------------:|---------------:|---------------:|:-------|",
    ]

    for rank, item in enumerate(metrics, start=1):
        if rank == 1:
            status = "LEAD"
        elif item["current_streak"] > 0:
            status = "ACTIVE"
        else:
            status = "IDLE"
        lines.append(
            f"| {rank:02d} | [@{item['login']}](https://github.com/{item['login']}) "
            f"| {item['commits_per_day']:.2f} | {item['total_commits']:,} "
            f"| {item['current_streak']} | {item['longest_streak']} | `{status}` |"
        )

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
            "",
            f"> `VELOCITY LEADER` → **@{velocity['login']}** · {velocity['commits_per_day']:.2f} commits/day  ",
            f"> `STREAK LEADER` → **@{streak['login']}** · {streak_text}",
            "",
            "<sub>Metrics are computed from public contribution telemetry over the last 365 days. Private",
            "contributions may be undercounted. Streaks count consecutive days with at least one commit.</sub>",
            END,
        ]
    )
    return "\n".join(lines)


def main():
    members = read_members()
    metrics = []
    for login in members:
        item = fetch_metrics(login)
        if item:
            metrics.append(item)

    if not metrics:
        raise RuntimeError("No contribution metrics could be collected.")

    snapshot = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    block = render(metrics, snapshot)
    text = README.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)

    if not pattern.search(text):
        raise RuntimeError(f"Leaderboard markers not found in {README}")

    updated = pattern.sub(lambda _: block, text)
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
