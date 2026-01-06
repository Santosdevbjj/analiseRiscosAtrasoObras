import os
import logging
import sqlite3
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Configuração de Logging Centralizada
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- CONFIGURAÇÃO DE INFRAESTRUTURA ---
# Se DATABASE_URL existir (Supabase), usaremos Postgres para usuários (Persistente no Render)
# Caso contrário, fallback para SQLite (Temporário no Render free)
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")
    engine = create_engine(DATABASE_URL, pool_size=5, max_overflow=10)
    IS_POSTGRES = True
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    DB_PATH = BASE_DIR / "users.db"
    IS_POSTGRES = False

def init_db():
    """Cria a estrutura de dados com timestamps para auditoria."""
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
            with engine.begin() as conn:
                conn.execute(text(query_users))
            logging.info("DB Postgres inicializado com sucesso.")
        else:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(query_users)
            logging.info("DB SQLite inicializado com sucesso.")
    except Exception as e:
        logging.error(f"Erro crítico na inicialização do DB: {e}")

def set_language(user_id: int, lang: str):
    """Insere ou atualiza o idioma com registro de timestamp."""
    query = """
        INSERT INTO users (user_id, language, updated_at) 
        VALUES (:id, :lang, :now)
        ON CONFLICT (user_id) DO UPDATE 
        SET language = EXCLUDED.language, updated_at = EXCLUDED.updated_at;
    """
    params = {"id": user_id, "lang": lang, "now": datetime.now()}
    _execute_query(query, params)

def get_language(user_id: int) -> str:
    """Retorna o idioma salvo ou padrão 'pt' com tratamento de erro."""
    query = "SELECT language FROM users WHERE user_id = :id"
    try:
        result = _execute_query(query, {"id": user_id}, fetch=True)
        return result[0][0] if result else "pt"
    except Exception as e:
        logging.error(f"Falha ao obter idioma para {user_id}: {e}")
        return "pt"

def set_storage_mode(user_id: int, mode: str):
    """Define se o usuário opera via CSV ou Banco de Dados."""
    query = """
        INSERT INTO users (user_id, storage_mode, updated_at) 
        VALUES (:id, :mode, :now)
        ON CONFLICT (user_id) DO UPDATE 
        SET storage_mode = EXCLUDED.storage_mode, updated_at = EXCLUDED.updated_at;
    """
    params = {"id": user_id, "mode": mode, "now": datetime.now()}
    _execute_query(query, params)

def get_storage_mode(user_id: int) -> str:
    """Retorna o modo de armazenamento configurado."""
    query = "SELECT storage_mode FROM users WHERE user_id = :id"
    try:
        result = _execute_query(query, {"id": user_id}, fetch=True)
        return result[0][0] if result else "SUPABASE"
    except Exception as e:
        logging.error(f"Falha ao obter modo para {user_id}: {e}")
        return "SUPABASE"

def _execute_query(query: str, params: dict, fetch: bool = False):
    """Função auxiliar para abstrair a execução entre SQLite e Postgres."""
    if IS_POSTGRES:
        try:
            with engine.connect() as conn:
                result = conn.execute(text(query), params)
                if fetch:
                    return result.fetchall()
                conn.commit()
        except SQLAlchemyError as e:
            logging.error(f"Erro SQLAlchemy: {e}")
            raise
    else:
        # Fallback SQLite para desenvolvimento local
        try:
            with sqlite3.connect(DB_PATH) as conn:
                # Converte sintaxe de :param para ? do SQLite se necessário
                cursor = conn.execute(query.replace(":", "?"), list(params.values()))
                if fetch:
                    return cursor.fetchall()
                conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Erro SQLite: {e}")
            raise

# Inicializa o banco ao carregar o módulo
init_db()
