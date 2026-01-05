import pandas as pd
import os
import logging
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Configuração de logs para acompanhar o progresso no terminal do Render
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def carregar_dados_supabase():
    load_dotenv()
    
    # Pega a URL do banco das variáveis de ambiente
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        logging.error("❌ Erro: DATABASE_URL não encontrada no ambiente!")
        return

    # Correção necessária para o SQLAlchemy reconhecer a URL do Render/Supabase
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    try:
        engine = create_engine(db_url)
        path_arquivo = "data/processed/df_mestre_consolidado.csv.gz"
        
        logging.info(f"📂 Iniciando leitura de {path_arquivo}...")

        # Lendo em "chunks" (pedaços) para economizar RAM no plano Free
        chunk_size = 10000 
        total_registros = 0
        
        # O modo 'replace' cria a tabela do zero no primeiro lote
        # Os próximos usam 'append' para adicionar os dados
        primeiro_lote = True

        for chunk in pd.read_csv(path_arquivo, compression='gzip', chunksize=chunk_size):
            metodo = 'replace' if primeiro_lote else 'append'
            
            # Envia o lote atual para a tabela 'base_conhecimento_ia'
            chunk.to_sql('base_conhecimento_ia', engine, if_exists=metodo, index=False)
            
            total_registros += len(chunk)
            logging.info(f"✅ Lote processado. Total acumulado: {total_registros} registros.")
            primeiro_lote = False

        logging.info("🚀 Sucesso! Todos os 300k registros estão no Supabase.")

    except Exception as e:
        logging.error(f"❌ Falha na migração: {e}")

if __name__ == "__main__":
    carregar_dados_supabase()
