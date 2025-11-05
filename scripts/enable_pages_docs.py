#!/usr/bin/env python3
"""
Enable GitHub Pages for the repository using the legacy branch+path source
so that the site serves directly from `main` branch's `docs/` directory.

This is useful when Actions-based Pages isn't yet enabled and the site
returns 404. After enabling, GitHub will build and publish the site
from `docs/` automatically.

Reads GitHub PAT from `.github/workflows/github_PAT.csv` (first row, second
column), same as other helper scripts in this repo.
"""

import csv
import json
import os
import sys
from typing import Optional

import urllib.request


OWNER = "EricZhou-math"
REPO = "ZHL"

TOKEN_CSV = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    ".github",
    "workflows",
    "github_PAT.csv",
)

API_BASE = "https://api.github.com"


def read_token_from_csv(csv_path: str) -> Optional[str]:
    if not os.path.exists(csv_path):
        return None
    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            # Expect at least two columns: key, token
            if len(row) >= 2 and row[1].strip():
                return row[1].strip()
            break
    return None


def request(method: str, url: str, token: str, data: Optional[dict] = None):
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "TraeAI-Client",
    }
    payload = None
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        return e.code, body


def main():
    token = read_token_from_csv(TOKEN_CSV)
    if not token:
        print("ERROR: Missing PAT. Please place token in .github/workflows/github_PAT.csv")
        sys.exit(1)

    pages_url = f"{API_BASE}/repos/{OWNER}/{REPO}/pages"

    # 1) Check current Pages status
    status, body = request("GET", pages_url, token)
    if status == 200:
        print("Pages is already enabled:")
        print(body)
        sys.exit(0)
    elif status == 404:
        print("Pages not enabled yet. Attempting to enable from main/docs …")
    else:
        print(f"Unexpected status when checking Pages: {status}\n{body}")

    # 2) Enable Pages using docs folder on main
    data = {
        "source": {
            "branch": "main",
            "path": "/docs",
        }
    }

    status, body = request("POST", pages_url, token, data)
    print(f"Create Pages response: {status}")
    print(body)

    # If already exists, try updating the source
    if status == 409:
        print("Pages already exists. Trying to update source to main/docs …")
        status, body = request("PUT", pages_url, token, data)
        print(f"Update Pages response: {status}")
        print(body)

    # 3) Show final status
    status, body = request("GET", pages_url, token)
    print(f"Final Pages status: {status}")
    print(body)


if __name__ == "__main__":
    main()