import os
import sys
import io
import joblib
import pandas as pd
import pytz
import logging
import warnings
import asyncio
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, text # Importado text para consultas seguras

# 1. SEGURANÇA E AMBIENTE
os.environ['MPLCONFIGDIR'] = '/tmp/matplotlib'
warnings.filterwarnings("ignore", category=UserWarning) # Trata avisos do ML

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib.utils import ImageReader # Para evitar escrita em disco

# Ajuste de Path
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

from fastapi import FastAPI, Request, Response
import uvicorn
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

import database
from i18n import TEXTS
from handlers import start_command, help_command

# Configurações Globais
BR_TIMEZONE = pytz.timezone('America/Sao_Paulo')
BASE_DIR = Path(__file__).resolve().parent.parent
LOGO_PATH = BASE_DIR / "assets" / "logo_ccbjj.png"
PIPELINE_PATH = BASE_DIR / "models" / "pipeline_random_forest.pkl"
FEATURES_PATH = BASE_DIR / "models" / "features_metadata.joblib"
DB_PATH = BASE_DIR / "data" / "processed" / "df_mestre_consolidado.csv.gz"

# Carregamento Otimizado (Cache Simples)
RESOURCES = {
    "pipeline": None,
    "features": None,
    "df_base": None,
    "engine": None
}

def get_resources():
    """Carrega recursos sob demanda para economizar memória inicial."""
    if RESOURCES["pipeline"] is None:
        RESOURCES["pipeline"] = joblib.load(PIPELINE_PATH)
        RESOURCES["features"] = joblib.load(FEATURES_PATH)
        RESOURCES["df_base"] = pd.read_csv(DB_PATH, compression="gzip")
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            RESOURCES["engine"] = create_engine(db_url.replace("postgres://", "postgresql://"))
    return RESOURCES

# --- UI HELPER ---
def obter_menu_infra():
    keyboard = [[
        InlineKeyboardButton("📂 Modo CSV Local", callback_data='set_CSV'),
        InlineKeyboardButton("☁️ Modo Supabase Cloud", callback_data='set_DB')
    ]]
    return InlineKeyboardMarkup(keyboard)

# --- GERADORES EFICIENTES (SEM DISCO) ---
def gerar_grafico_ia(risco_valor, id_obra):
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(10, 5))
    cor = 'green' if risco_valor <= 7 else 'orange' if risco_valor <= 10 else 'red'
    ax.barh(['Impacto Previsto'], [risco_valor], color=cor, height=0.5)
    ax.set_xlim(0, 15)
    ax.set_title(f'Análise de Risco: {id_obra}', fontsize=12, fontweight='bold')
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    buf.seek(0)
    plt.close(fig)
    return buf

def gerar_pdf_corporativo(id_obra, risco, status, modo, graf_buf, lang):
    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=A4)
    width, height = A4
    now_br = datetime.now(BR_TIMEZONE).strftime('%d/%m/%Y %H:%M')

    # CAPA E LOGO
    if LOGO_PATH.exists():
        c.drawImage(str(LOGO_PATH), width/2 - 2*cm, height - 4*cm, width=4*cm, preserveAspectRatio=True)
    
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width/2, height - 6*cm, "CCBJJ ENGENHARIA")
    c.line(2*cm, height - 7*cm, width - 2*cm, height - 7*cm)

    # TEXTO (Internacionalizado no futuro ou fixo estruturado)
    text = c.beginText(2*cm, height - 8.5*cm)
    text.setFont("Helvetica-Bold", 12)
    text.textLine(f"ID: {id_obra} | Status: {status}")
    text.textLine(f"Impacto: {risco:.2f} dias | Data: {now_br}")
    c.drawText(text)

    # GRÁFICO DIRETO DA MEMÓRIA (ImageReader)
    graf_buf.seek(0)
    img_reader = ImageReader(graf_buf)
    c.drawImage(img_reader, 2*cm, height - 18*cm, width=17*cm, preserveAspectRatio=True)
    
    c.showPage()
    c.save()
    pdf_buf.seek(0)
    return pdf_buf

# --- PROCESSAMENTO ASSÍNCRONO E SEGURO ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = database.get_language(user_id)
    modo = database.get_storage_mode(user_id)
    id_obra = update.message.text.strip().upper()

    res = get_resources()
    
    try:
        # 1. BUSCA SEGURA (SQL Parametrizado)
        if modo == "SUPABASE" and res["engine"]:
            query = text("SELECT * FROM dashboard_obras WHERE UPPER(id_obra) = :val")
            df = pd.read_sql(query, res["engine"], params={"val": id_obra})
        else:
            df = res["df_base"][res["df_base"]["id_obra"].str.upper() == id_obra]

        if df.empty:
            # Internacionalização da falha
            msg_erro = f"❌ {id_obra} {TEXTS[lang].get('not_found', 'não localizado')} ({modo})."
            await update.message.reply_text(msg_erro)
            return

        # 2. PREDIÇÃO
        X = df.reindex(columns=res["features"], fill_value=0)
        # Executa predição em thread para não bloquear o loop de eventos
        risco = await asyncio.to_thread(res["pipeline"].predict, X)
        risco_val = float(risco.mean())
        status = "🟢 NORMAL" if risco_val <= 7 else "🟡 ALERTA" if risco_val <= 10 else "🔴 CRÍTICO"

        # 3. RESPOSTA TEXTUAL
        await update.message.reply_text(f"🏗️ **Análise CCBJJ**\nID: `{id_obra}`\nStatus: {status}\nImpacto: `{risco_val:.2f} dias`", parse_mode=ParseMode.MARKDOWN)

        # 4. GERAÇÃO DE MÍDIA (Off-loop)
        graf_buf = await asyncio.to_thread(gerar_grafico_ia, risco_val, id_obra)
        await update.message.reply_photo(photo=graf_buf)
        
        pdf_buf = await asyncio.to_thread(gerar_pdf_corporativo, id_obra, risco_val, status, modo, graf_buf, lang)
        await update.message.reply_document(document=InputFile(pdf_buf, filename=f"CCBJJ_{id_obra}.pdf"))

    except Exception as e:
        logging.exception(f"Erro ao processar ID {id_obra}")
        await update.message.reply_text("⚠️ Erro interno no processamento. Tente novamente em instantes.")

# --- CALLBACKS ---
async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split("_")[1]
    database.set_language(query.from_user.id, lang)
    
    # Fluxo contínuo: Idioma -> Modo
    await query.edit_message_text(
        text=f"✅ {TEXTS[lang]['language_changed']}\n\n{TEXTS[lang]['infra_select']}",
        reply_markup=obter_menu_infra(),
        parse_mode=ParseMode.MARKDOWN
    )

async def config_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    modo = "CSV" if query.data == 'set_CSV' else "SUPABASE"
    database.set_storage_mode(query.from_user.id, modo)
    lang = database.get_language(query.from_user.id)
    await query.edit_message_text(f"✅ Setup: `{lang.upper()}` | `{modo}`\n\n{TEXTS[lang]['help']}", parse_mode=ParseMode.MARKDOWN)

# --- APP STARTUP ---
app = FastAPI()
ptb_app = None

@app.on_event("startup")
async def startup():
    global ptb_app
    token = os.getenv("TELEGRAM_TOKEN")
    webhook = os.getenv("WEBHOOK_URL")
    
    ptb_app = ApplicationBuilder().token(token).build()
    ptb_app.add_handler(CommandHandler("start", start_command))
    ptb_app.add_handler(CallbackQueryHandler(language_callback, pattern='^lang_'))
    ptb_app.add_handler(CallbackQueryHandler(config_callback, pattern='^set_'))
    ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    await ptb_app.initialize()
    await ptb_app.bot.set_webhook(f"{webhook}/webhook")
    await ptb_app.start()

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    await ptb_app.process_update(Update.de_json(data, ptb_app.bot))
    return Response(status_code=200)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
