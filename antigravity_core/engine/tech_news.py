"""
Tech Affairs Daily — News Engine
Fetches RSS feeds from major tech sources, uses Gemini AI to summarize,
and stores headlines in SQLite for up to 7 days.
"""
import time
import threading
import requests
import sqlite3
import json
import datetime
import xml.etree.ElementTree as ET
import os

# ── RSS Sources ────────────────────────────────────────────────────────────
RSS_FEEDS = [
    {"name": "Hacker News",   "url": "https://news.ycombinator.com/rss", "icon": "🟠"},
    {"name": "The Verge",     "url": "https://www.theverge.com/rss/index.xml", "icon": "🟣"},
    {"name": "TechCrunch",    "url": "https://techcrunch.com/feed/", "icon": "🟢"},
    {"name": "Ars Technica",  "url": "https://feeds.arstechnica.com/arstechnica/index", "icon": "🔵"},
    {"name": "Wired",         "url": "https://www.wired.com/feed/rss", "icon": "⚫"},
]

CORE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("VERCEL") or not os.access(CORE_DIR, os.W_OK):
    DATA_DIR = "/tmp/antigravity_data"
else:
    DATA_DIR = os.path.join(CORE_DIR, "data")

os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "antigravity.db")



SEED_DB_PATH = os.path.join(CORE_DIR, "data", "seed_antigravity.db")

def get_db():
    if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) == 0:
        if os.path.exists(SEED_DB_PATH):
            import shutil
            shutil.copyfile(SEED_DB_PATH, DB_PATH)
            print(f"[News] Initialized antigravity.db from seed: {SEED_DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn



def init_tech_news_table():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tech_news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fetch_date TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            source TEXT,
            url TEXT,
            icon TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def purge_old_news():
    """Delete news older than 7 days."""
    cutoff = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    conn = get_db()
    conn.execute("DELETE FROM tech_news WHERE fetch_date < ?", (cutoff,))
    conn.commit()
    conn.close()


def fetch_rss(url: str, timeout: int = 10) -> list[dict]:
    """Fetch and parse an RSS/Atom feed, return list of {title, link, summary}."""
    articles = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; AntigravityBot/1.0)"}
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        # Handle both RSS and Atom
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        # RSS format
        for item in root.findall(".//item")[:5]:
            title_el = item.find("title")
            link_el  = item.find("link")
            desc_el  = item.find("description")
            if title_el is not None and title_el.text:
                articles.append({
                    "title":   title_el.text.strip(),
                    "url":     link_el.text.strip() if link_el is not None and link_el.text else "",
                    "summary": desc_el.text.strip()[:300] if desc_el is not None and desc_el.text else "",
                })

        # Atom format (if no items found)
        if not articles:
            for entry in root.findall("atom:entry", ns)[:5]:
                title_el = entry.find("atom:title", ns)
                link_el  = entry.find("atom:link", ns)
                summary_el = entry.find("atom:summary", ns)
                if title_el is not None and title_el.text:
                    articles.append({
                        "title":   title_el.text.strip(),
                        "url":     link_el.get("href", "") if link_el is not None else "",
                        "summary": summary_el.text.strip()[:300] if summary_el is not None and summary_el.text else "",
                    })

    except Exception as e:
        print(f"[Tech News] RSS fetch error ({url[:50]}): {e}")

    return articles


def summarize_with_groq(raw_articles: list[dict], api_key: str) -> list[dict]:
    """Use Groq to produce clean 1-2 sentence summaries for each headline."""
    if not api_key or not raw_articles:
        return raw_articles

    titles_block = "\n".join(
        f"{i+1}. [{a['source']}] {a['title']}"
        for i, a in enumerate(raw_articles)
    )
    prompt = f"""You are a concise tech journalist. For each of the following tech news headlines, write exactly ONE punchy, plain-English sentence (max 25 words) summarising what it means and WHY it matters to someone studying AI/ML or software engineering.

Headlines:
{titles_block}

Return ONLY a JSON array of strings, one per headline, in the same order. No extra text."""

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={
                "model": "openai/gpt-oss-120b",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.5,
                "response_format": {"type": "json_object"}
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            },
            timeout=30
        )
        text = resp.json()["choices"][0]["message"]["content"]
        # Strip markdown code fences if present
        text = text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        summaries = json.loads(text)
        if isinstance(summaries, dict) and "summaries" in summaries:
            summaries = summaries["summaries"]
        for i, article in enumerate(raw_articles):
            if isinstance(summaries, list) and i < len(summaries):
                article["summary"] = summaries[i]
    except Exception as e:
        print(f"[Tech News] Groq summarisation error: {e}")

    return raw_articles


def has_news_for_today() -> bool:
    today = datetime.date.today().isoformat()
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) as cnt FROM tech_news WHERE fetch_date = ?", (today,)).fetchone()
    conn.close()
    return row["cnt"] > 0


def store_news(articles: list[dict]):
    today = datetime.date.today().isoformat()
    conn = get_db()
    for a in articles:
        conn.execute(
            "INSERT INTO tech_news (fetch_date, title, summary, source, url, icon) VALUES (?,?,?,?,?,?)",
            (today, a["title"], a.get("summary",""), a.get("source",""), a.get("url",""), a.get("icon","📰"))
        )
    conn.commit()
    conn.close()


def fetch_and_store_news(api_key: str = ""):
    """Main pipeline: fetch RSS → deduplicate → AI summarize → store."""
    print("[Tech News] Starting daily fetch...")
    all_articles = []

    for feed in RSS_FEEDS:
        articles = fetch_rss(feed["url"])
        for a in articles:
            a["source"] = feed["name"]
            a["icon"]   = feed["icon"]
        all_articles.extend(articles)
        print(f"[Tech News] {feed['name']}: {len(articles)} articles fetched.")

    if not all_articles:
        print("[Tech News] No articles fetched — network issue?")
        return

    # Pick top N (spread across sources, limit to 10)
    selected = all_articles[:10]

    # Try AI summarization
    selected = summarize_with_groq(selected, api_key)

    store_news(selected)
    print(f"[Tech News] {len(selected)} articles stored for {datetime.date.today().isoformat()}.")


def get_api_key_from_db() -> str:
    """Read Groq API key from the database if it was saved by the frontend."""
    try:
        conn = get_db()
        row = conn.execute("SELECT value FROM settings WHERE key = 'groq_api_key'").fetchone()
        conn.close()
        if row:
            return row["value"]
    except Exception:
        pass
    return os.environ.get("GROQ_API_KEY", "")


def run_tech_news_loop(stop_event: threading.Event):
    """Background daemon loop: fetch on startup if needed, then daily at 06:00."""
    init_tech_news_table()
    purge_old_news()

    # Fetch immediately if no news today
    if not has_news_for_today():
        api_key = get_api_key_from_db()
        fetch_and_store_news(api_key)
    else:
        print("[Tech News] Today's news already cached.")

    # Then check every hour; re-fetch only if date rolled over
    while not stop_event.wait(3600):
        try:
            purge_old_news()
            if not has_news_for_today():
                api_key = get_api_key_from_db()
                fetch_and_store_news(api_key)
        except Exception as e:
            print(f"[Tech News] Loop error: {e}")
