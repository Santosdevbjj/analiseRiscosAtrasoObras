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
# LOGS E CONFIGURAÇÕES
# ======================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ccbjj_bot")

BASE_DIR = Path(__file__).resolve().parent.parent
PIPELINE_PATH = BASE_DIR / "models/pipeline_random_forest.pkl"
FEATURES_PATH = BASE_DIR / "models/features_metadata.joblib"
DB_PATH = BASE_DIR / "data/processed/df_mestre_consolidado.csv.gz"

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# ======================================================
# CARREGAMENTO DE RECURSOS
# ======================================================
pipeline = joblib.load(PIPELINE_PATH)
features_order = joblib.load(FEATURES_PATH)
df_base = pd.read_csv(DB_PATH, compression="gzip")

# ======================================================
# FUNÇÕES DE APOIO
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
        f"_Desenvolvido por Sergio Luiz dos Santos_"
    )

def gerar_grafico(df_obra, preds):
    plt.figure(figsize=(8, 5))
    plt.bar(df_obra["etapa"], preds, color='steelblue')
    plt.title(f"Risco por Etapa - {df_obra['id_obra'].iloc[0]}", fontsize=14)
    plt.ylabel("Dias de Atraso", fontsize=12)
    plt.xticks(rotation=30)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=120)
    buf.seek(0)
    plt.close()
    return buf

def gerar_pdf(id_obra, texto_markdown, grafico_buf):
    pdf_buf = BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=A4)
    largura, altura = A4

    # Cabeçalho
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, altura - 2 * cm, "Relatório Executivo de Risco")
    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, altura - 2.6 * cm, f"Obra: {id_obra} | Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    c.line(2 * cm, altura - 2.8 * cm, largura - 2 * cm, altura - 2.8 * cm)

    # Conteúdo de Texto (Limpando markdown para o PDF)
    texto_limpo = texto_markdown.replace("**", "").replace("`", "")
    text_obj = c.beginText(2 * cm, altura - 4 * cm)
    text_obj.setFont("Helvetica", 11)
    text_obj.setLeading(16)
    
    for line in texto_limpo.split('\n'):
        text_obj.textLine(line)
    c.drawText(text_obj)

    # Inserção do Gráfico no PDF
    grafico_buf.seek(0)
    # Criamos um arquivo temporário para o ReportLab ler a imagem corretamente
    img_path = f"temp_graph_{id_obra}.png"
    with open(img_path, "wb") as f:
        f.write(grafico_buf.getbuffer())
    
    c.drawImage(img_path, 2 * cm, 3 * cm, width=17 * cm, preserveAspectRatio=True)
    c.showPage()
    c.save()
    
    # Limpeza e retorno
    if os.path.exists(img_path):
        os.remove(img_path)
    
    pdf_buf.seek(0)
    return pdf_buf

# ======================================================
# HANDLERS DO TELEGRAM
# ======================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏗️ *CCBJJ Bot*: Envie o ID da obra (ex: CCbjj-109).", parse_mode=ParseMode.MARKDOWN)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_obra = update.message.text.strip()
    df_obra = df_base[df_base["id_obra"] == id_obra]

    if df_obra.empty:
        await update.message.reply_text("❌ Obra não encontrada.")
        return

    # 1. Processamento
    X = preparar_X(df_obra)
    preds = pipeline.predict(X)
    
    # 2. Geração de Componentes
    texto = gerar_texto_executivo(id_obra, df_obra, preds)
    grafico_img = gerar_grafico(df_obra, preds)
    # Criar buffer separado para o PDF para não fechar o anterior
    grafico_para_pdf = BytesIO(grafico_img.getvalue())
    pdf_documento = gerar_pdf(id_obra, texto, grafico_para_pdf)

    # 3. ENVIO EM ORDEM
    # ENVIAR TEXTO
    await update.message.reply_text(texto, parse_mode=ParseMode.MARKDOWN)
    
    # ENVIAR GRÁFICO (Imagem)
    grafico_img.seek(0)
    await update.message.reply_photo(photo=grafico_img, caption="📊 Análise Visual de Risco")
    
    # ENVIAR PDF (Documento)
    pdf_documento.seek(0)
    await update.message.reply_document(
        document=InputFile(pdf_documento, filename=f"Relatorio_{id_obra}.pdf"),
        caption="📄 Relatório Consolidado (Texto + Gráfico)"
    )

# ======================================================
# API E EXECUÇÃO
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
