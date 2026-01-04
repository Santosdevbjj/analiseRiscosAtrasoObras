import os
import logging
import warnings
from io import BytesIO
from pathlib import Path
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import pandas as pd
import joblib

from fastapi import FastAPI, Request, Response, HTTPException
import uvicorn

from telegram import Update, InputFile
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

warnings.filterwarnings("ignore", category=UserWarning)

# ======================================================
# LOG
# ======================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ccbjj_bot")

# ======================================================
# PATHS
# ======================================================
BASE_DIR = Path(__file__).resolve().parent.parent
PIPELINE_PATH = BASE_DIR / "models/pipeline_random_forest.pkl"
FEATURES_PATH = BASE_DIR / "models/features_metadata.joblib"
DB_PATH = BASE_DIR / "data/processed/df_mestre_consolidado.csv.gz"
LOGO_PATH = BASE_DIR / "assets/logo_ccbjj.png"  # opcional

# ======================================================
# ENV
# ======================================================
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not TOKEN or not WEBHOOK_URL:
    raise RuntimeError("❌ TELEGRAM_TOKEN ou WEBHOOK_URL não definidos.")

# ======================================================
# LOAD RESOURCES
# ======================================================
pipeline = joblib.load(PIPELINE_PATH)
features_order = joblib.load(FEATURES_PATH)
df_base = pd.read_csv(DB_PATH, compression="gzip")

# Cache simples em memória
CACHE_RESULTADOS = {}

# ======================================================
# BUSINESS
# ======================================================
def emoji_risco(dias: float) -> str:
    if dias > 10:
        return "🔴 Crítico"
    if dias > 7:
        return "🟡 Alerta"
    return "🟢 Normal"


def preparar_X(df):
    X = df.copy()
    for col in features_order:
        if col not in X.columns:
            X[col] = 0
    return X[features_order]


def gerar_texto_executivo(id_obra, df_obra, preds):
    risco_medio = preds.mean()
    pior = df_obra.iloc[preds.argmax()]

    return (
        f"🏗️ **CCBJJ Engenharia & Inteligência de Risco**\n"
        f"----------------------------------\n"
        f"📍 **Obra:** {id_obra}\n"
        f"🏙️ **Cidade:** {df_obra['cidade'].iloc[0]}\n"
        f"⛰️ **Solo:** {df_obra['tipo_solo'].iloc[0]}\n"
        f"🌧️ **Chuva:** {df_obra['nivel_chuva'].iloc[0]} mm\n"
        f"----------------------------------\n"
        f"📊 **Diagnóstico da IA**\n"
        f"• Risco médio: `{risco_medio:.1f} dias`\n"
        f"• Status: {emoji_risco(risco_medio)}\n\n"
        f"⚠️ **Ponto Crítico**\n"
        f"A etapa mais sensível é **{pior['etapa']}**.\n"
        f"----------------------------------\n"
        f"💡 **Insight:** Revisar logística de **{pior['material']}**.\n\n"
        f"_Desenvolvido por Sergio Luiz dos Santos_"
    )


def gerar_grafico(df_obra, preds):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(df_obra["etapa"], preds)
    ax.set_title("Risco de atraso por etapa")
    ax.set_ylabel("Dias")

    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close(fig)
    return buf


def gerar_pdf(id_obra, texto, grafico_buf):
    pdf_buf = BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=A4)

    # Capa
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(10.5 * cm, 26 * cm, "CCBJJ Risk Intelligence")
    c.setFont("Helvetica", 12)
    c.drawCentredString(10.5 * cm, 24.5 * cm, "Relatório Executivo de Risco")
    c.drawCentredString(10.5 * cm, 23 * cm, f"Obra: {id_obra}")
    c.drawCentredString(10.5 * cm, 21.5 * cm, datetime.now().strftime("%d/%m/%Y %H:%M"))

    c.showPage()

    # Texto
    text_obj = c.beginText(2 * cm, 27 * cm)
    text_obj.setFont("Helvetica", 10)
    for line in texto.replace("**", "").split("\n"):
        text_obj.textLine(line)
    c.drawText(text_obj)

    # Gráfico
    grafico_buf.seek(0)
    c.drawImage(grafico_buf, 2 * cm, 6 * cm, width=17 * cm, preserveAspectRatio=True)

    c.showPage()
    c.save()

    pdf_buf.seek(0)
    return pdf_buf

# ======================================================
# TELEGRAM HANDLER
# ======================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *CCbjj Risk Intelligence Bot*\n"
        "🏗️ CCbjj Engenharia & Inteligência de Risco\n\n"
        "Envie o ID da obra no formato:\n"
        "`CCbjj-100`",
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_obra = update.message.text.strip()

    if id_obra in CACHE_RESULTADOS:
        texto, grafico, pdf = CACHE_RESULTADOS[id_obra]
    else:
        df_obra = df_base[df_base["id_obra"] == id_obra]
        if df_obra.empty:
            await update.message.reply_text("❌ Obra não encontrada.")
            return

        X = preparar_X(df_obra)
        preds = pipeline.predict(X)

        texto = gerar_texto_executivo(id_obra, df_obra, preds)
        grafico = gerar_grafico(df_obra, preds)
        pdf = gerar_pdf(id_obra, texto, grafico)

        CACHE_RESULTADOS[id_obra] = (texto, grafico, pdf)

    # 1️⃣ TEXTO
    await update.message.reply_text(texto, parse_mode=ParseMode.MARKDOWN)

    # 2️⃣ GRÁFICO
    await update.message.reply_photo(photo=grafico, caption="📊 Risco por etapa")

    # 3️⃣ PDF
    await update.message.reply_document(
        document=InputFile(pdf, filename=f"relatorio_{id_obra}.pdf"),
        caption="📄 Relatório Executivo"
    )

# ======================================================
# FASTAPI + WEBHOOK
# ======================================================
app = FastAPI()
ptb_app = None

@app.on_event("startup")
async def startup():
    global ptb_app
    ptb_app = ApplicationBuilder().token(TOKEN).build()
    ptb_app.add_handler(CommandHandler("start", start))
    ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await ptb_app.initialize()
    await ptb_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    await ptb_app.start()

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return Response(status_code=200)

@app.get("/")
async def health():
    return {"status": "online"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
