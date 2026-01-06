import sqlite3
from pathlib import Path

# Define o caminho para garantir que o banco seja criado na pasta correta
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "users.db"

def init_db():
    """Inicializa o banco de dados e as colunas necessárias para a arquitetura híbrida."""
    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
        cursor = conn.cursor()
        # Criação da tabela com suporte a persistência de preferências
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            language TEXT DEFAULT 'pt',
            storage_mode TEXT DEFAULT 'SUPABASE'
        )
        """)
        
        # Migração segura: Garante que colunas novas existam em bancos já criados no Render
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN storage_mode TEXT DEFAULT 'SUPABASE'")
        except sqlite3.OperationalError:
            pass  # A coluna já existe
            
        conn.commit()

def set_language(user_id, lang):
    """Insere ou atualiza o idioma preferido do usuário."""
    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (user_id, language) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET language=excluded.language
        """, (user_id, lang))
        conn.commit()

def get_language(user_id):
    """Recupera o idioma do usuário ou retorna o padrão 'pt'."""
    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row[0] if (row and row[0]) else "pt"

def set_storage_mode(user_id, mode):
    """Salva a escolha de infraestrutura (CSV ou SUPABASE) do usuário."""
    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (user_id, storage_mode) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET storage_mode=excluded.storage_mode
        """, (user_id, mode))
        conn.commit()

def get_storage_mode(user_id):
    """Recupera o modo de armazenamento preferido ou retorna 'SUPABASE' como padrão."""
    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT storage_mode FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row[0] if (row and row[0]) else "SUPABASE"

# Executa a inicialização ao carregar o módulo
init_db()
