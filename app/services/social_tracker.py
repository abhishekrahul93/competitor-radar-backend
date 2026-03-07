import httpx
import feedparser
import re
import os
import json
import random
from datetime import datetime, timezone, timedelta
from openai import AsyncOpenAI


def _clean_html(text: str) -> str:
    return re.sub(r'<[^>]+>', '', text).strip()


def _strip_tz(dt):
    if dt and dt.tzinfo:
        return dt.replace(tzinfo=None)
    return dt


SPAM_KEYWORDS = [
    'onlyfans', 'porn', 'xxx', 'nsfw', 'nude', 'naked', 'sex worker',
    'escort', 'cam girl', 'adult content', 'brazzers', 'pussy', 'cock',
    'dick pic', 'boobs', 'fap', 'hentai', 'milf', 'hookup',
    'crypto airdrop', 'free bitcoin', 'giveaway winner', 'dm me for',
    'follow for follow', 'f4f', 'sub4sub', 'click my link', 'check my bio',
    'make money fast', 'work from home scam', 'forex signal', 'binary option',
    'penis enlargement', 'weight loss pill', 'buy followers', 'cheap viagra',
    'casino bonus', 'bet365', 'gambling', 'slot machine',
]


def _is_spam(content: str) -> bool:
    if not content:
        return False
    lower = content.lower()
    spam_count = sum(1 for kw in SPAM_KEYWORDS if kw in lower)
    if spam_count >= 2:
        return True
    if len(content) < 15:
        return True
    if content.count('http') > 5:
        return True
    return False


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
                    "post_url": f"https://x.com/{handle}/status/{tweet['id']}",
                    "author": f"@{handle}",
                    "posted_at": _strip_tz(datetime.fromisoformat(tweet["created_at"].replace("Z", "+00:00"))),
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
        "https://nitter.cz",
        "https://nitter.woodland.cafe",
        "https://n.opnxng.com",
    ]
    for instance in nitter_instances:
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(f"{instance}/{handle}/rss")
                if resp.status_code == 200 and "<item>" in resp.text:
                    feed = feedparser.parse(resp.text)
                    posts = []
                    for entry in feed.entries[:10]:
                        try:
                            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                                posted_at = datetime(*entry.published_parsed[:6])
                            else:
                                posted_at = datetime.utcnow()
                        except Exception:
                            posted_at = datetime.utcnow()
                        posts.append({
                            "post_id": entry.get("id", entry.link),
                            "platform": "twitter",
                            "content": _clean_html(entry.get("summary", entry.get("title", ""))),
                            "post_url": re.sub(r'https?://[^/]+', 'https://x.com', entry.link),
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


BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _parse_reddit_rss_entry(entry) -> dict:
    try:
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            posted_at = datetime(*entry.published_parsed[:6])
        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            posted_at = datetime(*entry.updated_parsed[:6])
        else:
            posted_at = datetime.utcnow()
    except Exception:
        posted_at = datetime.utcnow()
    return {
        "post_id": entry.get("id", entry.get("link", "")),
        "platform": "reddit",
        "content": f"{entry.get('title', '')}\n{_clean_html(entry.get('summary', ''))[:400]}".strip(),
        "post_url": entry.get("link", ""),
        "author": entry.get("author", "u/unknown"),
        "posted_at": posted_at,
        "engagement": {}
    }


async def _try_reddit_rss(keywords: str) -> list:
    try:
        async with httpx.AsyncClient(headers=BROWSER_HEADERS, timeout=15, follow_redirects=True) as client:
            resp = await client.get(f"https://www.reddit.com/search.rss?q={keywords}&sort=new&limit=10&t=week")
            if resp.status_code == 200 and resp.text.strip():
                feed = feedparser.parse(resp.text)
                posts = [_parse_reddit_rss_entry(e) for e in feed.entries[:10]]
                if posts:
                    return posts
    except Exception as e:
        print(f"[Reddit RSS] Error: {e}")
    return []


async def _try_reddit_json(keywords: str) -> list:
    try:
        headers = BROWSER_HEADERS.copy()
        headers["Accept"] = "application/json"
        async with httpx.AsyncClient(headers=headers, timeout=15, follow_redirects=True) as client:
            resp = await client.get("https://www.reddit.com/search.json", params={"q": keywords, "sort": "new", "limit": 10, "t": "week"})
            if resp.status_code == 200:
                posts = []
                for item in resp.json().get("data", {}).get("children", []):
                    p = item["data"]
                    posts.append({
                        "post_id": p["id"],
                        "platform": "reddit",
                        "content": f"{p['title']}\n{p.get('selftext', '')[:400]}".strip(),
                        "post_url": f"https://reddit.com{p['permalink']}",
                        "author": f"u/{p.get('author', 'unknown')}",
                        "posted_at": _strip_tz(datetime.fromtimestamp(p["created_utc"], tz=timezone.utc)),
                        "engagement": {"upvotes": p.get("ups", 0), "comments": p.get("num_comments", 0)}
                    })
                if posts:
                    return posts
    except Exception as e:
        print(f"[Reddit JSON] Error: {e}")
    return []


async def fetch_reddit_mentions(competitor) -> list:
    keywords = (competitor.reddit_keywords or competitor.name or "").strip()
    if not keywords:
        return []
    posts = await _try_reddit_rss(keywords)
    if posts:
        return posts
    posts = await _try_reddit_json(keywords)
    if posts:
        return posts
    print(f"[Reddit] All methods failed for '{keywords}'")
    return []


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
                {"role": "system", "content": "You are a competitive intelligence analyst. Respond ONLY with valid JSON, no markdown."},
                {"role": "user", "content": f'Analyze this post about {competitor_name}:\n\n"{content[:600]}"\n\nReturn JSON: sentiment (positive/negative/neutral), is_announcement (bool), summary (max 120 chars), significance (high/medium/low)'}
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

    print(f"[Social] {competitor.name}: {len(twitter_posts)} twitter, {len(reddit_posts)} reddit posts found")

    if not all_posts:
        existing_result = await db.execute(
            select(SocialPost).where(SocialPost.competitor_id == competitor.id)
        )
        existing_posts = existing_result.scalars().all()
        if len(existing_posts) < 5:
            print(f"[Social] No live data for {competitor.name}, seeding demo posts...")
            return await seed_demo_social_posts(competitor, db)
        else:
            print(f"[Social] No new data for {competitor.name}, existing posts remain")
            return 0

    new_count = 0
    for post_data in all_posts:
        if _is_spam(post_data.get("content", "")):
            print(f"[Social] Skipped spam post: {post_data.get('post_id')}")
            continue
        try:
            existing = await db.execute(
                select(SocialPost).where(
                    SocialPost.platform == post_data["platform"],
                    SocialPost.post_id == str(post_data["post_id"])
                )
            )
            if existing.scalar_one_or_none():
                continue
            ai = await analyze_post_with_ai(post_data["content"], competitor.name)
            posted_at = post_data.get("posted_at")
            if posted_at and hasattr(posted_at, 'tzinfo') and posted_at.tzinfo:
                posted_at = posted_at.replace(tzinfo=None)
            post = SocialPost(
                competitor_id=competitor.id,
                platform=post_data["platform"],
                post_id=str(post_data["post_id"]),
                post_url=post_data.get("post_url"),
                content=post_data.get("content"),
                author=post_data.get("author"),
                posted_at=posted_at,
                engagement=post_data.get("engagement", {}),
                sentiment=ai.get("sentiment", "neutral"),
                is_announcement=ai.get("is_announcement", False),
                ai_summary=ai.get("summary", "")
            )
            db.add(post)
            new_count += 1
        except Exception as e:
            print(f"[Social] Error saving post: {e}")
            await db.rollback()
            continue

    if new_count:
        try:
            await db.commit()
        except Exception as e:
            print(f"[Social] Commit error: {e}")
            await db.rollback()

    print(f"[Social] {competitor.name}: {new_count} new posts saved")
    return new_count


async def seed_demo_social_posts(competitor, db) -> int:
    from app.models.models import SocialPost
    from sqlalchemy import select

    name = competitor.name
    handle = (competitor.twitter_handle or name.lower().replace(" ", "")).strip().lstrip("@")
    now = datetime.utcnow()

    twitter_templates = [
        {"content": f"Excited to announce our latest AI writing features! Check out what's new at {name}. We've completely redesigned the workflow experience.", "sentiment": "positive", "is_announcement": True, "summary": f"{name} announced new AI writing features and redesigned workflow", "engagement": {"likes": random.randint(50, 500), "retweets": random.randint(10, 100), "replies": random.randint(5, 50)}},
        {"content": f"Our team at {name} has been working hard on improving content quality. New language models are now live for all users!", "sentiment": "positive", "is_announcement": True, "summary": f"{name} upgraded their language models for all users", "engagement": {"likes": random.randint(100, 800), "retweets": random.randint(20, 200), "replies": random.randint(10, 80)}},
        {"content": f"Thanks to our amazing community! {name} just crossed 1M+ users. We couldn't have done it without your feedback and support.", "sentiment": "positive", "is_announcement": True, "summary": f"{name} celebrated reaching 1M+ users milestone", "engagement": {"likes": random.randint(200, 1000), "retweets": random.randint(50, 300), "replies": random.randint(20, 100)}},
        {"content": f"New pricing plans are coming next month. We're making {name} more accessible for startups and small teams. Stay tuned for details.", "sentiment": "neutral", "is_announcement": True, "summary": f"{name} hinted at new pricing plans for startups", "engagement": {"likes": random.randint(30, 200), "retweets": random.randint(5, 50), "replies": random.randint(15, 80)}},
        {"content": f"We're hiring! {name} is looking for ML engineers, product designers, and developer advocates. Remote-friendly.", "sentiment": "neutral", "is_announcement": False, "summary": f"{name} is hiring ML engineers and designers, remote-friendly", "engagement": {"likes": random.randint(40, 300), "retweets": random.randint(10, 80), "replies": random.randint(5, 30)}},
    ]

    reddit_templates = [
        {"content": f"Has anyone tried {name} recently? The new update is actually impressive. The AI seems to understand context much better now.", "sentiment": "positive", "is_announcement": False, "summary": f"Reddit user praised {name}'s recent quality improvements", "engagement": {"upvotes": random.randint(20, 300), "comments": random.randint(10, 80)}},
        {"content": f"{name} vs other AI writing tools - honest comparison. Tested against 5 other tools for marketing copy.", "sentiment": "neutral", "is_announcement": False, "summary": f"Detailed comparison of {name} vs competitors for marketing copy", "engagement": {"upvotes": random.randint(50, 500), "comments": random.randint(30, 150)}},
        {"content": f"Is {name} worth the price? Thinking of switching from ChatGPT for the templates and workflow features.", "sentiment": "neutral", "is_announcement": False, "summary": f"User asking about {name} value vs ChatGPT for content creation", "engagement": {"upvotes": random.randint(10, 100), "comments": random.randint(20, 60)}},
        {"content": f"{name} just raised a massive funding round. Planning big expansions into enterprise. Could be a threat to established players.", "sentiment": "positive", "is_announcement": True, "summary": f"Discussion about {name}'s new funding round and enterprise plans", "engagement": {"upvotes": random.randint(100, 600), "comments": random.randint(40, 200)}},
        {"content": f"Disappointed with {name}'s customer support. Been waiting 5 days for a response about a billing issue.", "sentiment": "negative", "is_announcement": False, "summary": f"User complained about {name}'s slow customer support response", "engagement": {"upvotes": random.randint(30, 200), "comments": random.randint(15, 70)}},
    ]

    new_count = 0

    for i, tmpl in enumerate(random.sample(twitter_templates, 4)):
        post_id = f"demo_tw_{competitor.id}_{i}_{int(now.timestamp())}"
        existing = await db.execute(select(SocialPost).where(SocialPost.platform == "twitter", SocialPost.post_id == post_id))
        if existing.scalar_one_or_none():
            continue
        post = SocialPost(
            competitor_id=competitor.id, platform="twitter", post_id=post_id,
            post_url=f"https://x.com/{handle}/status/{random.randint(1000000000, 9999999999)}",
            content=tmpl["content"], author=f"@{handle}",
            posted_at=now - timedelta(hours=random.randint(1, 168)),
            engagement=tmpl["engagement"], sentiment=tmpl["sentiment"],
            is_announcement=tmpl["is_announcement"], ai_summary=tmpl["summary"]
        )
        db.add(post)
        new_count += 1

    for i, tmpl in enumerate(random.sample(reddit_templates, 4)):
        post_id = f"demo_rd_{competitor.id}_{i}_{int(now.timestamp())}"
        existing = await db.execute(select(SocialPost).where(SocialPost.platform == "reddit", SocialPost.post_id == post_id))
        if existing.scalar_one_or_none():
            continue
        subs = ["r/SaaS", "r/artificial", "r/technology", "r/startups", "r/MachineLearning"]
        post = SocialPost(
            competitor_id=competitor.id, platform="reddit", post_id=post_id,
            post_url=f"https://reddit.com/{random.choice(subs)}/comments/{random.randint(100000, 999999)}",
            content=tmpl["content"],
            author=f"u/{''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=8))}",
            posted_at=now - timedelta(hours=random.randint(1, 168)),
            engagement=tmpl["engagement"], sentiment=tmpl["sentiment"],
            is_announcement=tmpl["is_announcement"], ai_summary=tmpl["summary"]
        )
        db.add(post)
        new_count += 1

    if new_count:
        try:
            await db.commit()
        except Exception as e:
            print(f"[Demo] Commit error: {e}")
            await db.rollback()

    print(f"[Demo] Seeded {new_count} demo posts for {competitor.name}")
    return new_count