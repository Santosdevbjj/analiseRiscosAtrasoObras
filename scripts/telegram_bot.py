"""
scripts/telegram_bot.py — Bot de Inteligência Preditiva MRV
Versão Final Consolidada: Data Science + Business Intelligence
"""

import os
import logging
import pandas as pd
import joblib
import numpy as np
from typing import List

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# -----------------------------
# Configurações de Caminho
# -----------------------------
MODEL_PATH = "models/modelo_random_forest.pkl"
DB_PATH = "data/raw/relatorio_consolidado.csv"  # Usando o consolidado que analisamos
ENCODER_PATH = "models/onehot_encoder.pkl"

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# -----------------------------
# Carregamento de Recursos
# -----------------------------
try:
    model = joblib.load(MODEL_PATH)
    logger.info("✅ Modelo RandomForest carregado.")
except Exception as e:
    logger.error(f"❌ Erro ao carregar modelo: {e}")
    model = None

try:
    db = pd.read_csv(DB_PATH)
    logger.info("✅ Base consolidada carregada.")
except Exception as e:
    logger.error(f"❌ Erro ao carregar base CSV: {e}")
    db = None

# Lista de colunas que o modelo espera (conforme seu treinamento)
COLUNAS_TREINO = [
    "orcamento_estimado", "rating_confiabilidade", "taxa_insucesso_fornecedor", 
    "complexidade_obra", "risco_etapa", "material_Aço", "material_Brita", 
    "material_Cimento", "material_Madeira", "material_Piso", "material_Revestimento", 
    "material_Tintas", "cidade_Belo Horizonte", "cidade_Curitiba", "cidade_Rio de Janeiro", 
    "cidade_Salvador", "cidade_São Paulo", "etapa_Acabamento", "etapa_Estrutura", "etapa_Fundação"
]

# -----------------------------
# Funções de Processamento ML
# -----------------------------
def preparar_e_prever(df_obra: pd.DataFrame) -> np.ndarray:
    """Prepara os dados da obra e retorna as predições do modelo."""
    # 1. Pipeline de encoding
    X = df_obra.drop(columns=["id_obra"], errors="ignore")
    X_encoded = pd.get_dummies(X, columns=["material", "cidade", "etapa"])
    
    # 2. Alinhamento de colunas
    for col in COLUNAS_TREINO:
        if col not in X_encoded.columns:
            X_encoded[col] = 0
    X_final = X_encoded[COLUNAS_TREINO]
    
    # 3. Predição
    return model.predict(X_final)

def emoji_risco(dias: float) -> str:
    if dias > 15: return "🔴"
    if dias > 5: return "🟡"
    return "🟢"

# -----------------------------
# Lógica de Relatório Consolidado
# -----------------------------
def gerar_relatorio_inteligente(id_obra: str, df_obra: pd.DataFrame) -> str:
    """Gera um relatório que une estatística descritiva e predição de ML."""
    
    # Executa a predição para todas as linhas da obra
    predicoes = preparar_e_prever(df_obra)
    df_obra['predicao_atraso'] = predicoes
    
    # Métricas principais
    risco_medio_previsto = df_obra['predicao_atraso'].mean()
    idx_pior_cenario = df_obra['predicao_atraso'].idxmax()
    pior_linha = df_obra.loc[idx_pior_cenario]
    
    cidade = df_obra['cidade'].iloc[0]
    orcamento = df_obra['orcamento_estimado'].iloc[0]
    
    status_geral = emoji_risco(risco_medio_previsto)
    
    relatorio = (
        f"{status_geral} *RELATÓRIO PREDITIVO MRV*\n"
        f"-------------------------------------------\n"
        f"📍 *Obra:* {id_obra}\n"
        f"🏢 *Cidade:* {cidade}\n"
        f"💰 *Orçamento:* R$ {orcamento:,.2f}\n"
        f"-------------------------------------------\n"
        f"📊 *MÉTRICA DE IA*\n"
        f"• Risco Médio Estimado: `{risco_medio_previsto:.1f} dias`\n\n"
        f"⚠️ *PONTO DE ATENÇÃO (PIOR CENÁRIO)*\n"
        f"• Etapa: {pior_linha['etapa']}\n"
        f"• Componente: {pior_linha['material']}\n"
        f"• Atraso Previsto: `{pior_linha['predicao_atraso']:.1f} dias`\n"
        f"• Taxa Fornecedor: {pior_linha['taxa_insucesso_fornecedor']:.2%}\n"
        f"-------------------------------------------\n"
        f"💡 *Sugestão:* Avaliar redundância de fornecedores para a etapa de {pior_linha['etapa']}."
    )
    return relatorio

# -----------------------------
# Handlers do Telegram
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏗️ *Sistema de Risco MRV Ativo*\n\n"
        "Envie o ID da obra (ex: `MRV-100`) para receber a análise preditiva consolidada.",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_usuario = update.message.text.upper().strip()
    logger.info(f"Consulta: {id_usuario}")

    if db is None or model is None:
        await update.message.reply_text("❌ Sistema offline. Verifique os arquivos .pkl e .csv.")
        return

    df_obra = db[db["id_obra"] == id_usuario]

    if df_obra.empty:
        await update.message.reply_text(f"❌ Obra `{id_usuario}` não encontrada na base.")
        return

    await update.message.reply_text("🔍 Processando modelos de IA e consolidando etapas...")
    
    try:
        texto_relatorio = gerar_relatorio_inteligente(id_usuario, df_obra)
        await update.message.reply_text(texto_relatorio, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Erro no processamento: {e}")
        await update.message.reply_text("❌ Erro ao gerar predição. Verifique o alinhamento das colunas.")

# -----------------------------
# Execução
# -----------------------------
def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        print("ERRO: Defina a variável de ambiente TELEGRAM_TOKEN")
        return

    app = ApplicationBuilder().token(token).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    logger.info("🚀 Bot MRV Online!")
    app.run_polling()

if __name__ == "__main__":
    main()
