import os
import logging
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Infra
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")
    # Em SQLAlchemy 2.x, pool_size/max_overflow podem ser ignorados dependendo do driver;
    # mantenha se necessário para seu driver específico.
    engine = create_engine(DATABASE_URL, pool_size=5, max_overflow=10, future=True)
    IS_POSTGRES = True
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    DB_PATH = BASE_DIR / "users.db"
    IS_POSTGRES = False

def init_db():
    """Cria tabela users com timestamps."""
    query_users = """
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            language TEXT DEFAULT 'pt',
            storage_mode TEXT DEFAULT 'SUPABASE',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """
    try:
        if IS_POSTGRES:
            # Transacional
            with engine.begin() as conn:
                conn.execute(text(query_users))
            logging.info("DB Postgres inicializado com sucesso.")
        else:
            # SQLite com placeholders nomeados
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(query_users)
            logging.info("DB SQLite inicializado com sucesso.")
    except Exception as e:
        logging.exception("Erro crítico na inicialização do DB")

def _now_utc():
    return datetime.now(timezone.utc)

def set_language(user_id: int, lang: str):
    """Upsert de idioma com updated_at (UTC)."""
    query = """
        INSERT INTO users (user_id, language, updated_at)
        VALUES (:id, :lang, :now)
        ON CONFLICT (user_id) DO UPDATE
        SET language = EXCLUDED.language,
            updated_at = EXCLUDED.updated_at;
    """
    params = {"id": user_id, "lang": lang, "now": _now_utc()}
    _execute_query(query, params)

def get_language(user_id: int) -> str:
    """Retorna idioma ou 'pt'."""
    query = "SELECT language FROM users WHERE user_id = :id"
    try:
        rows = _execute_query(query, {"id": user_id}, fetch=True)
        return rows[0][0] if rows else "pt"
    except Exception:
        logging.exception(f"Falha ao obter idioma para {user_id}")
        return "pt"

def set_storage_mode(user_id: int, mode: str):
    """Upsert de modo com updated_at (UTC)."""
    query = """
        INSERT INTO users (user_id, storage_mode, updated_at)
        VALUES (:id, :mode, :now)
        ON CONFLICT (user_id) DO UPDATE
        SET storage_mode = EXCLUDED.storage_mode,
            updated_at = EXCLUDED.updated_at;
    """
    params = {"id": user_id, "mode": mode, "now": _now_utc()}
    _execute_query(query, params)

def get_storage_mode(user_id: int) -> str:
    """Retorna modo ou 'SUPABASE'."""
    query = "SELECT storage_mode FROM users WHERE user_id = :id"
    try:
        rows = _execute_query(query, {"id": user_id}, fetch=True)
        return rows[0][0] if rows else "SUPABASE"
    except Exception:
        logging.exception(f"Falha ao obter modo para {user_id}")
        return "SUPABASE"

def _execute_query(query: str, params: dict, fetch: bool = False):
    """Execução abstrata para Postgres/SQLite com parametrização correta."""
    if IS_POSTGRES:
        try:
            if fetch:
                with engine.connect() as conn:
                    result = conn.execute(text(query), params)
                    return result.fetchall()
            else:
                # Usa transação para DML
                with engine.begin() as conn:
                    conn.execute(text(query), params)
        except SQLAlchemyError:
            logging.exception("Erro SQLAlchemy")
            raise
    else:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                # Usa placeholders nomeados (:id, :lang) diretamente
                cur = conn.execute(query, params)
                if fetch:
                    return cur.fetchall()
                conn.commit()
        except sqlite3.Error:
            logging.exception("Erro SQLite")
            raise

# Inicialização
init_db()
