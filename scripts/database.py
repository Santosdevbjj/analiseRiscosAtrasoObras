import sqlite3
import logging
from pathlib import Path

# Configuração de caminhos absoluta para o ambiente Render
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "users.db"

# Configuração básica de log para debugar no Render
logging.basicConfig(level=logging.INFO)

def init_db():
    """
    Inicializa o banco SQLite local. 
    Usa PRAGMA journal_mode=WAL para permitir leitura/escrita simultânea sem travar.
    """
    try:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            # Melhora a performance de escrita e evita 'Database is locked'
            conn.execute("PRAGMA journal_mode=WAL;")
            cursor = conn.cursor()
            
            # 1. Criação da tabela base
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                language TEXT DEFAULT 'pt',
                storage_mode TEXT DEFAULT 'SUPABASE'
            )
            """)
            
            # 2. Migrações de segurança para colunas existentes
            columns = [info[1] for info in cursor.execute("PRAGMA table_info(users)").fetchall()]
            
            if 'language' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'pt'")
            if 'storage_mode' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN storage_mode TEXT DEFAULT 'SUPABASE'")
                
            conn.commit()
            logging.info(f"SQLite: Banco de dados inicializado em {DB_PATH}")
    except Exception as e:
        logging.error(f"SQLite: Erro fatal na inicialização: {e}")

def set_language(user_id, lang):
    """Atualiza o idioma do usuário garantindo a persistência imediata."""
    try:
        with sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (user_id, language) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET language=excluded.language
            """, (user_id, lang))
            conn.commit()
            logging.info(f"SQLite: Idioma definido para {lang} para o usuário {user_id}")
    except Exception as e:
        logging.error(f"SQLite: Erro ao salvar idioma: {e}")

def get_language(user_id):
    """Busca o idioma. Retorna 'pt' se o usuário não for encontrado."""
    try:
        with sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row and row[0]:
                return row[0]
    except Exception as e:
        logging.error(f"SQLite: Erro ao buscar idioma: {e}")
    return "pt"

def set_storage_mode(user_id, mode):
    """Salva se o usuário prefere CSV ou SUPABASE."""
    try:
        with sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (user_id, storage_mode) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET storage_mode=excluded.storage_mode
            """, (user_id, mode))
            conn.commit()
            logging.info(f"SQLite: Modo {mode} salvo para o usuário {user_id}")
    except Exception as e:
        logging.error(f"SQLite: Erro ao salvar storage_mode: {e}")

def get_storage_mode(user_id):
    """Busca a preferência de infraestrutura."""
    try:
        with sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT storage_mode FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row and row[0]:
                return row[0]
    except Exception as e:
        logging.error(f"SQLite: Erro ao buscar storage_mode: {e}")
    return "SUPABASE"

# Garante a criação do banco ao importar
init_db()
