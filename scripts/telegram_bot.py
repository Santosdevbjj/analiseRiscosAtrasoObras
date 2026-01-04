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

# Tentativa de importação do ReportLab com tratamento de erro
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("⚠️ AVISO: Biblioteca 'reportlab' não encontrada. Geração de PDF desativada.")

warnings.filterwarnings("ignore", category=UserWarning)

# ======================================================
# CONFIGURAÇÕES
# ======================================================
BASE_DIR = Path(__file__).resolve().parent.parent
PIPELINE_PATH = BASE_DIR / "models/pipeline_random_forest.pkl"
FEATURES_PATH = BASE_DIR / "models/features_metadata.joblib"
DB_PATH = BASE_DIR / "data/processed/df_mestre_consolidado.csv.gz"

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Carregamento
pipeline = joblib.load(PIPELINE_PATH)
features_order = joblib.load(FEATURES_PATH)
df_base = pd.read_csv(DB_PATH, compression="gzip")

# ======================================================
# FUNÇÕES DE GERAÇÃO
# ======================================================
def emoji_risco(dias: float) -> str:
    if dias > 10: return "🔴 Crítico"
    if dias > 7: return "🟡 Alerta"
    return "🟢 Normal"

def preparar_X(df):
    X = df.copy()
    for col in features_order:
        if col not in X.columns: X[col] = 0
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
        f"_Desenvolvido por Sergio Luiz dos Santos_"
    )

def gerar_grafico(df_obra, preds):
    plt.figure(figsize=(8, 5))
    plt.bar(df_obra["etapa"], preds, color='steelblue')
    plt.title(f"Risco por Etapa - {df_obra['id_obra'].iloc[0]}")
    plt.ylabel("Dias de Atraso")
    plt.xticks(rotation=30)
    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=120)
    buf.seek(0)
    plt.close()
    return buf

def gerar_pdf(id_obra, texto_md, grafico_buf):
    if not REPORTLAB_AVAILABLE: return None
    pdf_buf = BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=A4)
    largura, altura = A4
    
    # Cabeçalho
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, altura - 2 * cm, "Relatório Executivo de Risco")
    c.line(2 * cm, altura - 2.8 * cm, largura - 2 * cm, altura - 2.8 * cm)

    # Texto
    texto_limpo = texto_md.replace("**", "").replace("`", "")
    text_obj = c.beginText(2 * cm, altura - 4 * cm)
    text_obj.setFont("Helvetica", 11)
    for line in texto_limpo.split('\n'): text_obj.textLine(line)
    c.drawText(text_obj)

    # Gráfico no PDF
    img_path = f"temp_{id_obra}.png"
    with open(img_path, "wb") as f: f.write(grafico_buf.getbuffer())
    c.drawImage(img_path, 2 * cm, 3 * cm, width=17 * cm, preserveAspectRatio=True)
    
    c.showPage()
    c.save()
    if os.path.exists(img_path): os.remove(img_path)
    pdf_buf.seek(0)
    return pdf_buf

# ======================================================
# HANDLERS
# ======================================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_obra = update.message.text.strip()
    df_obra = df_base[df_base["id_obra"] == id_obra]

    if df_obra.empty:
        await update.message.reply_text("❌ Obra não encontrada.")
        return

    X = preparar_X(df_obra)
    preds = pipeline.predict(X)
    
    texto = gerar_texto_executivo(id_obra, df_obra, preds)
    grafico_img = gerar_grafico(df_obra, preds)
    
    # 1. Enviar Texto
    await update.message.reply_text(texto, parse_mode=ParseMode.MARKDOWN)
    
    # 2. Enviar Gráfico
    grafico_img.seek(0)
    await update.message.reply_photo(photo=grafico_img, caption="📊 Análise Visual")
    
    # 3. Enviar PDF
    if REPORTLAB_AVAILABLE:
        graf_pdf = BytesIO(grafico_img.getvalue())
        pdf_file = gerar_pdf(id_obra, texto, graf_pdf)
        await update.message.reply_document(
            document=InputFile(pdf_file, filename=f"Relatorio_{id_obra}.pdf"),
            caption="📄 PDF Consolidado"
        )
    else:
        await update.message.reply_text("⚠️ PDF indisponível (biblioteca reportlab não instalada).")

# ======================================================
# APP
# ======================================================
app = FastAPI()
ptb_app = None

@app.on_event("startup")
async def startup():
    global ptb_app
    ptb_app = ApplicationBuilder().token(TOKEN).build()
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
