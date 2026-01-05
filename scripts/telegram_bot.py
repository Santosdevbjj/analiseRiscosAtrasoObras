import os 
import sys
import logging
import warnings
import joblib
import pandas as pd
import pytz
import csv
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
from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Relatórios PDF
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# Importações customizadas
from i18n import TEXTS
from database import get_language, set_language
from handlers import (
    help_command, about_command, 
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
LOGO_PATH = BASE_DIR / "assets/logo_ccbjj.png"
HISTORY_PATH = BASE_DIR / "data/history/analises_history.csv"

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
DATABASE_URL = os.getenv("DATABASE_URL")
BR_TIMEZONE = pytz.timezone('America/Sao_Paulo')

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

pipeline = joblib.load(PIPELINE_PATH)
features_order = joblib.load(FEATURES_PATH)
engine = create_engine(DATABASE_URL) if DATABASE_URL else None

df_base = pd.read_csv(DB_PATH, compression="gzip")
if "id_obra" in df_base.columns:
    df_base["id_obra"] = df_base["id_obra"].astype(str).str.strip()

USER_PREFERENCE = {}

# ======================================================
# FUNÇÕES DE APOIO
# ======================================================

def obter_menu_infra():
    keyboard = [
        [
            InlineKeyboardButton("📂 Modo CSV (Legado)", callback_data='set_CSV'),
            InlineKeyboardButton("☁️ Modo Supabase (Cloud)", callback_data='set_DB'),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def get_data(id_obra, user_id):
    mode = USER_PREFERENCE.get(user_id, "SUPABASE")
    id_obra_clean = id_obra.strip()
    
    if mode == "SUPABASE" and engine:
        # ILIKE resolve o problema de CCbjj vs CCBJJ
        query = f"SELECT * FROM dashboard_obras WHERE id_obra ILIKE '{id_obra_clean}'"
        df = pd.read_sql(query, engine)
        return df, "SUPABASE"
    else:
        # Busca insensível no Pandas
        df = df_base[df_base["id_obra"].str.contains(id_obra_clean, case=False, na=False)]
        return df, "CSV"

def preparar_X(df):
    X = df.copy()
    for col in features_order:
        if col not in X.columns: 
            X[col] = 0
    return X[features_order].fillna(0)

# [Mantenha aqui gerar_pdf_corporativo, salvar_historico e gerar_grafico]

# ======================================================
# NOVOS HANDLERS
# ======================================================

async def start_hibrido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Substitui o start antigo para garantir que os botões apareçam."""
    await update.message.reply_text(
        "🏗️ **CCBJJ Risk Intelligence**\n\n"
        "Sistema ativo. Por favor, selecione a fonte de dados para análise:",
        reply_markup=obter_menu_infra(),
        parse_mode=ParseMode.MARKDOWN
    )

async def config_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    mode = "CSV" if query.data == 'set_CSV' else "SUPABASE"
    USER_PREFERENCE[user_id] = mode
    await query.edit_message_text(text=f"✅ Infraestrutura definida: **{mode}**\nAgora envie o ID da obra (ex: CCbjj-100).", parse_mode=ParseMode.MARKDOWN)

# ======================================================
# HANDLER DE MENSAGEM
# ======================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_obra = update.message.text.strip()
    lang = resolve_language(update)
    user_id = update.effective_user.id
    
    df_obra, modo_usado = await get_data(id_obra, user_id)

    if df_obra.empty:
        await update.message.reply_text(f"❌ Obra `{id_obra}` não encontrada no {modo_usado}.")
        return

    try:
        X = preparar_X(df_obra)
        preds = pipeline.predict(X)
        risco_medio = preds.mean()
        
        # Simplificação para teste, use sua lógica de tradução completa aqui
        status_ia = "🔴 Crítico" if risco_medio > 10 else "🟢 Normal"
        
        texto_resp = (
            f"📊 **Resultado IA ({modo_usado})**\n"
            f"ID: `{id_obra}`\n"
            f"Risco Estimado: `{risco_medio:.1f} dias`\n"
            f"Status: {status_ia}"
        )
        
        await update.message.reply_text(texto_resp, parse_mode=ParseMode.MARKDOWN)
        # Opcional: Adicione gerar_grafico aqui se desejar
        
    except Exception as e:
        logging.error(f"Erro: {e}")
        await update.message.reply_text("⚠️ Erro ao processar predição.")

# ======================================================
# INICIALIZAÇÃO
# ======================================================
app = FastAPI()
ptb_app = None

@app.on_event("startup")
async def startup():
    global ptb_app
    ptb_app = ApplicationBuilder().token(TOKEN).build()
    
    # Adicionando Handlers
    ptb_app.add_handler(CommandHandler("start", start_hibrido)) # Usando o novo start
    ptb_app.add_handler(CallbackQueryHandler(config_callback, pattern='^set_'))
    ptb_app.add_handler(CallbackQueryHandler(language_callback, pattern='^lang_'))
    ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Comandos auxiliares do handlers.py
    ptb_app.add_handler(CommandHandler("help", help_command))
    ptb_app.add_handler(CommandHandler("healthcheck", healthcheck_command))

    await ptb_app.initialize()
    await ptb_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    await ptb_app.start()

@app.post("/webhook")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return Response(status_code=200)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
