import sqlite3
from pathlib import Path

# Define o caminho para garantir que o banco seja criado na pasta correta
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "users.db"

def init_db():
    """Inicializa o banco de dados e a tabela se não existirem."""
    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            language TEXT
        )
        """)
        conn.commit()

def set_language(user_id, lang):
    """Insere ou atualiza o idioma do usuário."""
    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO users (user_id, language) VALUES (?, ?)",
            (user_id, lang)
        )
        conn.commit()

def get_language(user_id):
    """Recupera o idioma do usuário."""
    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT language FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        return row[0] if row else None

# Inicializa o banco ao importar o script
init_db()
