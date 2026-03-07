# 🎯 CompetitorRadar AI

**AI-Powered Competitive Intelligence Platform**

A full-stack SaaS application that automatically monitors competitors, detects changes, and delivers AI-powered strategic insights — helping businesses stay ahead of their competition.

🔗 **Live Demo:** [competitor-radar-frontend.vercel.app](https://competitor-radar-frontend.vercel.app)
🌐 **Landing Page:** [comp-radar.com](https://comp-radar.com)

---

## The Problem

Businesses waste hours manually checking competitor websites, social media, and pricing pages. Changes go unnoticed, and strategic decisions are made with outdated information.

## The Solution

CompetitorRadar automates competitive intelligence by continuously scanning competitor websites, detecting changes, analyzing social media mentions, and delivering AI-powered strategic briefs — all in a clean, real-time dashboard.

---

## Features

### Core Intelligence
- **Automated Web Scanning** — Scrapes competitor websites (pricing, careers, docs, GitHub) every 12 hours using smart JS rendering with cloudscraper + httpx fallback
- **Change Detection** — Identifies content changes, categorizes them by significance (critical/medium/low), and tracks history
- **AI-Powered Briefs** — Generates strategic analysis for each change: what changed, why it matters, what to do, and threat level assessment (powered by OpenAI GPT-4o-mini)

### Social & SEO Monitoring
- **Social Monitor** — Tracks competitor mentions on Reddit (live RSS feed) and Twitter/X with AI-powered sentiment analysis, spam filtering, and announcement detection
- **SEO Tracker** — Monitors competitor search presence and keyword rankings

### Analytics & Reporting
- **Intelligence Dashboard** — Real-time stats with threat distribution, activity timeline, competitor leaderboard, and quick insights
- **Analytics Charts** — Visual trends of competitor activity over time
- **PDF Export** — Export individual briefs or all reports as professional PDFs
- **Weekly Digest Email** — Automated Monday morning email summary of all competitor activity

### Collaboration & Business
- **Multi-User Teams** — Create team workspaces, invite members with role-based access (owner/admin/member), share competitors across teams
- **AI Chat Assistant** — Ask natural language questions about your competitors, get data-driven strategic answers powered by your collected intelligence
- **Stripe Payments** — Three-tier pricing (Free/Pro $29/mo/Team $79/mo) with Stripe Checkout integration
- **Slack Integration** — Real-time alerts pushed to your team's Slack channel

---

## Tech Stack

### Frontend
- **React 18** + **Vite** — Fast, modern SPA
- **Custom Dark Theme** — Professional UI with Sora font
- **Deployed on Vercel** with API proxy rewrites

### Backend
- **FastAPI** (Python) — High-performance async API
- **PostgreSQL** — Relational database with SQLAlchemy async ORM
- **APScheduler** — Background job scheduling (12h auto-scan + Monday weekly digest)
- **Deployed on Railway**

### Integrations
- **OpenAI GPT-4o-mini** — AI analysis, chat assistant, sentiment analysis
- **Stripe** — Payment processing
- **Reddit RSS** — Social media monitoring
- **Gmail SMTP** — Email digest delivery
- **Slack Webhooks** — Real-time notifications

---

## Architecture

```
┌──────────────────┐     ┌──────────────────────┐     ┌────────────────┐
│                  │     │                      │     │                │
│   React + Vite   │────▶│   FastAPI Backend     │────▶│  PostgreSQL    │
│   (Vercel)       │     │   (Railway)          │     │  (Railway)     │
│                  │     │                      │     │                │
└──────────────────┘     └──────────┬───────────┘     └────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
               ┌────▼────┐  ┌─────▼─────┐  ┌────▼────┐
               │ OpenAI  │  │  Reddit   │  │ Stripe  │
               │ GPT-4o  │  │  RSS API  │  │ Checkout│
               └─────────┘  └───────────┘  └─────────┘
```

---

## Project Structure

```
├── frontend/
│   ├── src/
│   │   ├── App.jsx                 # Main app with routing and state
│   │   ├── utils/api.js            # API client class
│   │   └── components/
│   │       ├── Dashboard.jsx       # Intelligence dashboard with charts
│   │       ├── Charts.jsx          # Analytics visualizations
│   │       ├── Chat.jsx            # AI chat assistant
│   │       ├── Teams.jsx           # Team management
│   │       ├── Seo.jsx             # SEO tracker
│   │       └── Social.jsx          # Social media monitor
│   └── vercel.json                 # API proxy configuration
│
├── backend/
│   ├── main.py                     # FastAPI app entry point
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth.py             # JWT authentication
│   │   │   ├── competitors.py      # Competitor CRUD
│   │   │   ├── scanning.py         # Web scanning triggers
│   │   │   ├── changes.py          # Change detection API
│   │   │   ├── reports.py          # AI brief generation
│   │   │   ├── chat.py             # AI chat assistant
│   │   │   ├── teams.py            # Team management
│   │   │   ├── social.py           # Social monitoring
│   │   │   ├── seo.py              # SEO tracking
│   │   │   ├── payments.py         # Stripe integration
│   │   │   └── export.py           # PDF export
│   │   ├── core/
│   │   │   ├── config.py           # Environment configuration
│   │   │   ├── database.py         # Async PostgreSQL connection
│   │   │   └── auth.py             # JWT token handling
│   │   ├── models/
│   │   │   └── models.py           # SQLAlchemy models (8 tables)
│   │   └── services/
│   │       ├── scraper.py          # Web scraping engine
│   │       ├── change_detector.py  # Diff detection algorithm
│   │       ├── ai_analyst.py       # OpenAI integration
│   │       ├── social_tracker.py   # Reddit/Twitter fetching + spam filter
│   │       ├── seo_tracker.py      # SEO monitoring
│   │       ├── scheduler.py        # Background job scheduling
│   │       ├── email_service.py    # Weekly digest emails
│   │       └── slack_service.py    # Slack notifications
│   └── requirements.txt
```

---

## Database Schema

| Table | Description |
|-------|-------------|
| `users` | Authentication, plans, Slack webhooks |
| `teams` | Team workspaces with owner reference |
| `team_members` | Many-to-many user-team with roles |
| `competitors` | Tracked companies with URLs and social handles |
| `snapshots` | Point-in-time website content captures |
| `changes` | Detected differences with significance scores |
| `reports` | AI-generated strategic analysis |
| `social_posts` | Reddit/Twitter mentions with sentiment |

---

## Key Engineering Decisions

**Async Everything** — FastAPI with async SQLAlchemy and httpx for non-blocking I/O across web scraping, AI calls, and database operations.

**Smart Scraping** — Two-tier approach: cloudscraper for JS-heavy sites, httpx fallback for static pages. Handles anti-bot measures gracefully.

**Spam Filtering** — Keyword-based content filter for social media posts, preventing inappropriate Reddit content from appearing in the feed.

**Timezone Handling** — Normalized all datetime objects to naive UTC to prevent PostgreSQL asyncpg timezone mismatch errors across different data sources.

**Demo Data Fallback** — When external APIs are unavailable (rate limits, IP blocks), the system auto-seeds realistic demo data so the product remains demonstrable.

**Auth as Dict Pattern** — JWT authentication returns a lightweight dict instead of full ORM objects, reducing database queries on every authenticated request.

---

## Local Development

### Prerequisites
- Python 3.12+
- Node.js 18+
- PostgreSQL 15+

### Backend Setup
```bash
cd backend
pip install -r requirements.txt
# Set environment variables (see .env.example)
uvicorn main:app --reload --port 8080
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### Environment Variables
```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/radar
JWT_SECRET=your-secret-key
OPENAI_API_KEY=sk-...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
SMTP_EMAIL=your@gmail.com
SMTP_PASSWORD=app-password
```

---

## Deployment

- **Frontend:** Push to GitHub → auto-deploys on Vercel
- **Backend:** Push to GitHub → auto-deploys on Railway
- **Database:** Railway PostgreSQL (auto-provisioned)
- **API Proxy:** Vercel rewrites `/api/*` → Railway backend

---

## What I Learned

Building this project taught me production-grade full-stack development: debugging timezone mismatches across async database drivers, handling third-party API rate limits with graceful fallbacks, implementing JWT auth patterns for async Python, managing database migrations without Alembic using runtime ALTER TABLE statements, and building real-time data pipelines from Reddit RSS feeds with AI-powered content analysis.

---

## Future Roadmap

- [ ] Add comprehensive test suite (pytest + React Testing Library)
- [ ] Implement Alembic for proper database migrations
- [ ] Add WebSocket support for real-time scan updates
- [ ] Build browser extension for quick competitor adds
- [ ] Implement competitor comparison reports
- [ ] Add API rate limiting and usage analytics

---

## Author

**Abhishek Rahul**

Built as a full-stack SaaS project demonstrating end-to-end product development — from architecture and AI integration to deployment and team collaboration features.

---

*Built with React, FastAPI, PostgreSQL, and OpenAI*
