"""Refresh from a local network only when the daily public snapshot is stale."""

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen

from publication_watch import SCAN_VERSION


SITE = "https://ttanddd.github.io"
REMOTE = "https://github.com/TTANDDD/ttanddd.github.io.git"
RAW = "https://raw.githubusercontent.com/TTANDDD/ttanddd.github.io/main/data/scholar.json"
BEIJING = timezone(timedelta(hours=8))
FILES = ["data/scholar.json", "data/site.json", "index.html", "zh/index.html"]
ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}


def get_json(url):
    request = Request(url, headers={"User-Agent": "Hailong-Qu-Homepage/1.0"})
    with urlopen(request, timeout=25) as response:
        return json.load(response)


def current(snapshot, today):
    scan = snapshot.get("publication_scan", {})
    return (datetime.fromisoformat(snapshot["checked_at"].replace("Z", "+00:00")).astimezone(BEIJING).date() == today
            and scan.get("version") == SCAN_VERSION and scan.get("checked_at") == snapshot["checked_at"])


def git(cwd, *args):
    command = ["git", "-c", "credential.username=TTANDDD", "-c", "credential.interactive=false", *args]
    subprocess.run(command, cwd=cwd, env=ENV, check=True, timeout=120)


def main():
    today = datetime.now(BEIJING).date()
    snapshot = get_json(RAW + "?day=" + today.isoformat())
    if current(snapshot, today):
        print("Today's Google Scholar update is already in the repository:", snapshot["checked_at"])
        return
    with tempfile.TemporaryDirectory(prefix="academic-scholar-") as temporary:
        workspace = Path(temporary) / "site"
        git(temporary, "clone", "--quiet", "--depth", "1", "--branch", "main", REMOTE, str(workspace))
        snapshot_file = workspace / "data/scholar.json"
        if current(json.loads(snapshot_file.read_text(encoding="utf-8")), today):
            print("The cloud refresh completed before the local check.")
            return
        for script in ["update_scholar.py", "build.py"]:
            subprocess.run([sys.executable, str(workspace / "scripts" / script)], cwd=workspace, check=True, timeout=300)
        refreshed = json.loads(snapshot_file.read_text(encoding="utf-8"))
        if not current(refreshed, today):
            raise RuntimeError("No current verified Scholar snapshot was produced.")
        git(workspace, "add", "--", *FILES)
        git(workspace, "-c", "user.name=Hailong Qu", "-c", "user.email=128963527+TTANDDD@users.noreply.github.com",
            "commit", "-m", "Refresh Scholar citations and public publications from the local fallback")
        git(workspace, "push", "origin", "HEAD:main")
    stamp = refreshed["checked_at"]
    for attempt in range(12):
        live = get_json(SITE + "/data/scholar.json?checked=" + stamp + "&attempt=" + str(attempt))
        if live["checked_at"] == stamp:
            print("Verified the new snapshot on the live site:", stamp)
            return
        time.sleep(5)
    raise RuntimeError("The new snapshot is on main. GitHub Pages has not yet served it.")


if __name__ == "__main__":
    main()
