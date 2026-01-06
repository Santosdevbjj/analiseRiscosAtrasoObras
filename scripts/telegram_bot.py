import os
import sys
import io
import joblib
import pandas as pd
import pytz
import logging
import warnings
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine

# 1. CORREÇÃO PARA O RENDER: Cache do Matplotlib e Interface Headless
os.environ['MPLCONFIGDIR'] = '/tmp/matplotlib'
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

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
from reportlab.lib import colors

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

# Carregamento de Recursos
pipeline = joblib.load(PIPELINE_PATH)
features_order = joblib.load(FEATURES_PATH)
df_base = pd.read_csv(DB_PATH, compression="gzip")
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL.replace("postgres://", "postgresql://")) if DATABASE_URL else None

# --- UI HELPER ---
def obter_menu_infra():
    keyboard = [[
        InlineKeyboardButton("📂 Modo CSV Local", callback_data='set_CSV'),
        InlineKeyboardButton("☁️ Modo Supabase Cloud", callback_data='set_DB')
    ]]
    return InlineKeyboardMarkup(keyboard)

# --- GERADORES ---
def gerar_grafico_ia(risco_valor, id_obra):
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(10, 5))
    cor = 'green' if risco_valor <= 7 else 'orange' if risco_valor <= 10 else 'red'
    ax.barh(['Impacto Previsto'], [risco_valor], color=cor, height=0.5)
    ax.set_xlim(0, 15)
    ax.set_title(f'Análise de Risco: {id_obra}', fontsize=12, fontweight='bold')
    
    legenda = f"Status: {'NORMAL' if cor=='green' else 'ALERTA' if cor=='orange' else 'CRÍTICO'}\n" \
              "🟢 0-7 dias | 🟡 7-10 dias | 🔴 >10 dias"
    plt.figtext(0.15, 0.02, legenda, fontsize=10, bbox=dict(facecolor='white', alpha=0.5))
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    return buf

def gerar_pdf_corporativo(id_obra, risco, status, modo, graf_buf):
    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=A4)
    width, height = A4
    now_br = datetime.now(BR_TIMEZONE).strftime('%d/%m/%Y %H:%M')

    # --- CAPA E LOGO ---
    if LOGO_PATH.exists():
        c.drawImage(str(LOGO_PATH), width/2 - 2*cm, height - 4*cm, width=4*cm, preserveAspectRatio=True)
    
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(width/2, height - 6.5*cm, "CCBJJ ENGENHARIA")
    c.setFont("Helvetica", 14)
    c.drawCentredString(width/2, height - 7.5*cm, "RELATÓRIO TÉCNICO DE INTELIGÊNCIA PREDITIVA")
    c.setFont("Helvetica-Oblique", 9)
    c.drawCentredString(width/2, height - 8.2*cm, f"Gerado em: {now_br} (Brasília)")
    c.line(2*cm, height - 9*cm, width - 2*cm, height - 9*cm)

    # --- TEXTO DETALHADO ---
    text = c.beginText(2*cm, height - 10.5*cm)
    text.setFont("Helvetica-Bold", 12)
    text.textLine("1. DIAGNÓSTICO DE RISCO")
    text.setFont("Helvetica", 11)
    text.textLine(f"• ID da Obra: {id_obra}")
    text.textLine(f"• Fonte de Dados: {modo}")
    text.textLine(f"• Status Atual: {status}")
    text.textLine(f"• Atraso Previsto: {risco:.2f} dias")
    text.moveCursor(0, 15)
    text.setFont("Helvetica-Bold", 12)
    text.textLine("2. ANÁLISE PREDITIVA (ML)")
    text.setFont("Helvetica", 11)
    text.textLine("O modelo Random Forest analisou variáveis críticas de produtividade")
    text.textLine("e logística. O impacto calculado sugere uma atenção especial aos")
    text.textLine("marcos de entrega da unidade para mitigar os dias previstos.")
    c.drawText(text)

    # --- GRÁFICO ---
    graf_buf.seek(0)
    temp_img = f"tmp_{id_obra}.png"
    with open(temp_img, "wb") as f: f.write(graf_buf.read())
    c.drawImage(temp_img, 2*cm, 3*cm, width=17*cm, preserveAspectRatio=True)
    
    c.showPage()
    c.save()
    if os.path.exists(temp_img): os.remove(temp_img)
    pdf_buf.seek(0)
    return pdf_buf

# --- HANDLERS ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_obra = update.message.text.strip().upper()
    user_id = update.effective_user.id
    lang = database.get_language(user_id)
    modo = database.get_storage_mode(user_id)

    # Busca Insensível
    if modo == "SUPABASE" and engine:
        try:
            df = pd.read_sql(f"SELECT * FROM dashboard_obras WHERE UPPER(id_obra) = '{id_obra}'", engine)
        except: df = df_base[df_base["id_obra"].str.upper() == id_obra]
    else:
        df = df_base[df_base["id_obra"].str.upper() == id_obra]

    if df.empty:
        await update.message.reply_text(f"❌ ID `{id_obra}` não localizado no modo `{modo}`.")
        return

    X = df.reindex(columns=features_order, fill_value=0)
    risco = float(pipeline.predict(X).mean())
    status = "🟢 NORMAL" if risco <= 7 else "🟡 ALERTA" if risco <= 10 else "🔴 CRÍTICO"
    
    relatorio_txt = (
        f"🏗️ **ANÁLISE CCBJJ ENGENHARIA**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 **Unidade:** `{id_obra}`\n"
        f"🔌 **Base:** `{modo}`\n"
        f"🚦 **Risco:** {status}\n"
        f"⏳ **Impacto Previsto:** `{risco:.2f} dias` de atraso\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 **Nota Técnica:**\n"
        f"O modelo de IA detectou um padrão de desvio baseado em dados históricos. "
        f"Recomenda-se revisão imediata do cronograma desta unidade.\n\n"
        f"_Enviando arquivos detalhados..._"
    )
    await update.message.reply_text(relatorio_txt, parse_mode=ParseMode.MARKDOWN)

    graf = gerar_grafico_ia(risco, id_obra)
    await update.message.reply_photo(photo=graf, caption="📊 Gráfico de Dispersão de Risco.")
    
    pdf = gerar_pdf_corporativo(id_obra, risco, status, modo, graf)
    await update.message.reply_document(document=InputFile(pdf, filename=f"Relatorio_{id_obra}.pdf"))

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split("_")[1]
    database.set_language(query.from_user.id, lang)
    # FORÇA O MENU DE MODO A APARECER APÓS O IDIOMA
    await query.edit_message_text(
        text=f"✅ Idioma: {lang.upper()}\n\n{TEXTS[lang]['infra_select']}",
        reply_markup=obter_menu_infra(),
        parse_mode=ParseMode.MARKDOWN
    )

async def config_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    modo = "CSV" if query.data == 'set_CSV' else "SUPABASE"
    database.set_storage_mode(query.from_user.id, modo)
    lang = database.get_language(query.from_user.id)
    await query.edit_message_text(f"✅ Configuração Concluída!\n\nIdiomas e Fonte `{modo}` configurados.\n\n{TEXTS[lang]['help']}", parse_mode=ParseMode.MARKDOWN)

# --- FASTAPI ---
app = FastAPI()
ptb_app = None

@app.on_event("startup")
async def startup():
    global ptb_app
    ptb_app = ApplicationBuilder().token(TOKEN).build()
    ptb_app.add_handler(CommandHandler("start", start_command))
    ptb_app.add_handler(CommandHandler("help", help_command))
    ptb_app.add_handler(CallbackQueryHandler(language_callback, pattern='^lang_'))
    ptb_app.add_handler(CallbackQueryHandler(config_callback, pattern='^set_'))
    ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await ptb_app.initialize()
    await ptb_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    await ptb_app.start()

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    await ptb_app.process_update(Update.de_json(data, ptb_app.bot))
    return Response(status_code=200)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
