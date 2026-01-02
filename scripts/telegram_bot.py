import os
import logging
import warnings
from io import BytesIO
import pandas as pd
import joblib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

import uvicorn
from fastapi import FastAPI, Request, Response
from telegram import Update, Bot
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

warnings.filterwarnings("ignore", category=UserWarning)

# --- Configurações de Caminho ---
BASE_DIR = os.getcwd()
PIPELINE_PATH = os.path.join(BASE_DIR, "models", "pipeline_random_forest.pkl")
FEATURES_PATH = os.path.join(BASE_DIR, "models", "features_metadata.joblib")
DB_PATH = os.path.join(BASE_DIR, "data", "processed", "df_mestre_consolidado.csv.gz")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger("telegram_bot_ccbjj")

# Carregamento Global com Fallback
try:
    pipeline = joblib.load(PIPELINE_PATH)
    features_order = joblib.load(FEATURES_PATH)
    df_base = pd.read_csv(DB_PATH, compression='gzip')
    logger.info("✅ Recursos carregados com sucesso.")
except Exception as e:
    logger.error(f"❌ Erro ao carregar recursos: {e}")
    df_base = pd.DataFrame()

# --- Funções de Negócio ---
def emoji_risco(dias: float) -> str:
    if dias > 10: return "🔴 (Crítico)"
    if dias > 7: return "🟡 (Alerta)"
    return "🟢 (Normal)"

def preparar_dados_predicao(df_obra: pd.DataFrame):
    X = df_obra.copy()
    # Garante que apenas as colunas que o modelo conhece entrem na predição
    for col in features_order:
        if col not in X.columns:
            X[col] = 0
    return X[features_order]

def gerar_relatorio_inteligente(id_obra: str, df_obra: pd.DataFrame) -> str:
    X = preparar_dados_predicao(df_obra)
    pred_dias = pipeline.predict(X)
    risco_medio = float(pred_dias.mean())
    
    # Identifica a etapa com maior predição individual
    temp_df = df_obra.copy()
    temp_df['pred'] = pred_dias
    pior_linha = temp_df.loc[temp_df['pred'].idxmax()]

    return (
        f"🏗️ *CCBJJ RISK INTELLIGENCE*\n"
        f"-------------------------------------------\n"
        f"📍 *Obra:* {id_obra} | {str(df_obra['cidade'].iloc[0]).title()}\n"
        f"⛰️ *Geologia:* {str(df_obra['tipo_solo'].iloc[0]).title()}\n"
        f"🌧️ *Clima:* {float(df_obra['nivel_chuva'].iloc[0]):.0f}mm\n"
        f"-------------------------------------------\n"
        f"📊 *DIAGNÓSTICO DA IA*\n"
        f"• Risco Médio: `{risco_medio:.1f} dias`\n"
        f"• Status: {emoji_risco(risco_medio)}\n\n"
        f"⚠️ *PONTO DE ATENÇÃO*\n"
        f"A etapa de *{pior_linha['etapa'].title()}* é a mais crítica.\n"
        f"-------------------------------------------\n"
        f"💡 *INSIGHT:* Revisar logística de {pior_linha['material']}."
    )

# --- Handlers do Telegram ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    await update.message.reply_text(
        f"Olá {user}! 👋 *CCBJJ Bot Preditivo Online.*\n\n"
        "Envie o ID da obra para análise de risco (ex: `CCbjj-100`).",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_obra = update.message.text.strip()
    df_obra = df_base[df_base["id_obra"] == id_obra]
    
    if df_obra.empty:
        await update.message.reply_text(f"❌ Obra `{id_obra}` não encontrada em nossa base.")
        return

    msg_status = await update.message.reply_text("🔍 *Processando IA...*", parse_mode=ParseMode.MARKDOWN)

    try:
        # Envia Relatório Texto
        await update.message.reply_text(gerar_relatorio_inteligente(id_obra, df_obra), parse_mode=ParseMode.MARKDOWN)
        
        # Gera e Envia Gráfico (Em memória)
        plt.style.use('ggplot')
        X = preparar_dados_predicao(df_obra)
        preds = pipeline.predict(X)
        
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(df_obra['etapa'], preds, color='#1B5E20')
        ax.set_title(f"Risco por Etapa - {id_obra}")
        ax.set_ylabel("Dias de Atraso")
        
        img_buf = BytesIO()
        plt.savefig(img_buf, format='png')
        img_buf.seek(0)
        await update.message.reply_photo(photo=img_buf)
        plt.close(fig)
        
        await msg_status.delete()

    except Exception as e:
        logger.error(f"Erro no Handler: {e}")
        await update.message.reply_text("⚠️ Erro ao processar predição.")

# --- Configuração FastAPI + Webhook ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

app = FastAPI()
ptb_app = ApplicationBuilder().token(TOKEN).build()

@app.on_event("startup")
async def on_startup():
    ptb_app.add_handler(CommandHandler("start", start))
    ptb_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    # Configuração crucial do Webhook
    webhook_dest = f"{WEBHOOK_URL}/webhook"
    await ptb_app.bot.set_webhook(url=webhook_dest)
    await ptb_app.initialize()
    await ptb_app.start() # Necessário para processar updates
    logger.info(f"🚀 Webhook configurado para: {webhook_dest}")

@app.on_event("shutdown")
async def on_shutdown():
    await ptb_app.stop()
    await ptb_app.shutdown()

@app.post("/webhook")
async def webhook_endpoint(request: Request):
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return Response(status_code=200)

@app.get("/")
async def index():
    return {"status": "CCBJJ API Online", "mode": "Webhook"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
