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

# Importações customizadas
import database
from i18n import TEXTS
from handlers import (
    start_command, help_command, about_command, 
    status_command, language_callback, resolve_language,
    language_manual_command, example_command, healthcheck_command
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Configuração de Logging
logging.basicConfig(level=logging.INFO)
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

# Carrega CSV e normaliza dados de busca
df_base = pd.read_csv(DB_PATH, compression="gzip")
if "id_obra" in df_base.columns:
    df_base["id_obra"] = df_base["id_obra"].astype(str).str.strip()

# ======================================================
# FUNÇÕES DE APOIO
# ======================================================

def obter_menu_infra():
    """Gera o teclado para escolha da fonte de dados."""
    keyboard = [[
        InlineKeyboardButton("📂 Modo CSV", callback_data='set_CSV'),
        InlineKeyboardButton("☁️ Modo Supabase", callback_data='set_DB'),
    ]]
    return InlineKeyboardMarkup(keyboard)

async def get_data(id_obra, user_id):
    """Busca dados usando a preferência salva no banco SQLite local."""
    mode = database.get_storage_mode(user_id)
    id_obra_clean = id_obra.strip()
    
    if mode == "SUPABASE" and engine:
        try:
            query = f"SELECT * FROM dashboard_obras WHERE id_obra ILIKE '{id_obra_clean}'"
            df = pd.read_sql(query, engine)
            return df, "SUPABASE"
        except Exception as e:
            logging.error(f"Erro Supabase: {e}")
            # Fallback automático para CSV se o banco falhar
            df = df_base[df_base["id_obra"].str.contains(id_obra_clean, case=False, na=False)]
            return df, "CSV (Fallback)"
    else:
        df = df_base[df_base["id_obra"].str.contains(id_obra_clean, case=False, na=False)]
        return df, "CSV"

def preparar_X(df):
    """Prepara o DataFrame para o pipeline de predição."""
    X = df.copy()
    for col in features_order:
        if col not in X.columns: 
            X[col] = 0
    return X[features_order].fillna(0)

# ======================================================
# HANDLERS ADICIONAIS
# ======================================================

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando para alterar a fonte de dados (CSV/Supabase)."""
    lang = resolve_language(update)
    await update.message.reply_text(
        TEXTS[lang]["infra_select"],
        reply_markup=obter_menu_infra(),
        parse_mode=ParseMode.MARKDOWN
    )

async def config_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa a escolha do usuário no menu de infraestrutura."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang = resolve_language(update)
    
    mode = "CSV" if query.data == 'set_CSV' else "SUPABASE"
    database.set_storage_mode(user_id, mode)
    
    msg = f"{TEXTS[lang]['mode_changed']}**{mode}**"
    await query.edit_message_text(text=msg, parse_mode=ParseMode.MARKDOWN)

# ======================================================
# HANDLER DE MENSAGEM PRINCIPAL
# ======================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lógica principal de recebimento do ID e predição de IA."""
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
        
        # Lógica de semáforo de risco
        status_ia = "🔴 Crítico" if risco_medio > 10 else "🟡 Alerta" if risco_medio > 7 else "🟢 Normal"
        
        texto_resp = (
            f"🏗️ **CCBJJ Risk Analysis ({modo_usado})**\n"
            f"----------------------------------\n"
            f"📍 **ID:** `{id_obra}`\n"
            f"📊 **Risco Estimado:** `{risco_medio:.1f} dias`\n"
            f"🚦 **Status:** {status_ia}\n"
            f"----------------------------------"
        )
        
        await update.message.reply_text(texto_resp, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        logging.error(f"Erro na predição: {e}")
        await update.message.reply_text("⚠️ Erro técnico no processamento da IA.")

# ======================================================
# INICIALIZAÇÃO DO SERVIDOR (FASTAPI + WEBHOOK)
# ======================================================
app = FastAPI()
ptb_app = None

@app.on_event("startup")
async def startup():
    global ptb_app
    ptb_app = ApplicationBuilder().token(TOKEN).build()
    
    # Registro de Handlers de Comando e Mensagem
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

    # Inicialização do Bot e Webhook
    await ptb_app.initialize()
    try:
        await ptb_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
        logging.info(f"Webhook definido com sucesso: {WEBHOOK_URL}/webhook")
    except Exception as e:
        logging.error(f"Falha ao definir Webhook: {e}")
    
    await ptb_app.start()

@app.post("/webhook")
async def webhook_handler(request: Request):
    """Endpoint que recebe as atualizações do Telegram."""
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return Response(status_code=200)

@app.get("/healthcheck")
async def health():
    """Verificação de integridade para o Render."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
