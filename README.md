# 🔥 ConsistencyHub — Habit Tracker, Journal & Analytics

A Streamlit web app built for a college project: track daily habits, journal your mood,
and explore comprehensive analytics — with a full login system (Guest / User / Admin roles).

## 🎯 Problem Statement
Most people who want to build better habits fail not from lack of motivation but from lack
of **visibility and accountability**. Sticky notes and memory don't show the bigger picture:
how consistent you actually are, how mood connects to habits, or how close you are to
breaking a streak. ConsistencyHub brings habit tracking, journaling, and analytics together
into one dashboard.

## ✨ Features
- 🔐 Secure login with hashed + salted passwords
- 👀 Guest mode (no signup needed — session-only data)
- 🛠️ Admin role with a platform-wide leaderboard and user management
- ✅ Habit tracker with categories, weekly targets, live streaks
- 📔 Mood journal
- 📊 Analytics: completion rates, daily trend, 30-day heatmap, streak badges,
  category breakdown, mood-vs-completion correlation, CSV export
- 🎨 Custom orange "fire" theme (`.streamlit/config.toml`)

## 🧱 Tech Stack
Python · Streamlit · SQLite · Pandas · Plotly

## ▶️ Run Locally
```bash
pip install -r requirements.txt
streamlit run app.py
```
Default admin login: `admin` / `admin123` — **change this password after first login**
(Account settings → sidebar, once logged in).

## ☁️ Deploy on Streamlit Community Cloud
1. Create a new GitHub repository and push these files:
   `app.py`, `requirements.txt`, `.streamlit/config.toml`, `README.md`
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **"New app"**, pick your repo/branch, and set the main file to `app.py`.
4. Click **Deploy**. Streamlit Cloud installs `requirements.txt` automatically.

### ⚠️ Important note for your presentation / viva
This project uses **SQLite** (`tracker.db`) for simplicity, which is great for a demo but
has one limitation on Streamlit Community Cloud: the filesystem is **ephemeral** — if the
app goes to sleep and restarts, or you redeploy, the database resets. This is a well-known
trade-off of free-tier hosting with local file databases, and mentioning it (plus the
"Future Scope" fix: migrating to a hosted DB like Postgres/Supabase) shows a strong grasp
of real-world deployment considerations.

## 🚀 Future Scope
- Hosted database (Postgres/Supabase) for permanent persistence
- Email/push reminders
- Social features — shared streaks, group challenges
