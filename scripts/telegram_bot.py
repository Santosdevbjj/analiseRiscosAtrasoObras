import os
import logging
import warnings
import csv
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

# Tentativa de importação do ReportLab
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

warnings.filterwarnings("ignore", category=UserWarning)

# ======================================================
# CONFIGURAÇÕES E CAMINHOS
# ======================================================
BASE_DIR = Path(__file__).resolve().parent.parent
PIPELINE_PATH = BASE_DIR / "models/pipeline_random_forest.pkl"
FEATURES_PATH = BASE_DIR / "models/features_metadata.joblib"
DB_PATH = BASE_DIR / "data/processed/df_mestre_consolidado.csv.gz"
LOGO_PATH = BASE_DIR / "assets/logo_ccbjj.png"
HISTORY_PATH = BASE_DIR / "data/history/analises_history.csv"

# Garante que a pasta de histórico existe
HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Carregamento de Modelos e Dados
pipeline = joblib.load(PIPELINE_PATH)
features_order = joblib.load(FEATURES_PATH)
df_base = pd.read_csv(DB_PATH, compression="gzip")

# ======================================================
# SISTEMA DE HISTÓRICO
# ======================================================
def salvar_historico(user_id, id_obra, risco_medio, status, modo="Técnico"):
    """Registra cada consulta em um arquivo CSV para auditoria."""
    file_exists = HISTORY_PATH.exists()
    
    with open(HISTORY_PATH, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["data_hora", "usuario_id", "id_obra", "risco_medio", "status", "modo"])
        
        writer.writerow([
            datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            user_id,
            id_obra,
            f"{risco_medio:.2f}",
            status,
            modo
        ])

# ======================================================
# GERAÇÃO DE PDF CORPORATIVO
# ======================================================
def gerar_pdf_corporativo(id_obra, texto_md, grafico_buf, modo="Diretor"):
    if not REPORTLAB_AVAILABLE: return None
    
    pdf_buf = BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=A4)
    largura, altura = A4
    data_analise = datetime.now().strftime("%d/%m/%Y %H:%M")

    # --- PÁGINA 1: CAPA ---
    if LOGO_PATH.exists():
        c.drawImage(str(LOGO_PATH), (largura/2) - 3*cm, altura - 10*cm, width=6*cm, preserveAspectRatio=True)
    
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(largura/2, altura - 12*cm, "Relatório de Análise de Risco")
    
    c.setFont("Helvetica", 14)
    c.drawCentredString(largura/2, altura - 13.5*cm, "CCBJJ Engenharia & Inteligência")
    
    # Box de Informações da Capa
    c.setStrokeColor(colors.lightgrey)
    c.roundRect(4*cm, 10*cm, largura - 8*cm, 2.5*cm, 10, stroke=1, fill=0)
    
    c.setFont("Helvetica-Bold", 10)
    c.drawString(4.5*cm, 12*cm, f"ID DA OBRA: {id_obra}")
    c.drawString(4.5*cm, 11.5*cm, f"DATA DA ANÁLISE: {data_analise}")
    c.drawString(4.5*cm, 11*cm, f"MODO DE EMISSÃO: {modo}")
    c.drawString(4.5*cm, 10.5*cm, "RESPONSÁVEL: Sergio Luiz dos Santos")

    c.showPage() # Finaliza a capa

    # --- PÁGINA 2: CONTEÚDO TÉCNICO ---
    # Rodapé Interno (Logo reaparece pequeno)
    if LOGO_PATH.exists():
        c.drawImage(str(LOGO_PATH), largura - 3.5*cm, 1*cm, width=2*cm, preserveAspectRatio=True)
    
    c.setFont("Helvetica", 8)
    c.drawString(2*cm, 1.5*cm, f"Relatório Gerencial - Obra {id_obra} | Gerado em {data_analise}")
    c.line(2*cm, 2.2*cm, largura - 2*cm, 2.2*cm)

    # Conteúdo (Texto e Gráfico)
    texto_limpo = texto_md.replace("**", "").replace("`", "")
    text_obj = c.beginText(2*cm, altura - 3*cm)
    text_obj.setFont("Helvetica", 11)
    text_obj.setLeading(14)
    for line in texto_limpo.split('\n'):
        text_obj.textLine(line)
    c.drawText(text_obj)

    # Gráfico
    img_path = f"temp_{id_obra}.png"
    with open(img_path, "wb") as f:
        f.write(grafico_buf.getbuffer())
    c.drawImage(img_path, 2*cm, 3.5*cm, width=17*cm, preserveAspectRatio=True)
    
    c.showPage()
    c.save()
    
    if os.path.exists(img_path): os.remove(img_path)
    pdf_buf.seek(0)
    return pdf_buf

# ======================================================
# LOGICA DE PREDICÃO E HANDLERS
# ======================================================

# (Funções emoji_risco, preparar_X e gerar_grafico permanecem as mesmas do anterior)
def emoji_risco(dias: float) -> str:
    if dias > 10: return "🔴 Crítico"
    if dias > 7: return "🟡 Alerta"
    return "🟢 Normal"

def preparar_X(df):
    X = df.copy()
    for col in features_order:
        if col not in X.columns: X[col] = 0
    return X[features_order]

def gerar_grafico(df_obra, preds):
    plt.figure(figsize=(8, 5))
    plt.bar(df_obra["etapa"], preds, color='steelblue')
    plt.title(f"Distribuição de Risco - {df_obra['id_obra'].iloc[0]}")
    plt.ylabel("Atraso Estimado (Dias)")
    plt.xticks(rotation=30)
    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=120)
    buf.seek(0)
    plt.close()
    return buf

def gerar_texto_executivo(id_obra, df_obra, preds):
    risco_medio = preds.mean()
    pior_idx = preds.argmax()
    pior_etapa = df_obra.iloc[pior_idx]
    return (
        f"🏗️ **CCBJJ Engenharia & Inteligência**\n"
        f"----------------------------------\n"
        f"📍 **Obra:** {id_obra}\n"
        f"🏙️ **Cidade:** {df_obra['cidade'].iloc[0]}\n"
        f"----------------------------------\n"
        f"📊 **Diagnóstico IA**\n"
        f"• Risco médio: `{risco_medio:.1f} dias`\n"
        f"• Status: {emoji_risco(risco_medio)}\n\n"
        f"⚠️ **Ponto Crítico:** {pior_etapa['etapa']}\n"
        f"----------------------------------\n"
        f"_Relatório Automático v2.0_"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_obra = update.message.text.strip()
    user_id = update.message.from_user.id
    df_obra = df_base[df_base["id_obra"] == id_obra]

    if df_obra.empty:
        await update.message.reply_text("❌ ID da obra não localizado em nossa base.")
        return

    # Processamento
    X = preparar_X(df_obra)
    preds = pipeline.predict(X)
    risco_medio = preds.mean()
    status = emoji_risco(risco_medio)
    
    # 1. Salvar no Histórico CSV
    salvar_historico(user_id, id_obra, risco_medio, status)
    
    # 2. Gerar Visualizações
    texto = gerar_texto_executivo(id_obra, df_obra, preds)
    grafico_img = gerar_grafico(df_obra, preds)
    
    # 3. Enviar Respostas no Telegram
    await update.message.reply_text(texto, parse_mode=ParseMode.MARKDOWN)
    
    grafico_img.seek(0)
    await update.message.reply_photo(photo=grafico_img, caption="📈 Gráfico de Tendência de Atrasos")
    
    if REPORTLAB_AVAILABLE:
        grafico_img.seek(0)
        pdf_file = gerar_pdf_corporativo(id_obra, texto, grafico_img, modo="Diretor")
        await update.message.reply_document(
            document=InputFile(pdf_file, filename=f"Relatorio_{id_obra}_{datetime.now().strftime('%Y%m%d')}.pdf"),
            caption="📄 Relatório Executivo assinado digitalmente."
        )

# ======================================================
# INICIALIZAÇÃO DO APP (FastAPI)
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
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
