import sqlite3
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "users.db"

def init_db():
    """Inicializa o banco e as colunas necessárias."""
    try:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    language TEXT DEFAULT 'pt',
                    storage_mode TEXT DEFAULT 'SUPABASE'
                )
            """)
            conn.commit()
    except Exception as e:
        logging.error(f"Erro ao iniciar DB: {e}")

def set_language(user_id, lang):
    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (user_id, language) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET language=excluded.language
        """, (user_id, lang))
        conn.commit()

def get_language(user_id):
    try:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return row[0] if row else "pt"
    except:
        return "pt"

def set_storage_mode(user_id, mode):
    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (user_id, storage_mode) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET storage_mode=excluded.storage_mode
        """, (user_id, mode))
        conn.commit()

def get_storage_mode(user_id):
    try:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT storage_mode FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return row[0] if row else "SUPABASE"
    except:
        return "SUPABASE"

init_db()
