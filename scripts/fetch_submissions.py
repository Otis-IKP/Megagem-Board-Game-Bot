#!/usr/bin/env python3
"""Pull classmates' submitted bots from the public harness repo into ./harness.

    python3 scripts/fetch_submissions.py

Looks at every pull request on Ryfernandes/megagem-harness and at its main
branch, and copies any bot file that is not already in ./harness into
harness/src/bot_definitions/ (prefixed "pr<N>_" for pull requests). The harness
folder is not committed, so other people's code never enters this repo.

READ each fetched file before running it: it is someone else's code. To test
against one, name it as "bot_definitions.<file>:<Class>" in a line-up, or add
that string to CLASS_BOTS in otis_bots/zoo.py.
"""

import json
import subprocess
import urllib.request
from pathlib import Path

REPO = "Ryfernandes/megagem-harness"
HARNESS = Path(__file__).resolve().parents[1] / "harness"
BOT_DIR = "src/bot_definitions"
SKIP = {"__init__.py", "small_bid_bot.py"}


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(HARNESS), *args], check=True, capture_output=True, text=True
    ).stdout


def bot_files(ref: str) -> list[str]:
    listing = git("ls-tree", "--name-only", f"{ref}:{BOT_DIR}").split()
    return [f for f in listing if f.endswith(".py") and f not in SKIP]


def save(ref: str, name: str, prefix: str) -> None:
    target = HARNESS / BOT_DIR / f"{prefix}{name}"
    text = git("show", f"{ref}:{BOT_DIR}/{name}")
    if target.exists() and target.read_text() == text:
        return
    target.write_text(text)
    print(f"  fetched {target.relative_to(HARNESS.parent)}  <- read before running")


def main() -> int:
    if not HARNESS.is_dir():
        print("Run scripts/setup_harness.sh first.")
        return 1
    git("fetch", "-q", "origin")
    found = 0
    print("main branch:")
    for name in bot_files("origin/main"):
        save("origin/main", name, "")
        found += 1
    url = f"https://api.github.com/repos/{REPO}/pulls?state=all&per_page=100"
    with urllib.request.urlopen(url, timeout=30) as reply:
        pulls = json.load(reply)
    print(f"pull requests: {len(pulls)}")
    for pr in pulls:
        number = pr["number"]
        print(f" #{number} {pr['state']} by {pr['user']['login']}: {pr['title']}")
        git("fetch", "-q", "origin", f"pull/{number}/head")
        for name in bot_files("FETCH_HEAD"):
            save("FETCH_HEAD", name, f"pr{number}_")
            found += 1
    print(f"{found} submitted bot file(s) found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
