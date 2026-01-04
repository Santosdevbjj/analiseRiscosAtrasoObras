import os
import logging
import warnings
from io import BytesIO
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import joblib

from fastapi import FastAPI, Request, Response, HTTPException
import uvicorn

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import sqlite3

warnings.filterwarnings("ignore", category=UserWarning)

# ======================================================
# LOG
# ======================================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("ccbjj_telegram_bot")

# ======================================================
# PATHS
# ======================================================
BASE_DIR = Path(__file__).resolve().parent.parent
PIPELINE_PATH = BASE_DIR / "models" / "pipeline_random_forest.pkl"
FEATURES_PATH = BASE_DIR / "models" / "features_metadata.joblib"
DB_PATH = BASE_DIR / "data" / "processed" / "df_mestre_consolidado.csv.gz"
DB_PATH_PARQUET = BASE_DIR / "data" / "processed" / "df_mestre_consolidado.parquet"

# ======================================================
# ENV
# ======================================================
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
TELEGRAM_SECRET_TOKEN = os.getenv("TELEGRAM_SECRET_TOKEN")

if not TOKEN or not WEBHOOK_URL:
    raise RuntimeError("❌ TELEGRAM_TOKEN ou WEBHOOK_URL não definidos.")

# ======================================================
# DATABASE (IDIOMA)
# ======================================================
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    language TEXT
)
""")
conn.commit()

def get_language(user_id: int) -> str:
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else "pt"

def set_language(user_id: int, lang: str):
    cursor.execute(
        "INSERT OR REPLACE INTO users (user_id, language) VALUES (?, ?)",
        (user_id, lang),
    )
    conn.commit()

# ======================================================
# i18n
# ======================================================
TEXTS = {
    "pt": {
        "start": (
            "🤖 *CCbjj Risk Intelligence Bot* 🇧🇷\n"
            "🏗️ *CCbjj Engenharia & Inteligência de Risco*\n\n"
            "Análise preditiva de riscos e atrasos em obras.\n\n"
            "📌 Formato do ID:\n`CCbjj-<número>`\n"
            "Exemplo: CCbjj-100\n\n"
            "Digite o ID da obra para iniciar."
        ),
        "help": (
            "📘 *Ajuda*\n\n"
            "Use o formato:\n`CCbjj-<número>`\n\n"
            "Comandos:\n"
            "/start\n/help\n/about\n/status\n/language\n\n"
            "_Desenvolvido por Sergio Luiz dos Santos_"
        ),
        "about": (
            "🏗️ *CCbjj Engenharia & Inteligência de Risco*\n\n"
            "IA aplicada à análise de risco em construção civil.\n\n"
            "_Desenvolvido por Sergio Luiz dos Santos_"
        ),
        "status": "✅ Bot online e operando normalmente.",
        "language": "Idioma alterado para Português 🇧🇷",
        "not_found": "❌ Obra não encontrada.",
        "processing": "🔍 Processando análise preditiva..."
    },
    "en": {
        "start": (
            "🤖 *CCbjj Risk Intelligence Bot* 🇺🇸\n"
            "🏗️ *CCbjj Engineering & Risk Intelligence*\n\n"
            "Predictive risk analysis for construction projects.\n\n"
            "Project ID format:\n`CCbjj-<number>`\n"
            "Example: CCbjj-100\n\n"
            "Send the project ID to start."
        ),
        "help": (
            "📘 *Help*\n\n"
            "Use format:\n`CCbjj-<number>`\n\n"
            "Commands:\n"
            "/start\n/help\n/about\n/status\n/language\n\n"
            "_Developed by Sergio Luiz dos Santos_"
        ),
        "about": (
            "🏗️ *CCbjj Engineering & Risk Intelligence*\n\n"
            "AI-driven construction risk intelligence.\n\n"
            "_Developed by Sergio Luiz dos Santos_"
        ),
        "status": "✅ Bot is online and running.",
        "language": "Language changed to English 🇺🇸",
        "not_found": "❌ Project not found.",
        "processing": "🔍 Processing predictive analysis..."
    },
}

# ======================================================
# LOAD MODELS & DATA
# ======================================================
pipeline = joblib.load(PIPELINE_PATH)
features_order = joblib.load(FEATURES_PATH)

if DB_PATH_PARQUET.exists():
    df_base = pd.read_parquet(DB_PATH_PARQUET)
else:
    df_base = pd.read_csv(DB_PATH, compression="gzip", low_memory=False)

# ======================================================
# BUSINESS
# ======================================================
def emoji_risco(dias):
    if dias > 10:
        return "🔴 Crítico"
    if dias > 7:
        return "🟡 Alerta"
    return "🟢 Normal"

def preparar_dados_predicao(df):
    X = df.copy()
    for col in features_order:
        if col not in X.columns:
            X[col] = 0
    return X[features_order]

# ======================================================
# HANDLERS
# ======================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_language(update.effective_user.id)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇧🇷", callback_data="lang_pt"),
            InlineKeyboardButton("🇺🇸", callback_data="lang_en"),
        ]
    ])
    await update.message.reply_text(
        TEXTS[lang]["start"],
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_language(update.effective_user.id)
    await update.message.reply_text(TEXTS[lang]["help"], parse_mode=ParseMode.MARKDOWN)

async def about_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_language(update.effective_user.id)
    await update.message.reply_text(TEXTS[lang]["about"], parse_mode=ParseMode.MARKDOWN)

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_language(update.effective_user.id)
    await update.message.reply_text(TEXTS[lang]["status"])

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = query.data.split("_")[1]
    set_language(query.from_user.id, lang)
    await query.answer()
    await query.edit_message_text(TEXTS[lang]["language"])

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_language(update.effective_user.id)
    id_obra = update.message.text.strip()

    df = df_base[df_base["id_obra"] == id_obra]
    if df.empty:
        await update.message.reply_text(TEXTS[lang]["not_found"])
        return

    status_msg = await update.message.reply_text(TEXTS[lang]["processing"])

    X = preparar_dados_predicao(df)
    preds = pipeline.predict(X)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(df["etapa"], preds)
    ax.set_title(id_obra)
    ax.set_ylabel("Dias")

    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close(fig)

    await update.message.reply_photo(photo=buf)
    await status_msg.delete()

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
    ptb_app.add_handler(CommandHandler("help", help_cmd))
    ptb_app.add_handler(CommandHandler("about", about_cmd))
    ptb_app.add_handler(CommandHandler("status", status_cmd))
    ptb_app.add_handler(CallbackQueryHandler(language_callback))
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
