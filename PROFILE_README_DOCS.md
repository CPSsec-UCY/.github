# CPSEC Organization Profile README

This repository provides the GitHub organization profile for CPSEC-UCY.

## Layout

- `profile/README.md` — rendered on the organization homepage.
- `.github/leaderboard-members.txt` — GitHub logins included in the leaderboard.
- `.github/scripts/update_leaderboard.py` — computes streak and commit metrics and rewrites the leaderboard block.
- `.github/workflows/leaderboard.yml` — refreshes the leaderboard daily and on relevant changes.

## Contribution leaderboard

The leaderboard is generated from GitHub contribution telemetry for the trailing 365 days. It
reports commits per day, total commits, current streak, longest streak, and a status flag.

### Refresh locally

```bash
LEADERBOARD_TOKEN="$(gh auth token)" python3 .github/scripts/update_leaderboard.py
```

The script replaces everything between `<!-- LEADERBOARD:START -->` and
`<!-- LEADERBOARD:END -->` in `profile/README.md`.

### Automated refresh

`.github/workflows/leaderboard.yml` runs:

- daily at `03:17 UTC`
- on manual `workflow_dispatch`
- when the script, member list, or workflow changes on `main`

The workflow commits the regenerated README with `github-actions[bot]`.

### Members and tokens

Edit `.github/leaderboard-members.txt` to add or remove people. If the file is missing or empty,
the script falls back to the organization's public members via the GitHub API.

The workflow uses `GITHUB_TOKEN` by default. If the organization requires elevated access to read
member data, add an `ORG_READ_TOKEN` secret with the appropriate scope.

### Notes

- Private contributions are not visible to the workflow token and may be undercounted.
- Streaks count consecutive days with at least one contribution.
- If `main` is protected, allow the GitHub Actions bot to push or run the workflow from a branch
  and open a pull request instead.
