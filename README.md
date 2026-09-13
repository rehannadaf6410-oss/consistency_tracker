# Consistency Tracker

A Streamlit web app for tracking daily habits, journaling, and viewing analytics — completion rates, streaks, and mood trends.

## Features
- **Habit Tracker** — add habits, check them off daily, see live streaks
- **Journal** — daily mood slider + free-text entry, with history view
- **Analytics** — completion % per habit, daily consistency trend, streak table, mood-over-time chart

## Local Setup
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud (free, no terminal needed after this)
1. Push this repo to your GitHub account (steps below).
2. Go to https://streamlit.io/cloud and sign in with GitHub.
3. Click **New app**, select this repository, branch `main`, and set the main file to `app.py`.
4. Click **Deploy**. You'll get a permanent public URL like `https://your-app-name.streamlit.app`.

## Data storage
This app uses a local SQLite file (`tracker.db`) that's created automatically on first run. On Streamlit Community Cloud, this file resets whenever the app restarts/redeploys (the free tier doesn't have persistent storage) — fine for personal use and testing, but keep that in mind for long-term data.
