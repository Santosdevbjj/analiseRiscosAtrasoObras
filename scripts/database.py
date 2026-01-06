import sqlite3
import logging
from pathlib import Path

# Configuração de caminhos
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "users.db"

def init_db():
    """
    Inicializa o banco SQLite local para persistência de preferências.
    Inclui lógica de migração para garantir compatibilidade entre versões.
    """
    try:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            cursor = conn.cursor()
            
            # 1. Criação da tabela base
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                language TEXT DEFAULT 'pt',
                storage_mode TEXT DEFAULT 'SUPABASE'
            )
            """)
            
            # 2. Migração: Adiciona 'language' se não existir (segurança extra)
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'pt'")
            except sqlite3.OperationalError:
                pass # Coluna já existe
                
            # 3. Migração: Adiciona 'storage_mode' se não existir
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN storage_mode TEXT DEFAULT 'SUPABASE'")
            except sqlite3.OperationalError:
                pass # Coluna já existe
                
            conn.commit()
            logging.info("SQLite: Banco de dados inicializado com sucesso.")
    except Exception as e:
        logging.error(f"SQLite: Erro ao inicializar banco: {e}")

def set_language(user_id, lang):
    """Atualiza o idioma. No SQLite, usamos ON CONFLICT para economizar queries."""
    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (user_id, language) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET language=excluded.language
        """, (user_id, lang))
        conn.commit()

def get_language(user_id):
    """Busca o idioma ou retorna 'pt' como fallback."""
    try:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return row[0] if (row and row[0]) else "pt"
    except:
        return "pt"

def set_storage_mode(user_id, mode):
    """Persiste a escolha entre CSV e SUPABASE."""
    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (user_id, storage_mode) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET storage_mode=excluded.storage_mode
        """, (user_id, mode))
        conn.commit()

def get_storage_mode(user_id):
    """Busca o modo ou retorna 'SUPABASE' como padrão."""
    try:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT storage_mode FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return row[0] if (row and row[0]) else "SUPABASE"
    except:
        return "SUPABASE"

# Inicializa o banco ao carregar o módulo para garantir que as tabelas existam
init_db()
