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
from sqlalchemy import create_engine, text

# 1. CONFIGURAÇÕES DE AMBIENTE E SEGURANÇA
os.environ['MPLCONFIGDIR'] = '/tmp/matplotlib'
warnings.filterwarnings("ignore", category=UserWarning)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib.utils import ImageReader

# Ajuste de Path para módulos locais
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

from fastapi import FastAPI, Request, Response
import uvicorn
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)

import database
from i18n import get_text
from handlers import start_command, help_command, settings_command

# Configurações Globais
BR_TIMEZONE = pytz.timezone('America/Sao_Paulo')
BASE_DIR = Path(__file__).resolve().parent.parent
LOGO_PATH = BASE_DIR / "assets" / "logo_ccbjj.png"
PIPELINE_PATH = BASE_DIR / "models" / "pipeline_random_forest.pkl"
FEATURES_PATH = BASE_DIR / "models" / "features_metadata.joblib"
DB_PATH = BASE_DIR / "data" / "processed" / "df_mestre_consolidado.csv.gz"

# Cache de Recursos (Lazy Loading)
RESOURCES = {"pipeline": None, "features": None, "df_base": None, "engine": None}

def get_resources():
    if RESOURCES["pipeline"] is None:
        RESOURCES["pipeline"] = joblib.load(PIPELINE_PATH)
        RESOURCES["features"] = joblib.load(FEATURES_PATH)
        RESOURCES["df_base"] = pd.read_csv(DB_PATH, compression="gzip")
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            RESOURCES["engine"] = create_engine(db_url.replace("postgres://", "postgresql://"), pool_size=5)
    return RESOURCES

# --- AUXILIARES DE INTERFACE ---
def obter_menu_infra():
    keyboard = [[
        InlineKeyboardButton("📂 Modo CSV Local", callback_data='set_CSV'),
        InlineKeyboardButton("☁️ Modo Supabase Cloud", callback_data='set_DB')
    ]]
    return InlineKeyboardMarkup(keyboard)

# --- GERADORES DE MÍDIA (OTIMIZADOS) ---
def gerar_grafico_ia(risco_valor, id_obra, lang):
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(10, 5))
    cor = 'green' if risco_valor <= 7 else 'orange' if risco_valor <= 10 else 'red'
    
    ax.barh(['Impacto'], [risco_valor], color=cor, height=0.5)
    ax.set_xlim(0, 15)
    ax.set_title(f"{get_text(lang, 'chart_title')}: {id_obra}", fontsize=12, fontweight='bold')
    
    # Legenda técnica no rodapé da imagem
    plt.figtext(0.15, 0.02, get_text(lang, "chart_legend"), fontsize=9, bbox=dict(facecolor='white', alpha=0.5))
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    buf.seek(0)
    plt.close(fig)
    return buf

def gerar_pdf_corporativo(id_obra, risco, status, modo, graf_buf, lang):
    pdf_buf = io.BytesIO()
    c = canvas = canvas.Canvas(pdf_buf, pagesize=A4)
    width, height = A4
    now_br = datetime.now(BR_TIMEZONE).strftime('%d/%m/%Y %H:%M')

    # Cabeçalho com Logo
    if LOGO_PATH.exists():
        c.drawImage(str(LOGO_PATH), width/2 - 2*cm, height - 4*cm, width=4*cm, preserveAspectRatio=True)
    
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width/2, height - 6*cm, "CCBJJ ENGENHARIA")
    c.setFont("Helvetica", 14)
    c.drawCentredString(width/2, height - 7*cm, get_text(lang, "pdf_title"))
    c.line(2*cm, height - 8*cm, width - 2*cm, height - 8*cm)

    # Conteúdo Detalhado
    text_obj = c.beginText(2*cm, height - 9.5*cm)
    text_obj.setFont("Helvetica-Bold", 12)
    text_obj.textLine(get_text(lang, "pdf_section_1"))
    text_obj.setFont("Helvetica", 11)
    text_obj.textLine(f"• ID: {id_obra}")
    text_obj.textLine(f"• Status: {status}")
    text_obj.textLine(f"• Impacto: {risco:.2f} dias")
    text_obj.textLine(f"• Fonte: {modo} | Data: {now_br}")
    
    text_obj.moveCursor(0, 15)
    text_obj.setFont("Helvetica-Bold", 12)
    text_obj.textLine(get_text(lang, "pdf_section_2"))
    text_obj.setFont("Helvetica", 11)
    # Nota técnica simplificada para o PDF
    text_obj.textLine("Análise preditiva baseada em algoritmos de Machine Learning (Random Forest).")
    c.drawText(text_obj)

    # Imagem do Gráfico (via memória)
    graf_buf.seek(0)
    img_reader = ImageReader(graf_buf)
    c.drawImage(img_reader, 2*cm, height - 20*cm, width=17*cm, preserveAspectRatio=True)
    
    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(width/2, 2*cm, get_text(lang, "pdf_footer"))

    c.showPage()
    c.save()
    pdf_buf.seek(0)
    return pdf_buf

# --- CORE HANDLERS ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = database.get_language(user_id)
    modo = database.get_storage_mode(user_id)
    id_obra = update.message.text.strip().upper()

    res = get_resources()
    
    try:
        # 1. Busca Segura
        if modo == "SUPABASE" and res["engine"]:
            query = text("SELECT * FROM dashboard_obras WHERE UPPER(id_obra) = :val")
            df = pd.read_sql(query, res["engine"], params={"val": id_obra})
        else:
            df = res["df_base"][res["df_base"]["id_obra"].str.upper() == id_obra]

        if df.empty:
            await update.message.reply_text(get_text(lang, "not_found", id_obra=id_obra, modo=modo))
            return

        # 2. Predição Assíncrona
        wait_msg = await update.message.reply_text(get_text(lang, "processing"), parse_mode=ParseMode.MARKDOWN)
        
        X = df.reindex(columns=res["features"], fill_value=0)
        prediction = await asyncio.to_thread(res["pipeline"].predict, X)
        risco_val = float(prediction.mean())
        status = "🟢 NORMAL" if risco_val <= 7 else "🟡 ALERTA" if risco_val <= 10 else "🔴 CRÍTICO"

        # 3. Respostas
        await update.message.reply_text(
            f"{get_text(lang, 'report_header')}\n"
            f"ID: `{id_obra}`\n"
            f"{get_text(lang, 'report_status', status=status)}\n"
            f"{get_text(lang, 'report_impact', risco=risco_val)}\n\n"
            f"{get_text(lang, 'report_note', status=status)}",
            parse_mode=ParseMode.MARKDOWN
        )

        # 4. Mídia (Threads separadas para não travar o bot)
        graf_buf = await asyncio.to_thread(gerar_grafico_ia, risco_val, id_obra, lang)
        await update.message.reply_photo(photo=graf_buf)
        
        pdf_buf = await asyncio.to_thread(gerar_pdf_corporativo, id_obra, risco_val, status, modo, graf_buf, lang)
        await update.message.reply_document(
            document=InputFile(pdf_buf, filename=f"Relatorio_{id_obra}.pdf"),
            caption=get_text(lang, "sending_files"),
            parse_mode=ParseMode.MARKDOWN
        )
        await wait_msg.delete()

    except Exception as e:
        logging.exception(f"Erro ao processar ID {id_obra}")
        await update.message.reply_text("⚠️ Error / Erro Interno.")

# --- CONFIGURAÇÃO E CALLBACKS ---
async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split("_")[1]
    database.set_language(query.from_user.id, lang)
    
    await query.edit_message_text(
        text=f"{get_text(lang, 'language_changed')}\n\n{get_text(lang, 'infra_select')}",
        reply_markup=obter_menu_infra(),
        parse_mode=ParseMode.MARKDOWN
    )

async def config_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    modo = "CSV" if query.data == 'set_CSV' else "SUPABASE"
    database.set_storage_mode(query.from_user.id, modo)
    lang = database.get_language(query.from_user.id)
    
    await query.edit_message_text(
        text=get_text(lang, "setup_complete", modo=modo),
        parse_mode=ParseMode.MARKDOWN
    )

# --- STARTUP ---
app = FastAPI()
ptb_app = None

@app.on_event("startup")
async def startup():
    global ptb_app
    token = os.getenv("TELEGRAM_TOKEN")
    webhook_url = os.getenv("WEBHOOK_URL")
    
    ptb_app = ApplicationBuilder().token(token).build()
    
    # Handlers
    ptb_app.add_handler(CommandHandler("start", start_command))
    ptb_app.add_handler(CommandHandler("help", help_command))
    ptb_app.add_handler(CommandHandler("settings", settings_command))
    ptb_app.add_handler(CallbackQueryHandler(language_callback, pattern='^lang_'))
    ptb_app.add_handler(CallbackQueryHandler(config_callback, pattern='^set_'))
    ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    await ptb_app.initialize()
    await ptb_app.bot.set_webhook(f"{webhook_url}/webhook")
    await ptb_app.start()

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    await ptb_app.process_update(Update.de_json(data, ptb_app.bot))
    return Response(status_code=200)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
