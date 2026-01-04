import os
import logging
import hashlib
from io import BytesIO
from pathlib import Path
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import joblib

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

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

# ======================================================
# LOG
# ======================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ccbjj_bot")

# ======================================================
# PATHS
# ======================================================
BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
HISTORY_DIR = BASE_DIR / "data" / "history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

LOGO_PATH = ASSETS_DIR / "logo_ccbjj.png"
HISTORY_FILE = HISTORY_DIR / "historico_analises.csv"

PIPELINE_PATH = BASE_DIR / "models" / "pipeline_random_forest.pkl"
FEATURES_PATH = BASE_DIR / "models" / "features_metadata.joblib"
DB_PATH = BASE_DIR / "data" / "processed" / "df_mestre_consolidado.csv.gz"

# ======================================================
# ENV
# ======================================================
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
SECRET_TOKEN = os.getenv("TELEGRAM_SECRET_TOKEN")

# ======================================================
# LOAD DATA
# ======================================================
pipeline = joblib.load(PIPELINE_PATH)
features_order = joblib.load(FEATURES_PATH)
df_base = pd.read_csv(DB_PATH, compression="gzip")

# ======================================================
# CACHE & STATE
# ======================================================
prediction_cache = {}
user_mode = {}

# ======================================================
# CORE
# ======================================================
def emoji_risco(dias):
    if dias > 10:
        return "🔴 Crítico"
    if dias > 7:
        return "🟡 Alerta"
    return "🟢 Normal"


def preparar_dados(df):
    X = df.copy()
    for col in features_order:
        if col not in X.columns:
            X[col] = 0
    return X[features_order]


def gerar_predicao(id_obra, df):
    if id_obra in prediction_cache:
        return prediction_cache[id_obra]

    X = preparar_dados(df)
    preds = pipeline.predict(X)

    risco = float(preds.mean())
    pior = df.iloc[preds.argmax()]

    result = {
        "risco": risco,
        "status": emoji_risco(risco),
        "pior_etapa": pior["etapa"],
        "material": pior["material"],
        "preds": preds,
    }

    prediction_cache[id_obra] = result
    return result


def gerar_texto(id_obra, df, modo):
    r = gerar_predicao(id_obra, df)

    texto = (
        f"🏗️ *CCBJJ Engenharia & Inteligência de Risco*\n"
        f"----------------------------------\n"
        f"📍 *Obra:* {id_obra}\n"
        f"🏙️ *Cidade:* {df['cidade'].iloc[0]}\n"
        f"⛰️ *Solo:* {df['tipo_solo'].iloc[0]}\n"
        f"🌧️ *Chuva:* {df['nivel_chuva'].iloc[0]:.0f} mm\n"
        f"----------------------------------\n"
        f"📊 *Diagnóstico da IA*\n"
        f"• Risco médio: `{r['risco']:.1f} dias`\n"
        f"• Status: {r['status']}\n\n"
        f"⚠️ *Ponto Crítico*\n"
        f"A etapa mais sensível é *{r['pior_etapa']}*\n"
        f"----------------------------------\n"
        f"💡 *Insight:* Revisar logística de *{r['material']}*."
    )

    if modo == "tecnico":
        texto += "\n\n🔎 *Modo Técnico:* análise detalhada por etapa."

    return texto


def gerar_grafico(df, preds):
    buffer = BytesIO()
    plt.figure(figsize=(8, 4))
    plt.bar(df["etapa"], preds)
    plt.title("Risco de Atraso por Etapa")
    plt.ylabel("Dias")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    plt.close()
    return buffer


def registrar_historico(user, id_obra, risco, status, modo):
    registro = pd.DataFrame([{
        "data": datetime.now().isoformat(),
        "usuario": user,
        "obra": id_obra,
        "risco_medio": risco,
        "status": status,
        "modo": modo,
    }])

    if HISTORY_FILE.exists():
        registro.to_csv(HISTORY_FILE, mode="a", header=False, index=False)
    else:
        registro.to_csv(HISTORY_FILE, index=False)


def gerar_pdf(id_obra, df, texto, modo):
    r = gerar_predicao(id_obra, df)

    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # ================= CAPA =================
    if LOGO_PATH.exists():
        story.append(Image(LOGO_PATH, width=200, height=100))
        story.append(Spacer(1, 30))

    story.append(Paragraph("<b>Relatório Executivo de Risco</b>", styles["Title"]))
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"<b>Obra:</b> {id_obra}", styles["Normal"]))
    story.append(Paragraph(f"<b>Modo:</b> {modo.title()}", styles["Normal"]))
    story.append(Paragraph(f"<b>Data:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]))

    story.append(PageBreak())

    # ================= CONTEÚDO =================
    for linha in texto.replace("*", "").split("\n"):
        story.append(Paragraph(linha, styles["Normal"]))
        story.append(Spacer(1, 6))

    img_buffer = gerar_grafico(df, r["preds"])
    story.append(Spacer(1, 20))
    story.append(Image(img_buffer, width=400, height=200))

    # ================= ASSINATURA =================
    hash_relatorio = hashlib.sha256(texto.encode()).hexdigest()[:16]

    story.append(Spacer(1, 30))
    story.append(Paragraph("<b>Assinatura Digital</b>", styles["Heading3"]))
    story.append(Paragraph("CCBJJ Risk Intelligence System", styles["Normal"]))
    story.append(Paragraph(f"Hash: {hash_relatorio}", styles["Normal"]))
    story.append(Paragraph(datetime.now().isoformat(), styles["Normal"]))

    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer

# ======================================================
# TELEGRAM
# ======================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_mode[update.effective_user.id] = "diretor"
    await update.message.reply_text(
        "🤖 *CCBJJ Risk Intelligence Bot*\n\n"
        "Digite o ID da obra para análise.\n"
        "Exemplo: `CCbjj-100`\n\n"
        "Use `/mode tecnico` para visão detalhada.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Use: /mode diretor | tecnico")

    modo = context.args[0].lower()
    if modo not in ["diretor", "tecnico"]:
        return await update.message.reply_text("Modo inválido.")

    user_mode[update.effective_user.id] = modo
    await update.message.reply_text(f"Modo alterado para *{modo}*.", parse_mode=ParseMode.MARKDOWN)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_obra = update.message.text.strip()
    df = df_base[df_base["id_obra"] == id_obra]

    if df.empty:
        return await update.message.reply_text("❌ Obra não encontrada.")

    modo = user_mode.get(update.effective_user.id, "diretor")

    texto = gerar_texto(id_obra, df, modo)
    await update.message.reply_text(texto, parse_mode=ParseMode.MARKDOWN)

    r = gerar_predicao(id_obra, df)
    grafico = gerar_grafico(df, r["preds"])
    await update.message.reply_photo(photo=grafico, caption="📊 Risco por etapa")

    pdf = gerar_pdf(id_obra, df, texto, modo)
    await update.message.reply_document(
        document=InputFile(pdf, filename=f"relatorio_{id_obra}.pdf"),
        caption="📄 Relatório Executivo",
    )

    registrar_historico(
        update.effective_user.username or "anonimo",
        id_obra,
        r["risco"],
        r["status"],
        modo,
    )

# ======================================================
# FASTAPI
# ======================================================
app = FastAPI()
ptb_app = None

@app.on_event("startup")
async def startup():
    global ptb_app
    ptb_app = ApplicationBuilder().token(TOKEN).build()

    ptb_app.add_handler(CommandHandler("start", start))
    ptb_app.add_handler(CommandHandler("mode", mode))
    ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await ptb_app.initialize()
    await ptb_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook", secret_token=SECRET_TOKEN)
    await ptb_app.start()

@app.post("/webhook")
async def webhook(request: Request):
    if SECRET_TOKEN and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != SECRET_TOKEN:
        raise HTTPException(status_code=401)

    update = Update.de_json(await request.json(), ptb_app.bot)
    await ptb_app.process_update(update)
    return Response(status_code=200)

@app.get("/")
async def health():
    return {"status": "online"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
