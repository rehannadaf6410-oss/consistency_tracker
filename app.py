"""
Consistency Tracker + Journaling + Analytics
Run with: streamlit run app.py
"""

import streamlit as st
import sqlite3
import pandas as pd
import datetime
import plotly.express as px

# ---------------------------------------------------------
# DATABASE SETUP
# ---------------------------------------------------------
DB_PATH = "tracker.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS habit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id INTEGER,
            log_date TEXT,
            done INTEGER,
            UNIQUE(habit_id, log_date)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_date TEXT UNIQUE,
            mood INTEGER,
            entry TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------
def add_habit(name):
    conn = get_conn()
    try:
        conn.execute("INSERT INTO habits (name) VALUES (?)", (name,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

def get_habits():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM habits", conn)
    conn.close()
    return df

def mark_habit(habit_id, log_date, done):
    conn = get_conn()
    conn.execute("""
        INSERT INTO habit_logs (habit_id, log_date, done)
        VALUES (?, ?, ?)
        ON CONFLICT(habit_id, log_date) DO UPDATE SET done=excluded.done
    """, (habit_id, log_date, int(done)))
    conn.commit()
    conn.close()

def get_logs():
    conn = get_conn()
    df = pd.read_sql("""
        SELECT hl.log_date, h.name as habit, hl.done
        FROM habit_logs hl
        JOIN habits h ON h.id = hl.habit_id
    """, conn)
    conn.close()
    return df

def save_journal(log_date, mood, entry):
    conn = get_conn()
    conn.execute("""
        INSERT INTO journal (log_date, mood, entry)
        VALUES (?, ?, ?)
        ON CONFLICT(log_date) DO UPDATE SET mood=excluded.mood, entry=excluded.entry
    """, (log_date, mood, entry))
    conn.commit()
    conn.close()

def get_journal():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal ORDER BY log_date", conn)
    conn.close()
    return df

def current_streak(habit_id):
    conn = get_conn()
    df = pd.read_sql(
        "SELECT log_date, done FROM habit_logs WHERE habit_id=? ORDER BY log_date DESC",
        conn, params=(habit_id,)
    )
    conn.close()
    streak = 0
    today = datetime.date.today()
    for i, row in df.iterrows():
        expected = today - datetime.timedelta(days=streak)
        if str(row["log_date"]) == str(expected) and row["done"] == 1:
            streak += 1
        else:
            break
    return streak

# ---------------------------------------------------------
# UI CONFIG
# ---------------------------------------------------------
st.set_page_config(page_title="Consistency Tracker", page_icon="🔥", layout="wide")

st.sidebar.title("📌 Menu")
page = st.sidebar.radio("Go to", ["Habit Tracker", "Journal", "Analytics"])

today_str = str(datetime.date.today())

# ---------------------------------------------------------
# PAGE 1: HABIT TRACKER
# ---------------------------------------------------------
if page == "Habit Tracker":
    st.title("🔥 Daily Consistency Tracker")

    with st.expander("➕ Add a new habit"):
        new_habit = st.text_input("Habit name (e.g. Coding practice, Gym, Reading)")
        if st.button("Add Habit"):
            if new_habit.strip():
                add_habit(new_habit.strip())
                st.success(f"Added: {new_habit}")
                st.rerun()

    habits = get_habits()

    if habits.empty:
        st.info("Pehle upar se ek habit add karo.")
    else:
        st.subheader(f"Today — {today_str}")
        for _, h in habits.iterrows():
            col1, col2 = st.columns([3, 1])
            with col1:
                done = st.checkbox(h["name"], key=f"chk_{h['id']}")
            with col2:
                streak = current_streak(h["id"])
                st.write(f"🔥 Streak: {streak}")
            mark_habit(h["id"], today_str, done)

# ---------------------------------------------------------
# PAGE 2: JOURNAL
# ---------------------------------------------------------
elif page == "Journal":
    st.title("📔 Daily Journal")

    journal_df = get_journal()
    existing = journal_df[journal_df["log_date"] == today_str]

    default_mood = int(existing["mood"].values[0]) if not existing.empty else 5
    default_entry = existing["entry"].values[0] if not existing.empty else ""

    mood = st.slider("Aaj ka mood (1 = bekar, 10 = zabardast)", 1, 10, default_mood)
    entry = st.text_area("Aaj kya kiya / kaisa gaya likho:", value=default_entry, height=200)

    if st.button("Save Journal Entry"):
        save_journal(today_str, mood, entry)
        st.success("Saved!")

    st.divider()
    st.subheader("📖 Past Entries")
    if journal_df.empty:
        st.write("Abhi koi entry nahi hai.")
    else:
        for _, row in journal_df.sort_values("log_date", ascending=False).iterrows():
            with st.expander(f"{row['log_date']} — Mood: {row['mood']}/10"):
                st.write(row["entry"])

# ---------------------------------------------------------
# PAGE 3: ANALYTICS
# ---------------------------------------------------------
elif page == "Analytics":
    st.title("📊 Analytics")

    logs = get_logs()
    journal_df = get_journal()

    if logs.empty:
        st.info("Analytics dikhne ke liye pehle kuch habits track karo.")
    else:
        # Completion rate per habit
        st.subheader("Habit Completion Rate")
        summary = logs.groupby("habit")["done"].mean().reset_index()
        summary["done"] = (summary["done"] * 100).round(1)
        fig1 = px.bar(summary, x="habit", y="done",
                       labels={"done": "Completion %"}, text="done")
        st.plotly_chart(fig1, use_container_width=True)

        # Calendar-style trend: daily total completions
        st.subheader("Daily Consistency Trend")
        daily = logs.groupby("log_date")["done"].sum().reset_index()
        daily["log_date"] = pd.to_datetime(daily["log_date"])
        fig2 = px.line(daily, x="log_date", y="done", markers=True,
                        labels={"done": "Habits completed", "log_date": "Date"})
        st.plotly_chart(fig2, use_container_width=True)

        # Per-habit streaks
        st.subheader("Current Streaks")
        habits = get_habits()
        streak_data = []
        for _, h in habits.iterrows():
            streak_data.append({"habit": h["name"], "streak": current_streak(h["id"])})
        st.dataframe(pd.DataFrame(streak_data), use_container_width=True)

    st.divider()
    st.subheader("🙂 Mood Trend (from Journal)")
    if journal_df.empty:
        st.write("Journal entries add karo mood trend dekhne ke liye.")
    else:
        journal_df["log_date"] = pd.to_datetime(journal_df["log_date"])
        fig3 = px.line(journal_df.sort_values("log_date"), x="log_date", y="mood",
                        markers=True, labels={"mood": "Mood (1-10)"})
        st.plotly_chart(fig3, use_container_width=True)
