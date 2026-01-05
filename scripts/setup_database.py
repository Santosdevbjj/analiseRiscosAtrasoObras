import pandas as pd
import os
import logging
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Configuração de logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def carregar_dados_supabase():
    load_dotenv()
    
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        logging.error("❌ Erro: DATABASE_URL não encontrada!")
        return

    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    try:
        # Aumentamos o pool_size para manter a conexão estável durante a carga pesada
        engine = create_engine(db_url, pool_pre_ping=True)
        path_arquivo = "data/processed/df_mestre_consolidado.csv.gz"
        
        logging.info(f"📂 Abrindo arquivo comprimido: {path_arquivo}")

        chunk_size = 10000 
        total_registros = 0
        primeiro_lote = True

        # O 'engine.connect()' garante que a conexão está ativa
        with engine.connect() as conn:
            for chunk in pd.read_csv(path_arquivo, compression='gzip', chunksize=chunk_size):
                
                # Garantimos que os nomes das colunas estão em minúsculo para bater com o SQL
                chunk.columns = [c.lower() for c in chunk.columns]
                
                metodo_sql = 'replace' if primeiro_lote else 'append'
                
                # Enviamos para a tabela 'dashboard_obras'
                chunk.to_sql(
                    'dashboard_obras', 
                    conn, 
                    if_exists=metodo_sql, 
                    index=False,
                    method='multi' # <-- Isso acelera muito a inserção!
                )
                
                total_registros += len(chunk)
                logging.info(f"✅ Lote processado. Total no banco: {total_registros}")
                primeiro_lote = False

        logging.info("🚀 Missão cumprida! O Supabase recebeu todos os dados.")

    except Exception as e:
        logging.error(f"❌ Falha na migração: {e}")

if __name__ == "__main__":
    carregar_dados_supabase()
