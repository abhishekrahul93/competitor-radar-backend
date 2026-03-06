import httpx
import feedparser
import asyncio
import re
import os
import json
from datetime import datetime, timezone
from openai import AsyncOpenAI


def _clean_html(text: str) -> str:
    return re.sub(r'<[^>]+>', '', text).strip()


async def _fetch_twitter_api(handle: str, bearer_token: str) -> list:
    posts = []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            user_resp = await client.get(
                f"https://api.twitter.com/2/users/by/username/{handle}",
                headers={"Authorization": f"Bearer {bearer_token}"}
            )
            if user_resp.status_code != 200:
                return posts
            user_id = user_resp.json()["data"]["id"]
            tweets_resp = await client.get(
                f"https://api.twitter.com/2/users/{user_id}/tweets",
                headers={"Authorization": f"Bearer {bearer_token}"},
                params={"max_results": 10, "tweet.fields": "created_at,public_metrics,text", "exclude": "retweets,replies"}
            )
            for tweet in tweets_resp.json().get("data", []):
                posts.append({
                    "post_id": tweet["id"],
                    "platform": "twitter",
                    "content": tweet["text"],
                    "post_url": f"https://twitter.com/{handle}/status/{tweet['id']}",
                    "author": f"@{handle}",
                    "posted_at": datetime.fromisoformat(tweet["created_at"].replace("Z", "+00:00")),
                    "engagement": tweet.get("public_metrics", {})
                })
    except Exception as e:
        print(f"[Twitter API] Error for @{handle}: {e}")
    return posts


async def _fetch_twitter_nitter(handle: str) -> list:
    nitter_instances = [
        "https://nitter.privacydev.net",
        "https://nitter.poast.org",
        "https://nitter.net",
    ]
    for instance in nitter_instances:
        try:
            async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
                resp = await client.get(f"{instance}/{handle}/rss")
                if resp.status_code == 200:
                    feed = feedparser.parse(resp.text)
                    posts = []
                    for entry in feed.entries[:10]:
                        try:
                            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                                posted_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                            else:
                                posted_at = datetime.utcnow().replace(tzinfo=timezone.utc)
                        except Exception:
                            posted_at = datetime.utcnow().replace(tzinfo=timezone.utc)
                        posts.append({
                            "post_id": entry.get("id", entry.link),
                            "platform": "twitter",
                            "content": _clean_html(entry.get("summary", entry.get("title", ""))),
                            "post_url": re.sub(r'https?://[^/]+', 'https://twitter.com', entry.link),
                            "author": f"@{handle}",
                            "posted_at": posted_at,
                            "engagement": {}
                        })
                    if posts:
                        return posts
        except Exception as e:
            print(f"[Nitter] {instance} failed: {e}")
            continue
    return []


async def fetch_twitter_posts(competitor) -> list:
    handle = (competitor.twitter_handle or "").strip().lstrip("@")
    if not handle:
        return []
    bearer = os.getenv("TWITTER_BEARER_TOKEN")
    if bearer:
        posts = await _fetch_twitter_api(handle, bearer)
        if posts:
            return posts
    return await _fetch_twitter_nitter(handle)


async def fetch_reddit_mentions(competitor) -> list:
    keywords = (competitor.reddit_keywords or competitor.name or "").strip()
    if not keywords:
        return []
    posts = []
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": "CompetitorRadar/1.0 (monitoring tool)"},
            timeout=15
        ) as client:
            resp = await client.get(
                "https://www.reddit.com/search.json",
                params={"q": keywords, "sort": "new", "limit": 10, "t": "week"}
            )
            if resp.status_code == 200:
                for item in resp.json().get("data", {}).get("children", []):
                    p = item["data"]
                    posts.append({
                        "post_id": p["id"],
                        "platform": "reddit",
                        "content": f"{p['title']}\n{p.get('selftext', '')[:400]}".strip(),
                        "post_url": f"https://reddit.com{p['permalink']}",
                        "author": f"u/{p.get('author', 'unknown')}",
                        "posted_at": datetime.fromtimestamp(p["created_utc"], tz=timezone.utc),
                        "engagement": {"upvotes": p.get("ups", 0), "comments": p.get("num_comments", 0)}
                    })
    except Exception as e:
        print(f"[Reddit] Error for '{keywords}': {e}")
    return posts


async def analyze_post_with_ai(content: str, competitor_name: str) -> dict:
    default = {"sentiment": "neutral", "is_announcement": False, "summary": content[:120], "significance": "low"}
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return default
    try:
        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a competitive intelligence analyst. Respond ONLY with valid JSON."},
                {"role": "user", "content": f'Analyze this post from {competitor_name}:\n\n"{content[:600]}"\n\nReturn JSON with keys: sentiment (positive/negative/neutral), is_announcement (bool), summary (string), significance (high/medium/low)'}
            ],
            max_tokens=150,
            temperature=0.3
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r'^```json|^```|```$', '', raw, flags=re.MULTILINE).strip()
        return json.loads(raw)
    except Exception as e:
        print(f"[AI] Post analysis error: {e}")
        return default


async def scan_competitor_social(competitor, db) -> int:
    from app.models.models import SocialPost
    from sqlalchemy import select

    twitter_posts = await fetch_twitter_posts(competitor)
    reddit_posts = await fetch_reddit_mentions(competitor)
    all_posts = twitter_posts + reddit_posts

    new_count = 0
    for post_data in all_posts:
        existing = await db.execute(
            select(SocialPost).where(
                SocialPost.platform == post_data["platform"],
                SocialPost.post_id == str(post_data["post_id"])
            )
        )
        if existing.scalar_one_or_none():
            continue

        ai = await analyze_post_with_ai(post_data["content"], competitor.name)

        post = SocialPost(
            competitor_id=competitor.id,
            platform=post_data["platform"],
            post_id=str(post_data["post_id"]),
            post_url=post_data.get("post_url"),
            content=post_data.get("content"),
            author=post_data.get("author"),
            posted_at=post_data.get("posted_at"),
            engagement=post_data.get("engagement", {}),
            sentiment=ai.get("sentiment", "neutral"),
            is_announcement=ai.get("is_announcement", False),
            ai_summary=ai.get("summary", "")
        )
        db.add(post)
        new_count += 1

    if new_count:
        await db.commit()

    return new_count
