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

from fastapi import FastAPI, Request, Response
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
# CONFIGURAÇÕES E LOGS
# ======================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ccbjj_bot")

BASE_DIR = Path(__file__).resolve().parent.parent
PIPELINE_PATH = BASE_DIR / "models/pipeline_random_forest.pkl"
FEATURES_PATH = BASE_DIR / "models/features_metadata.joblib"
DB_PATH = BASE_DIR / "data/processed/df_mestre_consolidado.csv.gz"

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not TOKEN or not WEBHOOK_URL:
    raise RuntimeError("❌ TELEGRAM_TOKEN ou WEBHOOK_URL não definidos.")

# ======================================================
# CARREGAMENTO DE RECURSOS
# ======================================================
pipeline = joblib.load(PIPELINE_PATH)
features_order = joblib.load(FEATURES_PATH)
df_base = pd.read_csv(DB_PATH, compression="gzip")

CACHE_RESULTADOS = {}

# ======================================================
# LÓGICA DE NEGÓCIO
# ======================================================
def emoji_risco(dias: float) -> str:
    if dias > 10: return "🔴 Crítico"
    if dias > 7: return "🟡 Alerta"
    return "🟢 Normal"

def preparar_X(df):
    X = df.copy()
    for col in features_order:
        if col not in X.columns:
            X[col] = 0
    return X[features_order]

def gerar_texto_executivo(id_obra, df_obra, preds):
    risco_medio = preds.mean()
    pior_idx = preds.argmax()
    pior_etapa = df_obra.iloc[pior_idx]

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
        f"Etapa: **{pior_etapa['etapa']}**\n"
        f"----------------------------------\n"
        f"💡 **Insight:** Revisar logística de **{pior_etapa['material']}**.\n\n"
        f"_Relatório gerado automaticamente_"
    )

def gerar_grafico(df_obra, preds):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(df_obra["etapa"], preds, color='#2c3e50')
    ax.set_title(f"Risco por Etapa - {df_obra['id_obra'].iloc[0]}")
    ax.set_ylabel("Dias de atraso")
    plt.xticks(rotation=45)
    
    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=150)
    buf.seek(0)
    plt.close(fig)
    return buf

def gerar_pdf(id_obra, texto_markdown, grafico_buf):
    pdf_buf = BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=A4)
    largura, altura = A4

    # Título e Cabeçalho
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, altura - 2 * cm, "CCBJJ Risk Intelligence - Relatório")
    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, altura - 2.5 * cm, f"Data de emissão: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    c.line(2 * cm, altura - 2.8 * cm, largura - 2 * cm, altura - 2.8 * cm)

    # Texto Explicativo (Removendo markdown simples para o PDF)
    texto_limpo = texto_markdown.replace("**", "").replace("`", "")
    text_obj = c.beginText(2 * cm, altura - 4 * cm)
    text_obj.setFont("Helvetica", 11)
    text_obj.setLeading(14)
    
    for line in texto_limpo.split('\n'):
        text_obj.textLine(line)
    c.drawText(text_obj)

    # Inserir Gráfico no PDF
    grafico_buf.seek(0)
    c.drawImage(InputFile(grafico_buf).input_file, 2 * cm, 4 * cm, width=17 * cm, preserveAspectRatio=True)

    # Rodapé
    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(largura/2, 1.5 * cm, "Este documento é uma análise preditiva baseada em Machine Learning.")

    c.showPage()
    c.save()
    pdf_buf.seek(0)
    return pdf_buf

# ======================================================
# TELEGRAM HANDLER
# ======================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *CCBJJ Risk Intelligence*\nEnvie o ID da obra para análise.",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_obra = update.message.text.strip()
    
    # Busca dados
    df_obra = df_base[df_base["id_obra"] == id_obra]
    if df_obra.empty:
        await update.message.reply_text("❌ Obra não encontrada na base de dados.")
        return

    # Predição e Geração de Conteúdo
    X = preparar_X(df_obra)
    preds = pipeline.predict(X)
    
    texto = gerar_texto_executivo(id_obra, df_obra, preds)
    grafico = gerar_grafico(df_obra, preds)
    # Geramos uma cópia do buffer do gráfico para o PDF não esgotar o primeiro
    grafico_para_pdf = BytesIO(grafico.getvalue())
    pdf = gerar_pdf(id_obra, texto, grafico_para_pdf)

    # ENVIO SEQUENCIAL
    # 1. Texto
    await update.message.reply_text(texto, parse_mode=ParseMode.MARKDOWN)
    
    # 2. Gráfico (Imagem)
    grafico.seek(0)
    await update.message.reply_photo(photo=grafico, caption=f"📊 Gráfico de Risco: {id_obra}")
    
    # 3. PDF
    pdf.seek(0)
    await update.message.reply_document(
        document=InputFile(pdf, filename=f"Relatorio_{id_obra}.pdf"),
        caption="📄 Relatório detalhado para arquivamento."
    )

# ======================================================
# FASTAPI + SERVIDOR
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
