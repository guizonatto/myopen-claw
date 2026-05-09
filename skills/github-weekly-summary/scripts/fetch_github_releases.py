"""
Script: fetch_github_releases.py
Função: Busca releases e commits da última semana nos repositórios configurados via GitHub API
Usar quando: Coleta semanal de dados do GitHub para o pipeline github-weekly-summary

ENV_VARS:
  - GITHUB_TOKEN: token pessoal do GitHub com acesso de leitura aos repositórios
  - GITHUB_REPO: lista de repositórios separados por vírgula (ex: org1/repo1,org2/repo2)

DB_TABLES:
  - (nenhuma)
"""

import os
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPOS = [r.strip() for r in os.environ.get("GITHUB_REPO", "").split(",") if r.strip()]

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

ONE_WEEK_AGO = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()


def _get(url, params=None):
    resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _fetch_releases(repo):
    releases = []
    page = 1
    while True:
        data = _get(f"https://api.github.com/repos/{repo}/releases", params={"per_page": 50, "page": page})
        if not data:
            break
        for r in data:
            published = r.get("published_at") or ""
            if published < ONE_WEEK_AGO:
                return releases
            releases.append({
                "repo": repo,
                "tag": r.get("tag_name"),
                "name": r.get("name"),
                "body": r.get("body", ""),
                "published_at": published,
                "url": r.get("html_url"),
                "author": (r.get("author") or {}).get("login"),
            })
        page += 1
    return releases


def _fetch_commits(repo):
    commits = []
    try:
        branches_data = _get(f"https://api.github.com/repos/{repo}/branches")
        branches = [b["name"] for b in branches_data]
    except Exception:
        branches = ["main", "master"]

    seen = set()
    for branch in branches:
        page = 1
        while True:
            try:
                data = _get(
                    f"https://api.github.com/repos/{repo}/commits",
                    params={"sha": branch, "since": ONE_WEEK_AGO, "per_page": 50, "page": page},
                )
            except Exception:
                break
            if not data:
                break
            for c in data:
                sha = c.get("sha")
                if sha in seen:
                    continue
                seen.add(sha)
                commit_info = c.get("commit", {})
                commits.append({
                    "repo": repo,
                    "branch": branch,
                    "sha": sha[:8] if sha else "",
                    "message": (commit_info.get("message") or "").split("\n")[0],
                    "author": (commit_info.get("author") or {}).get("name"),
                    "date": (commit_info.get("author") or {}).get("date"),
                    "url": c.get("html_url", ""),
                })
            page += 1

    return commits


def fetch_weekly_releases_and_commits():
    all_releases = []
    all_commits = []
    for repo in GITHUB_REPOS:
        try:
            all_releases.extend(_fetch_releases(repo))
        except Exception as e:
            print(f"[WARN] Releases do repositório {repo}: {e}")
        try:
            all_commits.extend(_fetch_commits(repo))
        except Exception as e:
            print(f"[WARN] Commits do repositório {repo}: {e}")
    return {"releases": all_releases, "commits": all_commits}


if __name__ == "__main__":
    import json
    data = fetch_weekly_releases_and_commits()
    print(f"Releases: {len(data['releases'])}, Commits: {len(data['commits'])}")
    print(json.dumps(data, indent=2, ensure_ascii=False))
