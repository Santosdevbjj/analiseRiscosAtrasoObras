import pandas as pd
import os
import logging
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Configuração de Logs para monitorar o carregamento
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_data_to_supabase():
    # 1. Carregar variáveis de ambiente
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        logging.error("❌ DATABASE_URL não encontrada!")
        return

    # Ajuste para compatibilidade com SQLAlchemy 2.0+
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    try:
        engine = create_engine(db_url)
        
        # 2. Ler o arquivo consolidado (O que analisamos anteriormente)
        file_path = "data/processed/df_mestre_consolidado.csv.gz"
        logging.info(f"📂 Lendo arquivo: {file_path}")
        
        # Usamos chunksize para não estourar a memória RAM do plano Free do Render
        chunk_size = 10000 
        df_reader = pd.read_csv(file_path, compression='gzip', chunksize=chunk_size)

        first_chunk = True
        for i, chunk in enumerate(df_reader):
            # 3. Enviar para o banco (Tabela: dashboard_obras)
            # 'replace' no primeiro chunk para limpar a mesa, 'append' nos próximos
            mode = 'replace' if first_chunk else 'append'
            
            chunk.to_sql('dashboard_obras', engine, if_exists=mode, index=False)
            
            logging.info(f"✅ Lote {i+1} enviado ({len(chunk)} registros).")
            first_chunk = False

        logging.info("🚀 Carga completa! 300k registros disponíveis no Supabase.")

    except Exception as e:
        logging.error(f"❌ Erro durante a carga: {e}")

if __name__ == "__main__":
    load_data_to_supabase()
