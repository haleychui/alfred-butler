"""
Search service for Alfred: news, podcasts, music, jokes
"""
import httpx
import urllib.parse
from xml.etree import ElementTree as ET


def search_news(query: str, lang: str = "zh-TW", max_results: int = 5) -> list[dict]:
    """Fetch recent news via Google News RSS (free, no API key)."""
    encoded = urllib.parse.quote(query)
    if lang == "zh-TW":
        url = f"https://news.google.com/rss/search?q={encoded}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    else:
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    try:
        r = httpx.get(url, timeout=15, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0 Alfred/1.0"})
        root = ET.fromstring(r.text)
        items = root.findall(".//item")[:max_results]
        results = []
        for item in items:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            source_el = item.find("source")
            source = source_el.text if source_el is not None else ""
            if title:
                results.append({
                    "title": title,
                    "url": link,
                    "pub_date": pub_date[:16] if pub_date else "",
                    "source": source,
                })
        return results
    except Exception as e:
        return []


def search_podcast_episodes(query: str, max_results: int = 3) -> list[dict]:
    """Search podcast episodes via iTunes API (free, no API key needed)."""
    try:
        r = httpx.get(
            "https://itunes.apple.com/search",
            params={
                "term": query,
                "media": "podcast",
                "entity": "podcastEpisode",
                "limit": max_results,
                "country": "TW",
            },
            timeout=10
        )
        results = r.json().get("results", [])
        episodes = []
        for p in results:
            audio_url = p.get("episodeUrl", "")
            if not audio_url:
                continue
            episodes.append({
                "title": p.get("trackName", ""),
                "show": p.get("collectionName", ""),
                "audio_url": audio_url,
                "description": (p.get("shortDescription") or p.get("description") or "")[:200],
                "duration_sec": (p.get("trackTimeMillis") or 0) // 1000,
                "pub_date": (p.get("releaseDate") or "")[:10],
                "artwork": p.get("artworkUrl160", ""),
            })
        return episodes
    except Exception:
        return []


def search_podcast_shows(query: str, max_results: int = 3) -> list[dict]:
    """Search for podcast shows via iTunes API."""
    try:
        r = httpx.get(
            "https://itunes.apple.com/search",
            params={
                "term": query,
                "media": "podcast",
                "entity": "podcast",
                "limit": max_results,
                "country": "TW",
            },
            timeout=10
        )
        results = r.json().get("results", [])
        shows = []
        for p in results:
            shows.append({
                "name": p.get("collectionName", ""),
                "artist": p.get("artistName", ""),
                "feed_url": p.get("feedUrl", ""),
                "genre": ", ".join(p.get("genres", [])),
                "apple_url": p.get("collectionViewUrl", ""),
                "episode_count": p.get("trackCount", 0),
                "artwork": p.get("artworkUrl160", ""),
            })
        return shows
    except Exception:
        return []


def get_latest_podcast_episode(feed_url: str) -> dict | None:
    """Fetch the latest episode from a podcast RSS feed."""
    try:
        r = httpx.get(feed_url, timeout=10, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0 Alfred/1.0"})
        root = ET.fromstring(r.text)
        item = root.find(".//item")
        if not item:
            return None
        enclosure = item.find("enclosure")
        audio_url = enclosure.get("url", "") if enclosure is not None else ""
        return {
            "title": item.findtext("title", "").strip(),
            "audio_url": audio_url,
            "pub_date": item.findtext("pubDate", "")[:16],
            "description": item.findtext("description", "")[:200],
        }
    except Exception:
        return None


def youtube_search_url(query: str) -> str:
    return f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"


def spotify_search_url(query: str) -> str:
    return f"https://open.spotify.com/search/{urllib.parse.quote(query)}"
