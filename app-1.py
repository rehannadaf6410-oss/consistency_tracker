"""
ConsistencyHub - Habit Tracker, Journal & Analytics
College Project | Streamlit Community Cloud ready

Run locally:  streamlit run app.py
Default admin login: username = admin | password = admin123 (change it after first login!)
"""

import streamlit as st
import sqlite3
import pandas as pd
import datetime
import hashlib
import secrets
import random
import plotly.express as px

# =========================================================
# APP CONFIG
# =========================================================
DB_PATH = "tracker.db"
APP_NAME = "ConsistencyHub"

st.set_page_config(page_title="ConsistencyHub | Habit Tracker", page_icon="🔥", layout="wide")

QUOTES = [
    "Small daily improvements lead to staggering long-term results.",
    "Motivation gets you started. Habit keeps you going.",
    "You don't have to be great to start, but you have to start to be great.",
    "Success is the sum of small efforts repeated day in and day out.",
    "We are what we repeatedly do. Excellence, then, is not an act, but a habit.",
    "The secret of your future is hidden in your daily routine.",
    "Discipline is choosing between what you want now and what you want most.",
    "Consistency is what transforms average into excellence.",
]

CATEGORIES = ["Health & Fitness", "Study & Learning", "Productivity", "Mindfulness", "Personal", "Other"]

MOOD_EMOJI = {1: "😞", 2: "😔", 3: "😕", 4: "😐", 5: "🙂", 6: "😊", 7: "😄", 8: "😁", 9: "🤩", 10: "🥳"}

# =========================================================
# CUSTOM STYLING
# =========================================================
def inject_css():
    st.markdown("""
        <style>
        .hero {
            padding: 2.2rem 2rem;
            border-radius: 16px;
            background: linear-gradient(135deg, #FF7A45 0%, #FF5722 45%, #D84315 100%);
            color: white;
            margin-bottom: 1.2rem;
        }
        .hero h1 { margin: 0; font-size: 2.3rem; }
        .hero p { font-size: 1.05rem; opacity: 0.95; margin-top: 0.4rem; }
        .metric-card {
            background: #FFF3E0;
            border-radius: 12px;
            padding: 0.9rem 1rem;
            border: 1px solid #FFD7B5;
        }
        .badge {
            display: inline-block;
            padding: 0.15rem 0.6rem;
            border-radius: 999px;
            background: #FFE0B2;
            color: #E65100;
            font-size: 0.78rem;
            font-weight: 600;
            margin-left: 0.4rem;
        }
        .quote-box {
            background: #FFF8E1;
            border-left: 5px solid #FFB300;
            padding: 0.8rem 1rem;
            border-radius: 8px;
            font-style: italic;
        }
        .guest-banner {
            background: #FFEBEE;
            border-left: 5px solid #E53935;
            padding: 0.7rem 1rem;
            border-radius: 8px;
            margin-bottom: 1rem;
        }
        </style>
    """, unsafe_allow_html=True)


# =========================================================
# DATABASE SETUP
# =========================================================
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.sha256((salt + password).encode()).hexdigest()
    return digest, salt


def verify_password(password, salt, digest):
    return hashlib.sha256((salt + password).encode()).hexdigest() == digest


def migrate_schema():
    """Fix databases created by an older version of this app (missing user_id
    columns on habits/journal). Safe no-op on a fresh or already-current DB."""
    conn = get_conn()
    c = conn.cursor()
    outdated_habits = False
    for table in ("habits", "journal"):
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if c.fetchone():
            cols = [r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]
            if "user_id" not in cols:
                c.execute(f"DROP TABLE {table}")
                if table == "habits":
                    outdated_habits = True
    if outdated_habits:
        # habit_logs referenced the old habits table's ids; clear it too so
        # ids don't collide with the freshly recreated habits table.
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='habit_logs'")
        if c.fetchone():
            c.execute("DROP TABLE habit_logs")
    conn.commit()
    conn.close()


def init_db():
    migrate_schema()
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            salt TEXT,
            role TEXT DEFAULT 'user',
            created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            category TEXT DEFAULT 'Other',
            target_days_per_week INTEGER DEFAULT 7,
            created_at TEXT,
            UNIQUE(user_id, name)
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
            user_id INTEGER,
            log_date TEXT,
            mood INTEGER,
            entry TEXT,
            UNIQUE(user_id, log_date)
        )
    """)
    conn.commit()

    c.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
    if c.fetchone()[0] == 0:
        h, s = hash_password("admin123")
        c.execute(
            "INSERT INTO users (username, password_hash, salt, role, created_at) VALUES (?,?,?,?,?)",
            ("admin", h, s, "admin", str(datetime.datetime.now()))
        )
        conn.commit()
    conn.close()


# =========================================================
# AUTH FUNCTIONS
# =========================================================
def create_user(username, password, role="user"):
    username = username.strip()
    if not username or not password:
        return False, "Username and password cannot be empty."
    if len(password) < 4:
        return False, "Password must be at least 4 characters."
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (username,))
    if c.fetchone():
        conn.close()
        return False, "That username is already taken."
    h, s = hash_password(password)
    c.execute(
        "INSERT INTO users (username, password_hash, salt, role, created_at) VALUES (?,?,?,?,?)",
        (username, h, s, role, str(datetime.datetime.now()))
    )
    conn.commit()
    conn.close()
    return True, "Account created! Please log in."


def authenticate(username, password):
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(username,))
    conn.close()
    if df.empty:
        return None
    row = df.iloc[0]
    if verify_password(password, row["salt"], row["password_hash"]):
        return {"id": int(row["id"]), "username": row["username"], "role": row["role"]}
    return None


def update_password(user_id, old_password, new_password):
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM users WHERE id=?", conn, params=(user_id,))
    if df.empty:
        conn.close()
        return False, "User not found."
    row = df.iloc[0]
    if not verify_password(old_password, row["salt"], row["password_hash"]):
        conn.close()
        return False, "Current password is incorrect."
    if len(new_password) < 4:
        conn.close()
        return False, "New password must be at least 4 characters."
    h, s = hash_password(new_password)
    conn.execute("UPDATE users SET password_hash=?, salt=? WHERE id=?", (h, s, user_id))
    conn.commit()
    conn.close()
    return True, "Password updated successfully."


def get_all_users():
    conn = get_conn()
    df = pd.read_sql("SELECT id, username, role, created_at FROM users ORDER BY id", conn)
    conn.close()
    return df


def delete_user(user_id):
    conn = get_conn()
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.execute("DELETE FROM habits WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM journal WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


# =========================================================
# GUEST-AWARE DATA LAYER
# (guest data lives only in st.session_state and disappears
#  when the browser tab is closed/refreshed)
# =========================================================
def is_guest(user):
    return user is not None and user.get("role") == "guest"


def add_habit(user, name, category, target_days=7):
    name = name.strip()
    if not name:
        return False, "Please enter a habit name."
    if is_guest(user):
        if any(h["name"].lower() == name.lower() for h in st.session_state.guest_habits):
            return False, "You already have a habit with that name."
        new_id = st.session_state.guest_next_id
        st.session_state.guest_next_id += 1
        st.session_state.guest_habits.append(
            {"id": new_id, "name": name, "category": category, "target_days_per_week": target_days}
        )
        return True, "Habit added!"
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO habits (user_id, name, category, target_days_per_week, created_at) VALUES (?,?,?,?,?)",
            (user["id"], name, category, target_days, str(datetime.datetime.now()))
        )
        conn.commit()
        ok, msg = True, "Habit added!"
    except sqlite3.IntegrityError:
        ok, msg = False, "You already have a habit with that name."
    conn.close()
    return ok, msg


def get_habits(user):
    if is_guest(user):
        return pd.DataFrame(st.session_state.guest_habits,
                             columns=["id", "name", "category", "target_days_per_week"])
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM habits WHERE user_id=? ORDER BY id", conn, params=(user["id"],))
    conn.close()
    return df


def delete_habit(user, habit_id):
    if is_guest(user):
        st.session_state.guest_habits = [h for h in st.session_state.guest_habits if h["id"] != habit_id]
        st.session_state.guest_logs = [l for l in st.session_state.guest_logs if l["habit_id"] != habit_id]
        return
    conn = get_conn()
    conn.execute("DELETE FROM habits WHERE id=? AND user_id=?", (habit_id, user["id"]))
    conn.execute("DELETE FROM habit_logs WHERE habit_id=?", (habit_id,))
    conn.commit()
    conn.close()


def mark_habit(user, habit_id, log_date, done):
    if is_guest(user):
        for l in st.session_state.guest_logs:
            if l["habit_id"] == habit_id and l["log_date"] == log_date:
                l["done"] = int(done)
                return
        st.session_state.guest_logs.append({"habit_id": habit_id, "log_date": log_date, "done": int(done)})
        return
    conn = get_conn()
    conn.execute("""
        INSERT INTO habit_logs (habit_id, log_date, done) VALUES (?,?,?)
        ON CONFLICT(habit_id, log_date) DO UPDATE SET done=excluded.done
    """, (habit_id, log_date, int(done)))
    conn.commit()
    conn.close()


def get_logs_raw(user):
    if is_guest(user):
        return pd.DataFrame(st.session_state.guest_logs, columns=["habit_id", "log_date", "done"])
    conn = get_conn()
    df = pd.read_sql("""
        SELECT hl.habit_id, hl.log_date, hl.done
        FROM habit_logs hl JOIN habits h ON h.id = hl.habit_id
        WHERE h.user_id=?
    """, conn, params=(user["id"],))
    conn.close()
    return df


def get_logs(user):
    habits = get_habits(user)
    logs = get_logs_raw(user)
    if habits.empty or logs.empty:
        return pd.DataFrame(columns=["log_date", "habit", "done", "category"])
    merged = logs.merge(habits, left_on="habit_id", right_on="id", suffixes=("", "_h"))
    merged = merged.rename(columns={"name": "habit"})
    return merged[["log_date", "habit", "done", "category"]]


def get_log_value(user, habit_id, log_date):
    logs = get_logs_raw(user)
    if logs.empty:
        return False
    row = logs[(logs["habit_id"] == habit_id) & (logs["log_date"] == log_date)]
    return bool(row.iloc[0]["done"]) if not row.empty else False


def save_journal(user, log_date, mood, entry):
    if is_guest(user):
        for j in st.session_state.guest_journal:
            if j["log_date"] == log_date:
                j["mood"] = mood
                j["entry"] = entry
                return
        st.session_state.guest_journal.append({"log_date": log_date, "mood": mood, "entry": entry})
        return
    conn = get_conn()
    conn.execute("""
        INSERT INTO journal (user_id, log_date, mood, entry) VALUES (?,?,?,?)
        ON CONFLICT(user_id, log_date) DO UPDATE SET mood=excluded.mood, entry=excluded.entry
    """, (user["id"], log_date, mood, entry))
    conn.commit()
    conn.close()


def get_journal(user):
    if is_guest(user):
        df = pd.DataFrame(st.session_state.guest_journal, columns=["log_date", "mood", "entry"])
        return df.sort_values("log_date") if not df.empty else df
    conn = get_conn()
    df = pd.read_sql("SELECT log_date, mood, entry FROM journal WHERE user_id=? ORDER BY log_date",
                      conn, params=(user["id"],))
    conn.close()
    return df


def current_streak(user, habit_id):
    logs = get_logs_raw(user)
    if logs.empty:
        return 0
    df = logs[logs["habit_id"] == habit_id].sort_values("log_date", ascending=False)
    streak = 0
    today = datetime.date.today()
    for _, row in df.iterrows():
        expected = today - datetime.timedelta(days=streak)
        if str(row["log_date"]) == str(expected) and row["done"] == 1:
            streak += 1
        else:
            break
    return streak


def best_streak(user, habit_id):
    logs = get_logs_raw(user)
    if logs.empty:
        return 0
    df = logs[(logs["habit_id"] == habit_id) & (logs["done"] == 1)].sort_values("log_date")
    if df.empty:
        return 0
    dates = pd.to_datetime(df["log_date"]).tolist()
    best = cur = 1
    for i in range(1, len(dates)):
        if (dates[i] - dates[i - 1]).days == 1:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return best


# =========================================================
# SESSION STATE INIT
# =========================================================
def init_session_state():
    defaults = {
        "auth_user": None,
        "guest_habits": [],
        "guest_logs": [],
        "guest_journal": [],
        "guest_next_id": 1,
        "auth_mode": "Login",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def do_logout():
    st.session_state.auth_user = None
    st.session_state.guest_habits = []
    st.session_state.guest_logs = []
    st.session_state.guest_journal = []
    st.session_state.guest_next_id = 1


# =========================================================
# LANDING PAGE (logged-out)
# =========================================================
def render_landing():
    st.markdown(f"""
        <div class="hero">
            <h1>🔥 {APP_NAME}</h1>
            <p>Build habits that stick. Track your consistency, journal your journey,
            and see the story behind your data.</p>
        </div>
    """, unsafe_allow_html=True)

    tab_login, tab_signup, tab_guest, tab_about = st.tabs(
        ["🔐 Login", "🆕 Sign Up", "👀 Try as Guest", "📘 About This Project"]
    )

    with tab_login:
        st.subheader("Welcome back")
        with st.form("login_form"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)
        if submitted:
            user = authenticate(u.strip(), p)
            if user:
                st.session_state.auth_user = user
                st.success(f"Welcome, {user['username']}!")
                st.rerun()
            else:
                st.error("Invalid username or password.")
        st.caption("Default admin account for demo: **admin / admin123** (please change after login)")

    with tab_signup:
        st.subheader("Create a free account")
        st.caption("A registered account saves your data permanently across sessions.")
        with st.form("signup_form"):
            u2 = st.text_input("Choose a username")
            p2 = st.text_input("Choose a password", type="password")
            p3 = st.text_input("Confirm password", type="password")
            submitted2 = st.form_submit_button("Create Account", use_container_width=True)
        if submitted2:
            if p2 != p3:
                st.error("Passwords do not match.")
            else:
                ok, msg = create_user(u2, p2, role="user")
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

    with tab_guest:
        st.subheader("Explore without signing up")
        st.info("Guest mode lets you try every feature instantly. "
                "⚠️ Guest data is **temporary** — it lives only in this browser session "
                "and disappears when you close or refresh the tab.")
        if st.button("Continue as Guest", use_container_width=True):
            st.session_state.auth_user = {"id": None, "username": "Guest", "role": "guest"}
            st.rerun()

    with tab_about:
        render_about_content()


def render_about_content():
    st.markdown("### 🎯 Problem Statement")
    st.write(
        "Most people who want to build better habits fail not because they lack motivation, "
        "but because they lack **visibility and accountability**. Sticky notes, memory, and "
        "generic to-do apps don't show the bigger picture — how consistent you actually are, "
        "how your mood connects to your habits, or how close you are to breaking your streak."
    )
    st.markdown("### 💡 Our Solution")
    st.write(
        f"**{APP_NAME}** combines three things that are usually separate — daily habit tracking, "
        "mood journaling, and data analytics — into one simple dashboard, so you can see not just "
        "*what* you did, but *how it made you feel* and *how consistent you're really being*."
    )
    st.markdown("### ✨ Key Features")
    st.markdown("""
    - 🔐 **Secure login system** with hashed passwords, plus Guest and Admin roles
    - ✅ **Daily habit tracker** with categories, weekly targets, and live streaks
    - 📔 **Mood journal** to log how each day felt, alongside your habits
    - 📊 **Comprehensive analytics** — completion rates, trends, heatmaps, mood correlation
    - 🏆 **Achievement badges** for streak milestones
    - 🛠️ **Admin dashboard** with a platform-wide leaderboard and user management
    - 📥 **CSV export** of your own data at any time
    """)
    st.markdown("### 🧭 How To Use")
    st.markdown("""
    1. **Sign up** for an account (or click *Try as Guest* to explore instantly).
    2. Go to **Habit Tracker** → add habits you want to build (e.g. *Read 20 pages*, *Gym*).
    3. Every day, come back and **tick off** the habits you completed.
    4. Visit **Journal** to write a short note about your day and rate your mood.
    5. Open **Analytics** to see charts, streaks, and badges based on your history.
    6. If you're an **Admin**, use the **Admin Panel** to monitor all users.
    """)
    st.markdown("### 🧱 Tech Stack")
    st.markdown("`Python` · `Streamlit` · `SQLite` · `Pandas` · `Plotly`")
    st.markdown("### 🚀 Future Scope")
    st.markdown("""
    - Migrate storage from SQLite to a hosted database (e.g. Postgres/Supabase) for true persistence
    - Email/push reminders for pending habits
    - Social features — share streaks with friends, group challenges
    """)


# =========================================================
# HOME PAGE
# =========================================================
def render_home(user):
    hour = datetime.datetime.now().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    st.markdown(f"## {greeting}, {user['username']}! 👋")

    quote = QUOTES[datetime.date.today().toordinal() % len(QUOTES)]
    st.markdown(f'<div class="quote-box">💬 "{quote}"</div>', unsafe_allow_html=True)
    st.write("")

    habits = get_habits(user)
    today_str = str(datetime.date.today())
    journal_df = get_journal(user)

    total_habits = len(habits)
    done_today = 0
    if not habits.empty:
        done_today = sum(get_log_value(user, hid, today_str) for hid in habits["id"])

    best_overall = 0
    if not habits.empty:
        best_overall = max((current_streak(user, hid) for hid in habits["id"]), default=0)

    today_mood = None
    if not journal_df.empty:
        row = journal_df[journal_df["log_date"] == today_str]
        if not row.empty:
            today_mood = int(row.iloc[0]["mood"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Habits", total_habits)
    c2.metric("Done Today", f"{done_today}/{total_habits}" if total_habits else "0/0")
    c3.metric("Best Current Streak", f"{best_overall} 🔥")
    c4.metric("Today's Mood", f"{MOOD_EMOJI.get(today_mood,'—')} {today_mood or ''}")

    st.divider()
    if total_habits == 0:
        st.info("You haven't added any habits yet. Go to **Habit Tracker** in the sidebar to add your first one!")
    else:
        st.subheader("✅ Today's Checklist (preview)")
        for _, h in habits.iterrows():
            val = get_log_value(user, h["id"], today_str)
            icon = "✅" if val else "⬜"
            st.write(f"{icon} {h['name']}  ·  *{h['category']}*")
        st.caption("Head to the **Habit Tracker** tab to check items off for today.")


# =========================================================
# HABIT TRACKER PAGE
# =========================================================
def render_tracker(user):
    st.title("✅ Daily Habit Tracker")

    if is_guest(user):
        st.markdown('<div class="guest-banner">👀 You\'re in <b>Guest Mode</b> — '
                    'this data will be lost when you close or refresh the tab. '
                    'Sign up anytime to keep it permanently.</div>', unsafe_allow_html=True)

    with st.expander("➕ Add a new habit"):
        with st.form("add_habit_form", clear_on_submit=True):
            name = st.text_input("Habit name (e.g. Read 20 pages, Gym, Drink water)")
            colA, colB = st.columns(2)
            category = colA.selectbox("Category", CATEGORIES)
            target = colB.slider("Target days / week", 1, 7, 7)
            add_clicked = st.form_submit_button("Add Habit")
        if add_clicked:
            ok, msg = add_habit(user, name, category, target)
            (st.success if ok else st.warning)(msg)
            if ok:
                st.rerun()

    habits = get_habits(user)
    today_str = str(datetime.date.today())

    if habits.empty:
        st.info("No habits yet — use the box above to add your first one. 🌱")
        return

    st.subheader(f"Today — {today_str}")
    for _, h in habits.iterrows():
        col1, col2, col3, col4 = st.columns([3, 1.3, 1.2, 0.6])
        with col1:
            current_val = get_log_value(user, h["id"], today_str)
            done = st.checkbox(f"{h['name']}", value=current_val, key=f"chk_{h['id']}")
            st.markdown(f'<span class="badge">{h["category"]}</span>', unsafe_allow_html=True)
        with col2:
            st.metric("Streak", f"{current_streak(user, h['id'])} 🔥", label_visibility="collapsed")
        with col3:
            last7 = get_logs_raw(user)
            last7_count = 0
            if not last7.empty:
                cutoff = datetime.date.today() - datetime.timedelta(days=6)
                sub = last7[(last7["habit_id"] == h["id"]) & (last7["done"] == 1)]
                sub = sub[pd.to_datetime(sub["log_date"]).dt.date >= cutoff]
                last7_count = len(sub)
            st.caption(f"This week: {last7_count}/{h['target_days_per_week']} target")
        with col4:
            if st.button("🗑️", key=f"del_{h['id']}", help="Delete this habit"):
                delete_habit(user, h["id"])
                st.rerun()

        if done != current_val:
            mark_habit(user, h["id"], today_str, done)
            st.rerun()


# =========================================================
# JOURNAL PAGE
# =========================================================
def render_journal(user):
    st.title("📔 Daily Journal")

    if is_guest(user):
        st.markdown('<div class="guest-banner">👀 Guest Mode — journal entries reset when you leave.</div>',
                     unsafe_allow_html=True)

    today_str = str(datetime.date.today())
    journal_df = get_journal(user)
    existing = journal_df[journal_df["log_date"] == today_str] if not journal_df.empty else journal_df

    default_mood = int(existing["mood"].values[0]) if not existing.empty else 5
    default_entry = existing["entry"].values[0] if not existing.empty else ""

    mood = st.slider("How was your mood today? (1 = rough, 10 = amazing)", 1, 10, default_mood)
    st.write(f"Feeling: {MOOD_EMOJI.get(mood,'')}")
    entry = st.text_area("What happened today? How did it go?", value=default_entry, height=180)

    if st.button("💾 Save Journal Entry", use_container_width=True):
        save_journal(user, today_str, mood, entry)
        st.success("Saved!")
        st.rerun()

    st.divider()
    st.subheader("📖 Past Entries")
    journal_df = get_journal(user)
    if journal_df.empty:
        st.write("No entries yet — write your first one above.")
    else:
        for _, row in journal_df.sort_values("log_date", ascending=False).iterrows():
            with st.expander(f"{MOOD_EMOJI.get(int(row['mood']),'')} {row['log_date']} — Mood: {row['mood']}/10"):
                st.write(row["entry"] if row["entry"] else "_(no notes)_")


# =========================================================
# ANALYTICS PAGE
# =========================================================
def render_analytics(user):
    st.title("📊 Analytics")

    habits = get_habits(user)
    logs = get_logs(user)
    journal_df = get_journal(user)

    if habits.empty:
        st.info("Add some habits and start tracking to unlock analytics.")
        return

    # ---- Overview metrics ----
    completion_rate = round(logs["done"].mean() * 100, 1) if not logs.empty else 0.0
    best_overall = max((best_streak(user, hid) for hid in habits["id"]), default=0)
    current_overall = max((current_streak(user, hid) for hid in habits["id"]), default=0)
    avg_mood = round(journal_df["mood"].mean(), 1) if not journal_df.empty else None

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Habits", len(habits))
    c2.metric("Overall Completion", f"{completion_rate}%")
    c3.metric("Current Best Streak", f"{current_overall} 🔥")
    c4.metric("All-Time Best Streak", f"{best_overall} 🏆")
    c5.metric("Avg Mood", f"{avg_mood if avg_mood is not None else '—'}")

    st.divider()

    # ---- Completion rate per habit ----
    st.subheader("Habit Completion Rate")
    if not logs.empty:
        summary = logs.groupby("habit")["done"].mean().reset_index()
        summary["done"] = (summary["done"] * 100).round(1)
        fig1 = px.bar(summary, x="habit", y="done", labels={"done": "Completion %"}, text="done",
                      color="done", color_continuous_scale="Oranges")
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.caption("No log data yet.")

    # ---- Daily trend ----
    st.subheader("Daily Consistency Trend")
    if not logs.empty:
        daily = logs.groupby("log_date")["done"].sum().reset_index()
        daily["log_date"] = pd.to_datetime(daily["log_date"])
        fig2 = px.line(daily, x="log_date", y="done", markers=True,
                        labels={"done": "Habits completed", "log_date": "Date"})
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.caption("No log data yet.")

    # ---- 30-day heatmap ----
    st.subheader("Last 30 Days Heatmap")
    if not logs.empty:
        end = datetime.date.today()
        start = end - datetime.timedelta(days=29)
        window = logs.copy()
        window["log_date"] = pd.to_datetime(window["log_date"])
        window = window[(window["log_date"].dt.date >= start) & (window["log_date"].dt.date <= end)]
        if not window.empty:
            pivot = window.pivot_table(index="habit", columns="log_date", values="done", aggfunc="max", fill_value=0)
            fig_hm = px.imshow(pivot, color_continuous_scale="Oranges", aspect="auto",
                                labels=dict(x="Date", y="Habit", color="Done"))
            st.plotly_chart(fig_hm, use_container_width=True)
        else:
            st.caption("Not enough recent data for a heatmap yet.")
    else:
        st.caption("No log data yet.")

    # ---- Streaks table + achievements ----
    st.subheader("🏆 Streaks & Achievements")
    rows = []
    for _, h in habits.iterrows():
        cs = current_streak(user, h["id"])
        bs = best_streak(user, h["id"])
        badge = "—"
        if bs >= 100:
            badge = "💎 Century Club"
        elif bs >= 30:
            badge = "🏆 30-Day Champion"
        elif bs >= 7:
            badge = "⭐ Week Warrior"
        elif bs >= 3:
            badge = "🔥 3-Day Streak"
        rows.append({"Habit": h["name"], "Current Streak": cs, "Best Streak": bs, "Badge": badge})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ---- Category breakdown ----
    st.subheader("Category Breakdown")
    if not habits.empty:
        cat_counts = habits["category"].value_counts().reset_index()
        cat_counts.columns = ["category", "count"]
        fig_cat = px.pie(cat_counts, names="category", values="count", hole=0.4)
        st.plotly_chart(fig_cat, use_container_width=True)

    st.divider()

    # ---- Mood trend & correlation ----
    st.subheader("🙂 Mood Trend")
    if journal_df.empty:
        st.write("Add journal entries to see your mood trend.")
    else:
        jdf = journal_df.copy()
        jdf["log_date"] = pd.to_datetime(jdf["log_date"])
        fig3 = px.line(jdf.sort_values("log_date"), x="log_date", y="mood", markers=True,
                        labels={"mood": "Mood (1-10)"})
        st.plotly_chart(fig3, use_container_width=True)

        if not logs.empty:
            st.subheader("Mood vs. Habit Completion")
            daily_completion = logs.copy()
            daily_completion["log_date"] = pd.to_datetime(daily_completion["log_date"])
            daily_completion = daily_completion.groupby("log_date")["done"].mean().reset_index()
            daily_completion["done"] = daily_completion["done"] * 100
            merged = pd.merge(jdf, daily_completion, on="log_date", how="inner")
            if not merged.empty:
                fig4 = px.scatter(merged, x="done", y="mood",
                                   labels={"done": "Completion % that day", "mood": "Mood (1-10)"},
                                   trendline=None)
                st.plotly_chart(fig4, use_container_width=True)
                st.caption("Each point is a day where you logged both habits and a mood entry.")
            else:
                st.caption("Log habits and journal on the same days to see this correlation.")

    st.divider()
    st.subheader("📥 Export Your Data")
    colx, coly = st.columns(2)
    if not logs.empty:
        colx.download_button("Download Habit Logs (CSV)", logs.to_csv(index=False),
                              file_name="habit_logs.csv", mime="text/csv", use_container_width=True)
    if not journal_df.empty:
        coly.download_button("Download Journal (CSV)", journal_df.to_csv(index=False),
                              file_name="journal.csv", mime="text/csv", use_container_width=True)


# =========================================================
# ADMIN PANEL
# =========================================================
def render_admin(user):
    st.title("🛠️ Admin Panel")
    st.caption("Visible only to admin accounts.")

    users_df = get_all_users()
    conn = get_conn()
    total_habits = pd.read_sql("SELECT COUNT(*) as n FROM habits", conn).iloc[0]["n"]
    total_logs = pd.read_sql("SELECT COUNT(*) as n FROM habit_logs", conn).iloc[0]["n"]
    total_journal = pd.read_sql("SELECT COUNT(*) as n FROM journal", conn).iloc[0]["n"]
    conn.close()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Registered Users", len(users_df))
    c2.metric("Total Habits Created", int(total_habits))
    c3.metric("Total Logs Recorded", int(total_logs))
    c4.metric("Journal Entries", int(total_journal))

    st.divider()
    st.subheader("🏅 Consistency Leaderboard")
    leaderboard = []
    for _, u in users_df.iterrows():
        fake_user = {"id": int(u["id"]), "username": u["username"], "role": u["role"]}
        u_habits = get_habits(fake_user)
        u_logs = get_logs_raw(fake_user)
        rate = round(u_logs["done"].mean() * 100, 1) if not u_logs.empty else 0.0
        best = max((best_streak(fake_user, hid) for hid in u_habits["id"]), default=0) if not u_habits.empty else 0
        leaderboard.append({"Username": u["username"], "Role": u["role"],
                             "Habits": len(u_habits), "Completion %": rate, "Best Streak": best})
    lb_df = pd.DataFrame(leaderboard).sort_values("Completion %", ascending=False)
    st.dataframe(lb_df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("👥 User Management")
    admin_count = int((users_df["role"] == "admin").sum())
    for _, u in users_df.iterrows():
        colu1, colu2, colu3, colu4 = st.columns([2, 1, 2, 1])
        colu1.write(f"**{u['username']}**")
        colu2.write(f"`{u['role']}`")
        colu3.caption(str(u["created_at"]))
        disable_delete = (u["id"] == user["id"]) or (u["role"] == "admin" and admin_count <= 1)
        if colu4.button("Delete", key=f"deluser_{u['id']}", disabled=disable_delete):
            delete_user(int(u["id"]))
            st.rerun()
    st.caption("You can't delete your own account or the last remaining admin.")


# =========================================================
# ACCOUNT / SIDEBAR
# =========================================================
def render_sidebar(user):
    st.sidebar.markdown(f"### 👤 {user['username']}")
    st.sidebar.markdown(f"Role: `{user['role']}`")

    pages = ["🏠 Home", "✅ Habit Tracker", "📔 Journal", "📊 Analytics", "📘 About / Help"]
    if user["role"] == "admin":
        pages.insert(4, "🛠️ Admin Panel")

    choice = st.sidebar.radio("Navigate", pages)

    if not is_guest(user):
        with st.sidebar.expander("⚙️ Account settings"):
            with st.form("pw_form"):
                old_pw = st.text_input("Current password", type="password")
                new_pw = st.text_input("New password", type="password")
                pw_submit = st.form_submit_button("Change Password")
            if pw_submit:
                ok, msg = update_password(user["id"], old_pw, new_pw)
                (st.success if ok else st.error)(msg)

    st.sidebar.divider()
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        do_logout()
        st.rerun()

    return choice


# =========================================================
# MAIN
# =========================================================
def main():
    init_db()
    init_session_state()
    inject_css()

    user = st.session_state.auth_user
    if user is None:
        render_landing()
        return

    choice = render_sidebar(user)

    if choice == "🏠 Home":
        render_home(user)
    elif choice == "✅ Habit Tracker":
        render_tracker(user)
    elif choice == "📔 Journal":
        render_journal(user)
    elif choice == "📊 Analytics":
        render_analytics(user)
    elif choice == "🛠️ Admin Panel":
        render_admin(user)
    elif choice == "📘 About / Help":
        render_about_content()


if __name__ == "__main__":
    main()
