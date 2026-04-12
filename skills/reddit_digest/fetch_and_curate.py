"""
Função: Buscar os principais posts dos subreddits de IA e organizar um digest personalizado
Usar quando: É necessário entregar um resumo diário dos melhores posts de IA do Reddit, considerando preferências do usuário
ENV_VARS: Nenhuma obrigatória
DB_TABLES: reddit_digest, reddit_preferences (memória separada)
"""

from typing import List, Dict
import requests
import json
import os

SUBREDDITS = [
    "ArtificalIntelligence",
    "ClaudeAI",
    "CursorAI",
    "OpenAI",
    "OpenClawUseCases"
]

MEMORY_FILE = "memory/reddit_preferences.json"

USER_RULES = ["do not include memes"]  # Inicial, será atualizado conforme feedback

HEADERS = {"User-Agent": "OpenClawRedditDigest/1.0"}


def fetch_top_posts(subreddit: str, limit: int = 5) -> List[Dict]:
    url = f"https://www.reddit.com/r/{subreddit}/top.json?t=day&limit={limit}"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    posts = []
    for child in data.get("data", {}).get("children", []):
        post = child["data"]
        if not any(rule in post.get("title", "").lower() for rule in USER_RULES):
            posts.append({
                "subreddit": subreddit,
                "title": post.get("title"),
                "url": f"https://reddit.com{post.get('permalink')}",
                "score": post.get("score"),
                "author": post.get("author"),
                "created_utc": post.get("created_utc"),
                "num_comments": post.get("num_comments"),
                "is_self": post.get("is_self"),
                "stickied": post.get("stickied"),
            })
    return posts

def load_preferences() -> Dict:
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"rules": USER_RULES}

def save_preferences(prefs: Dict):
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(prefs, f, ensure_ascii=False, indent=2)

def curate_digest(posts: List[Dict], prefs: Dict) -> List[Dict]:
    # Exemplo: filtra posts conforme prefs['rules']
    rules = prefs.get("rules", [])
    digest = []
    for post in posts:
        if not any(rule in post["title"].lower() for rule in rules):
            digest.append(post)
    return digest

def ask_feedback():
    print("Você gostou do digest de hoje? (sim/não)")
    feedback = input().strip().lower()
    prefs = load_preferences()
    if feedback == "não":
        print("Descreva o que não gostou (ex: 'memes', 'muito técnico', etc):")
        motivo = input().strip().lower()
        if motivo and motivo not in prefs["rules"]:
            prefs["rules"].append(motivo)
            save_preferences(prefs)
            print(f"Regra '{motivo}' adicionada para curadoria futura.")
    else:
        print("Obrigado pelo feedback!")

def run():
    prefs = load_preferences()
    all_posts = []
    for subreddit in SUBREDDITS:
        posts = fetch_top_posts(subreddit)
        all_posts.extend(posts)
    digest = curate_digest(all_posts, prefs)
    print("--- Reddit Digest ---")
    for post in digest:
        print(f"[{post['subreddit']}] {post['title']} (Score: {post['score']})\n{post['url']}\n")
    ask_feedback()

if __name__ == "__main__":
    run()
