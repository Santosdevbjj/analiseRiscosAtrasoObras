import os 
import sys
import logging
import warnings
import joblib
import pandas as pd
import pytz
from io import BytesIO
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine

# Adiciona o diretório scripts ao PATH
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

# Servidor e API
from fastapi import FastAPI, Request, Response
import uvicorn

# Telegram
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

# Importações customizadas corrigidas
import database  # Importa o módulo completo para usar get_storage_mode
from i18n import TEXTS
from handlers import (
    start_command, help_command, about_command, 
    status_command, language_callback, resolve_language,
    language_manual_command, example_command, healthcheck_command
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore", category=UserWarning)

# ======================================================
# CONFIGURAÇÕES DE CAMINHOS E CONEXÕES
# ======================================================
BASE_DIR = Path(__file__).resolve().parent.parent
PIPELINE_PATH = BASE_DIR / "models/pipeline_random_forest.pkl"
FEATURES_PATH = BASE_DIR / "models/features_metadata.joblib"
DB_PATH = BASE_DIR / "data/processed/df_mestre_consolidado.csv.gz"

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Inicialização de Recursos
pipeline = joblib.load(PIPELINE_PATH)
features_order = joblib.load(FEATURES_PATH)
engine = create_engine(DATABASE_URL) if DATABASE_URL else None

# Carrega CSV (Legado/Fallback)
df_base = pd.read_csv(DB_PATH, compression="gzip")

# ======================================================
# FUNÇÕES DE APOIO
# ======================================================

def obter_menu_infra():
    keyboard = [[
        InlineKeyboardButton("📂 Modo CSV", callback_data='set_CSV'),
        InlineKeyboardButton("☁️ Modo Supabase", callback_data='set_DB'),
    ]]
    return InlineKeyboardMarkup(keyboard)

async def get_data(id_obra, user_id):
    """Busca dados usando a preferência salva no banco SQLite."""
    mode = database.get_storage_mode(user_id) # Busca do SQLite persistente
    id_obra_clean = id_obra.strip()
    
    if mode == "SUPABASE" and engine:
        query = f"SELECT * FROM dashboard_obras WHERE id_obra ILIKE '{id_obra_clean}'"
        df = pd.read_sql(query, engine)
        return df, "SUPABASE"
    else:
        df = df_base[df_base["id_obra"].str.contains(id_obra_clean, case=False, na=False)]
        return df, "CSV"

def preparar_X(df):
    X = df.copy()
    for col in features_order:
        if col not in X.columns: 
            X[col] = 0
    return X[features_order].fillna(0)

# ======================================================
# HANDLERS ADICIONAIS
# ======================================================

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = resolve_language(update)
    await update.message.reply_text(
        TEXTS[lang]["infra_select"],
        reply_markup=obter_menu_infra(),
        parse_mode=ParseMode.MARKDOWN
    )

async def config_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang = resolve_language(update)
    
    mode = "CSV" if query.data == 'set_CSV' else "SUPABASE"
    database.set_storage_mode(user_id, mode) # Salva no SQLite
    
    msg = f"{TEXTS[lang]['mode_changed']}**{mode}**"
    await query.edit_message_text(text=msg, parse_mode=ParseMode.MARKDOWN)

# ======================================================
# HANDLER DE MENSAGEM PRINCIPAL
# ======================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_obra = update.message.text.strip()
    lang = resolve_language(update)
    user_id = update.effective_user.id
    
    df_obra, modo_usado = await get_data(id_obra, user_id)

    if df_obra.empty:
        await update.message.reply_text(f"{TEXTS[lang]['not_found']}{modo_usado}.")
        return

    try:
        X = preparar_X(df_obra)
        preds = pipeline.predict(X)
        risco_medio = preds.mean()
        
        status_ia = "🔴 Crítico" if risco_medio > 10 else "🟡 Alerta" if risco_medio > 7 else "🟢 Normal"
        
        texto_resp = (
            f"🏗️ **CCBJJ Risk Analysis ({modo_usado})**\n"
            f"----------------------------------\n"
            f"📍 **ID:** `{id_obra}`\n"
            f"📊 **Risco:** `{risco_medio:.1f} dias`\n"
            f"🚦 **Status:** {status_ia}\n"
            f"----------------------------------"
        )
        
        await update.message.reply_text(texto_resp, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        logging.error(f"Erro na predição: {e}")
        await update.message.reply_text("⚠️ Erro técnico no modelo de IA.")

# ======================================================
# INICIALIZAÇÃO DO SERVIDOR
# ======================================================
app = FastAPI()
ptb_app = None

@app.on_event("startup")
async def startup():
    global ptb_app
    ptb_app = ApplicationBuilder().token(TOKEN).build()
    
    # Registro de Handlers
    ptb_app.add_handler(CommandHandler("start", start_command))
    ptb_app.add_handler(CommandHandler("settings", settings_command))
    ptb_app.add_handler(CommandHandler("help", help_command))
    ptb_app.add_handler(CommandHandler("about", about_command))
    ptb_app.add_handler(CommandHandler("status", status_command))
    ptb_app.add_handler(CommandHandler("language", language_manual_command))
    ptb_app.add_handler(CommandHandler("healthcheck", healthcheck_command))
    
    ptb_app.add_handler(CallbackQueryHandler(config_callback, pattern='^set_'))
    ptb_app.add_handler(CallbackQueryHandler(language_callback, pattern='^lang_'))
    
    ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await ptb_app.initialize()
    await ptb_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    await ptb_app.start()

@app.post("/webhook")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return Response(status_code=200)

@app.get("/healthcheck")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
