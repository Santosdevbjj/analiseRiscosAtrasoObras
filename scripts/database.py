import sqlite3

conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    language TEXT
)
""")
conn.commit()


def set_language(user_id, lang):
    cursor.execute(
        "INSERT OR REPLACE INTO users (user_id, language) VALUES (?, ?)",
        (user_id, lang)
    )
    conn.commit()


def get_language(user_id):
    cursor.execute(
        "SELECT language FROM users WHERE user_id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    return row[0] if row else None
