import feedparser
import requests
import hashlib
import time
from datetime import datetime, timezone
from dateutil import parser as date_parser
from bs4 import BeautifulSoup
from typing import Optional

RSS_SOURCES = [
    {"name": "Hacker News", "url": "https://hnrss.org/frontpage?count=20", "category": "Tech"},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "category": "Tech"},
    {"name": "Wired", "url": "https://www.wired.com/feed/rss", "category": "Tech"},
    {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index", "category": "Tech"},
    {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/", "category": "AI"},
    {"name": "VentureBeat AI", "url": "https://venturebeat.com/category/ai/feed/", "category": "AI"},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "category": "Startups"},
    {"name": "Reuters Technology", "url": "https://feeds.reuters.com/reuters/technologyNews", "category": "Business"},
]

CATEGORY_KEYWORDS = {
    "AI": ["artificial intelligence", "machine learning", "llm", "gpt", "claude", "openai", "deepmind", "neural", "model", "ai "],
    "Tech": ["software", "hardware", "apple", "google", "microsoft", "chip", "semiconductor", "open source", "developer"],
    "Business": ["startup", "funding", "ipo", "acquisition", "revenue", "valuation", "market", "ceo", "investment"],
    "Science": ["research", "study", "quantum", "space", "nasa", "climate", "biology", "physics", "breakthrough"],
    "Security": ["hack", "breach", "vulnerability", "cybersecurity", "exploit", "privacy", "surveillance"],
}

_article_cache: dict = {}
_feed_cache: dict = {"articles": [], "fetched_at": 0}
CACHE_TTL = 600  # 10 minutes


def _extract_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    return soup.get_text(separator=" ", strip=True)[:2000]


def _detect_category(title: str, summary: str) -> str:
    combined = (title + " " + summary).lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            return cat
    return "General"


def _parse_date(entry) -> str:
    for field in ("published", "updated"):
        raw = entry.get(field)
        if raw:
            try:
                return date_parser.parse(raw).astimezone(timezone.utc).isoformat()
            except Exception:
                pass
    return datetime.now(timezone.utc).isoformat()


def _article_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def _fetch_single_feed(source: dict) -> list:
    try:
        feed = feedparser.parse(source["url"])
        articles = []
        for entry in feed.entries[:8]:
            url = entry.get("link", "")
            if not url:
                continue
            title = entry.get("title", "").strip()
            raw_summary = entry.get("summary", entry.get("description", ""))
            summary = _extract_text(raw_summary)
            image = None
            if hasattr(entry, "media_content") and entry.media_content:
                image = entry.media_content[0].get("url")
            if not image and hasattr(entry, "enclosures") and entry.enclosures:
                for enc in entry.enclosures:
                    if enc.get("type", "").startswith("image"):
                        image = enc.get("href")
                        break
            article = {
                "id": _article_id(url),
                "title": title,
                "summary": summary,
                "url": url,
                "source": source["name"],
                "category": _detect_category(title, summary),
                "published_at": _parse_date(entry),
                "image": image,
                "read_time": max(1, len(summary.split()) // 200),
            }
            articles.append(article)
            _article_cache[article["id"]] = article
        return articles
    except Exception as e:
        print(f"Feed fetch error ({source['name']}): {e}")
        return []


def fetch_articles(force: bool = False) -> list:
    now = time.time()
    if not force and _feed_cache["articles"] and (now - _feed_cache["fetched_at"]) < CACHE_TTL:
        return _feed_cache["articles"]

    all_articles = []
    for source in RSS_SOURCES:
        all_articles.extend(_fetch_single_feed(source))

    # Deduplicate by title similarity (simple)
    seen_titles = set()
    unique = []
    for a in all_articles:
        key = a["title"][:60].lower()
        if key not in seen_titles:
            seen_titles.add(key)
            unique.append(a)

    # Sort by published date desc
    unique.sort(key=lambda x: x["published_at"], reverse=True)
    _feed_cache["articles"] = unique[:60]
    _feed_cache["fetched_at"] = now
    return _feed_cache["articles"]


def get_article(article_id: str) -> Optional[dict]:
    return _article_cache.get(article_id)


def get_full_article_content(url: str) -> str:
    try:
        resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        paragraphs = soup.find_all("p")
        text = " ".join(p.get_text(strip=True) for p in paragraphs)
        return text[:4000]
    except Exception:
        return ""
