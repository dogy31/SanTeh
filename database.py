import sqlite3

conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
id INTEGER PRIMARY KEY AUTOINCREMENT,
telegram_id INTEGER,
code TEXT,
site_user_id TEXT
)
""")

conn.commit()


def save_code(site_user_id, code):
    cursor.execute(
        "INSERT INTO users(site_user_id, code) VALUES (?, ?)",
        (site_user_id, code)
    )
    conn.commit()


def link_telegram(code, telegram_id):
    cursor.execute(
        "UPDATE users SET telegram_id=? WHERE code=?",
        (telegram_id, code)
    )
    conn.commit()


def get_telegram(site_user_id):
    cursor.execute(
        "SELECT telegram_id FROM users WHERE site_user_id=?",
        (site_user_id,)
    )
    return cursor.fetchone()