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
LOGO_PATH = BASE_DIR / "assets/logo_ccbjj.png"
HISTORY_PATH = BASE_DIR / "data/history/analises_history.csv"

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
DATABASE_URL = os.getenv("DATABASE_URL")
BR_TIMEZONE = pytz.timezone('America/Sao_Paulo')

# Ajuste da URL do banco para o SQLAlchemy
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Inicialização de Recursos
pipeline = joblib.load(PIPELINE_PATH)
features_order = joblib.load(FEATURES_PATH)
engine = create_engine(DATABASE_URL) if DATABASE_URL else None

# Carrega CSV (Legado)
df_base = pd.read_csv(DB_PATH, compression="gzip")
if "id_obra" in df_base.columns:
    df_base["id_obra"] = df_base["id_obra"].astype(str).str.strip().str.upper()

# Armazenamento temporário de preferência (Em produção, ideal usar banco)
USER_PREFERENCE = {} # {user_id: 'SUPABASE' ou 'CSV'}

# ======================================================
# FUNÇÕES DE APOIO E INFRAESTRUTURA
# ======================================================

async def get_data(id_obra, user_id):
    """Busca dados na fonte escolhida pelo usuário."""
    mode = USER_PREFERENCE.get(user_id, "SUPABASE") # Padrão Cloud
    
    if mode == "SUPABASE" and engine:
        query = f"SELECT * FROM dashboard_obras WHERE id_obra = '{id_obra}'"
        df = pd.read_sql(query, engine)
        return df, "SUPABASE"
    else:
        df = df_base[df_base["id_obra"] == id_obra]
        return df, "CSV"

def preparar_X(df):
    """Ajusta os dados para o formato que o seu PKL espera."""
    X = df.copy()
    # Mapeia colunas do banco/csv para o que o modelo espera se necessário
    # O pipeline_random_forest.pkl exige as features exatas do treino
    for col in features_order:
        if col not in X.columns: 
            X[col] = 0
    return X[features_order].fillna(0)

# [Mantenha aqui as suas funções gerar_pdf_corporativo, salvar_historico e gerar_grafico sem alterações]
# (Omitidas aqui para brevidade, mas devem permanecer no seu arquivo)

# ======================================================
# HANDLERS DE COMANDO
# ======================================================

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu para escolher entre CSV e Supabase."""
    keyboard = [
        [
            InlineKeyboardButton("📂 Modo CSV (Legado)", callback_data='set_CSV'),
            InlineKeyboardButton("☁️ Modo Supabase (Cloud)", callback_data='set_DB'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "⚙️ **Configurações de Infraestrutura**\nEscolha como deseja processar os dados:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def config_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if query.data == 'set_CSV':
        USER_PREFERENCE[user_id] = "CSV"
        msg = "✅ Modo alterado para: **CSV (Local)**"
    else:
        USER_PREFERENCE[user_id] = "SUPABASE"
        msg = "✅ Modo alterado para: **Supabase (Nuvem)**"
    
    await query.edit_message_text(text=msg, parse_mode=ParseMode.MARKDOWN)

# ======================================================
# HANDLER PRINCIPAL DE ANÁLISE (IA + INFRA)
# ======================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_obra = update.message.text.strip().upper()
    lang = resolve_language(update)
    user_id = update.effective_user.id
    
    # 1. Busca de Dados Híbrida
    df_obra, modo_usado = await get_data(id_obra, user_id)

    if df_obra.empty:
        not_found_msg = "❌ Project not found." if lang == "en" else "❌ ID da obra não localizado."
        await update.message.reply_text(not_found_msg)
        return

    try:
        # 2. Processamento com o PKL antigo
        X = preparar_X(df_obra)
        preds = pipeline.predict(X)
        risco_medio = preds.mean()
        
        idx_max = preds.argmax()
        etapa_critica = df_obra.iloc[idx_max]["etapa"]
        
        # 3. Formatação da Resposta (Sua lógica original de tradução)
        status_ia = "🔴 Crítico" if risco_medio > 10 else "🟡 Alerta" if risco_medio > 7 else "🟢 Normal"
        
        # [Seu bloco de montagem de texto_resp aqui...]
        
        texto_resp = (
            f"🏗️ **CCBJJ Intelligence ({modo_usado})**\n"
            f"----------------------------------\n"
            f"📍 **Projeto:** `{id_obra}`\n"
            f"📊 **Risco Médio:** `{risco_medio:.1f} dias`\n"
            f"🚦 **Status:** {status_ia}\n"
            f"⚠️ **Ponto Crítico:** `{etapa_critica}`\n"
            f"----------------------------------\n"
            f"_Processado via infraestrutura híbrida._"
        )
        
        # 4. Envio de Gráficos e PDF (Seus métodos originais)
        await update.message.reply_text(texto_resp, parse_mode=ParseMode.MARKDOWN)
        
        graf_buf = gerar_grafico(df_obra, preds, id_obra, lang=lang)
        await update.message.reply_photo(photo=graf_buf, caption="📈 Análise Preditiva")
        
        # Registro no histórico
        salvar_historico(user_id, id_obra, risco_medio, status_ia, modo_usado, lang)

    except Exception as e:
        logging.error(f"Erro no processamento: {e}")
        await update.message.reply_text("⚠️ Erro técnico ao processar IA.")

# ======================================================
# APLICAÇÃO E WEBHOOK
# ======================================================
app = FastAPI()
ptb_app = None

@app.on_event("startup")
async def startup():
    global ptb_app
    ptb_app = ApplicationBuilder().token(TOKEN).build()
    
    # Handlers Originais
    ptb_app.add_handler(CommandHandler("start", start_command))
    ptb_app.add_handler(CommandHandler("settings", settings_command)) # Novo comando
    ptb_app.add_handler(CallbackQueryHandler(config_callback, pattern='^set_')) # Novo callback
    
    # Handlers de Sistema
    ptb_app.add_handler(CallbackQueryHandler(language_callback, pattern='^lang_'))
    ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # ... outros handlers (about, help, etc) ...

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
