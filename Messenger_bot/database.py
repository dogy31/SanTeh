import sqlite3

conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
id INTEGER PRIMARY KEY AUTOINCREMENT,
telegram_id INTEGER,
max_id INTEGER,
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
    # Return site_user_id if update was successful
    cursor.execute(
        "SELECT site_user_id FROM users WHERE code=? AND telegram_id=?",
        (code, telegram_id)
    )
    result = cursor.fetchone()
    return result[0] if result else None


def link_max(code, max_id):
    cursor.execute(
        "UPDATE users SET max_id=? WHERE code=?",
        (max_id, code)
    )
    conn.commit()
    # Return site_user_id if update was successful
    cursor.execute(
        "SELECT site_user_id FROM users WHERE code=? AND max_id=?",
        (code, max_id)
    )
    result = cursor.fetchone()
    return result[0] if result else None


def get_telegram(site_user_id):
    cursor.execute(
        "SELECT telegram_id FROM users WHERE site_user_id=? AND telegram_id IS NOT NULL ORDER BY id DESC LIMIT 1",
        (site_user_id,)
    )
    return cursor.fetchone()


def get_max(site_user_id):
    cursor.execute(
        "SELECT max_id FROM users WHERE site_user_id=? AND max_id IS NOT NULL ORDER BY id DESC LIMIT 1",
        (site_user_id,)
    )
    return cursor.fetchone()