# scripts/telegram_bot.py
import os
import logging
import warnings
from io import BytesIO

import pandas as pd
import joblib
import matplotlib.pyplot as plt

from fastapi import FastAPI, Request, Response
import uvicorn

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

warnings.filterwarnings("ignore", category=UserWarning)

# ==========================================================
# 🔧 CONFIGURAÇÃO DE LOG
# ==========================================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("ccbjj_telegram_bot")

# ==========================================================
# 📁 RESOLUÇÃO CORRETA DE PATH (CRÍTICO PARA RENDER)
# ==========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(BASE_DIR)  # sobe de /scripts para raiz

MODELS_DIR = os.path.join(BASE_DIR, "models")
DATA_DIR = os.path.join(BASE_DIR, "data", "processed")

PIPELINE_PATH = os.path.join(MODELS_DIR, "pipeline_random_forest.pkl")
FEATURES_PATH = os.path.join(MODELS_DIR, "features_metadata.joblib")
DB_PATH = os.path.join(DATA_DIR, "df_mestre_consolidado.csv.gz")

logger.info(f"BASE_DIR: {BASE_DIR}")

# ==========================================================
# 🔐 VARIÁVEIS DE AMBIENTE
# ==========================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not TELEGRAM_TOKEN or not WEBHOOK_URL:
    raise RuntimeError(
        "❌ Variáveis de ambiente TELEGRAM_TOKEN ou WEBHOOK_URL não configuradas."
    )

# ==========================================================
# 🤖 FASTAPI + TELEGRAM APPLICATION
# ==========================================================
app = FastAPI(title="CCBJJ Risk Intelligence API")

ptb_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# ==========================================================
# 📦 RECURSOS GLOBAIS (CARREGADOS NO STARTUP)
# ==========================================================
pipeline = None
features_order = None
df_base = None

# ==========================================================
# 🧠 FUNÇÕES DE NEGÓCIO
# ==========================================================
def emoji_risco(dias: float) -> str:
    if dias > 10:
        return "🔴 Crítico"
    if dias > 7:
        return "🟡 Alerta"
    return "🟢 Normal"


def preparar_dados_predicao(df_obra: pd.DataFrame) -> pd.DataFrame:
    X = df_obra.copy()
    for col in features_order:
        if col not in X.columns:
            X[col] = 0
    return X[features_order]


def gerar_relatorio_inteligente(id_obra: str, df_obra: pd.DataFrame) -> str:
    X = preparar_dados_predicao(df_obra)
    preds = pipeline.predict(X)

    risco_medio = float(preds.mean())
    temp_df = df_obra.copy()
    temp_df["pred"] = preds
    pior_linha = temp_df.loc[temp_df["pred"].idxmax()]

    return (
        f"🏗️ *CCBJJ RISK INTELLIGENCE*\n"
        f"----------------------------------\n"
        f"📍 *Obra:* {id_obra}\n"
        f"🌎 *Cidade:* {str(df_obra['cidade'].iloc[0]).title()}\n"
        f"⛰️ *Solo:* {str(df_obra['tipo_solo'].iloc[0]).title()}\n"
        f"🌧️ *Chuva:* {float(df_obra['nivel_chuva'].iloc[0]):.0f} mm\n"
        f"----------------------------------\n"
        f"📊 *DIAGNÓSTICO DA IA*\n"
        f"• Atraso Médio: `{risco_medio:.1f} dias`\n"
        f"• Status: {emoji_risco(risco_medio)}\n\n"
        f"⚠️ *Ponto Crítico*\n"
        f"Etapa: *{pior_linha['etapa'].title()}*\n"
        f"💡 *Insight:* Revisar logística de {pior_linha['material']}."
    )

# ==========================================================
# 📩 HANDLERS DO TELEGRAM
# ==========================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    await update.message.reply_text(
        f"Olá {user}! 👋\n\n"
        "*CCBJJ Bot Preditivo Online.*\n"
        "Envie o *ID da obra* para análise (ex: `CCbjj-100`).",
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_obra = update.message.text.strip()

    df_obra = df_base[df_base["id_obra"] == id_obra]

    if df_obra.empty:
        await update.message.reply_text(
            f"❌ Obra `{id_obra}` não encontrada.", parse_mode=ParseMode.MARKDOWN
        )
        return

    status_msg = await update.message.reply_text(
        "🔍 *Processando análise da IA...*", parse_mode=ParseMode.MARKDOWN
    )

    try:
        await update.message.reply_text(
            gerar_relatorio_inteligente(id_obra, df_obra),
            parse_mode=ParseMode.MARKDOWN,
        )

        # --- Gráfico ---
        X = preparar_dados_predicao(df_obra)
        preds = pipeline.predict(X)

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(df_obra["etapa"], preds)
        ax.set_title(f"Risco por Etapa - {id_obra}")
        ax.set_ylabel("Dias de Atraso")

        buf = BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format="png")
        buf.seek(0)
        plt.close(fig)

        await update.message.reply_photo(photo=buf)
        await status_msg.delete()

    except Exception as e:
        logger.exception("Erro ao processar mensagem")
        await update.message.reply_text("⚠️ Erro ao processar a análise.")

# ==========================================================
# 🚀 STARTUP / SHUTDOWN
# ==========================================================
@app.on_event("startup")
async def startup_event():
    global pipeline, features_order, df_base

    logger.info("🔄 Carregando recursos do modelo...")
    pipeline = joblib.load(PIPELINE_PATH)
    features_order = joblib.load(FEATURES_PATH)
    df_base = pd.read_csv(DB_PATH, compression="gzip")
    logger.info("✅ Recursos carregados com sucesso.")

    ptb_app.add_handler(CommandHandler("start", start))
    ptb_app.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    )

    await ptb_app.initialize()

    webhook_dest = f"{WEBHOOK_URL}/webhook"
    await ptb_app.bot.set_webhook(
        url=webhook_dest,
        allowed_updates=["message"],
        drop_pending_updates=True,
    )

    await ptb_app.start()
    logger.info(f"🚀 Webhook configurado: {webhook_dest}")


@app.on_event("shutdown")
async def shutdown_event():
    await ptb_app.stop()
    await ptb_app.shutdown()
    logger.info("🛑 Bot finalizado corretamente.")

# ==========================================================
# 🌐 ENDPOINTS FASTAPI
# ==========================================================
@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return Response(status_code=200)


@app.get("/")
async def root():
    return {"status": "online", "service": "CCBJJ Risk Intelligence"}


@app.get("/health")
async def health():
    return {"status": "ok"}

# ==========================================================
# ▶️ ENTRYPOINT LOCAL
# ==========================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
