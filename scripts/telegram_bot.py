import os 
import sys
import logging
import joblib
import pandas as pd
import pytz
import io
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine

# Ajuste de PATH para módulos locais
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

from fastapi import FastAPI, Request, Response
import uvicorn

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib import colors
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import database
from i18n import TEXTS
from handlers import start_command, help_command, resolve_language

# Fuso Horário Brasília
BR_TIMEZONE = pytz.timezone('America/Sao_Paulo')

logging.basicConfig(level=logging.INFO)

# CAMINHOS
BASE_DIR = Path(__file__).resolve().parent.parent
LOGO_PATH = BASE_DIR / "assets" / "logo_ccbjj.png"
PIPELINE_PATH = BASE_DIR / "models" / "pipeline_random_forest.pkl"
FEATURES_PATH = BASE_DIR / "models" / "features_metadata.joblib"
DB_PATH = BASE_DIR / "data" / "processed" / "df_mestre_consolidado.csv.gz"

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
DATABASE_URL = os.getenv("DATABASE_URL")

# Carregamento de Recursos
pipeline = joblib.load(PIPELINE_PATH)
features_order = joblib.load(FEATURES_PATH)
engine = create_engine(DATABASE_URL.replace("postgres://", "postgresql://")) if DATABASE_URL else None
df_base = pd.read_csv(DB_PATH, compression="gzip")

# ======================================================
# FUNÇÕES DE INTERFACE (MENUS)
# ======================================================

def obter_menu_infra():
    """Retorna o teclado de escolha de infraestrutura."""
    keyboard = [[
        InlineKeyboardButton("📂 Modo CSV Local", callback_data='set_CSV'),
        InlineKeyboardButton("☁️ Modo Supabase Cloud", callback_data='set_DB'),
    ]]
    return InlineKeyboardMarkup(keyboard)

# ======================================================
# CALLBACKS (PROCESSAMENTO DE CLIQUES)
# ======================================================

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Escolha do idioma -> Salva -> CHAMA O MENU DE MODO AUTOMATICAMENTE"""
    query = update.callback_query
    await query.answer()
    
    lang = query.data.split("_")[1] # pt ou en
    user_id = query.from_user.id
    database.set_language(user_id, lang)
    
    # Edita a mensagem confirmando idioma e já oferecendo a INFRAESTRUTURA
    await query.edit_message_text(
        text=f"{TEXTS[lang]['language_changed']}\n\n{TEXTS[lang]['infra_select']}",
        reply_markup=obter_menu_infra(),
        parse_mode=ParseMode.MARKDOWN
    )

async def config_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Escolha da Infra -> Salva -> Finaliza Onboarding"""
    query = update.callback_query
    await query.answer()
    
    mode = "CSV" if query.data == 'set_CSV' else "SUPABASE"
    user_id = query.from_user.id
    database.set_storage_mode(user_id, mode)
    
    lang = database.get_language(user_id)
    confirm_msg = "✅ Configuração Concluída!" if lang == "pt" else "✅ Setup Complete!"
    
    await query.edit_message_text(
        text=f"{confirm_msg}\n🌐 Idioma: `{lang.upper()}`\n🔌 Infra: `{mode}`\n\n{TEXTS[lang]['help']}",
        parse_mode=ParseMode.MARKDOWN
    )

# ======================================================
# GERAÇÃO DE PDF E GRÁFICOS
# ======================================================

def gerar_grafico_ia(risco_valor, id_obra):
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(10, 5))
    cor = 'green' if risco_valor <= 7 else 'orange' if risco_valor <= 10 else 'red'
    ax.barh(['Impacto Previsto'], [risco_valor], color=cor, height=0.5)
    ax.set_xlim(0, max(15, risco_valor + 3))
    ax.set_title(f'Análise de Risco: {id_obra}', fontsize=12, fontweight='bold')
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    return buf

def gerar_pdf_final(id_obra, risco, status, modo, graf_buf):
    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=A4)
    width, height = A4
    
    # Capa com Logo
    if LOGO_PATH.exists():
        c.drawImage(str(LOGO_PATH), 2*cm, height - 4*cm, width=3*cm, preserveAspectRatio=True)
    
    c.setFont("Helvetica-Bold", 18)
    c.drawString(6*cm, height - 3*cm, "CCBJJ ENGENHARIA")
    c.setFont("Helvetica", 12)
    c.drawString(6*cm, height - 3.7*cm, "Relatório Preditivo de Impacto em Cronograma")
    
    c.line(2*cm, height - 4.5*cm, width - 2*cm, height - 4.5*cm)

    # Dados
    text = c.beginText(2*cm, height - 6*cm)
    text.setFont("Helvetica-Bold", 12)
    text.textLine(f"ID DA OBRA: {id_obra}")
    text.textLine(f"FONTE DE DADOS: {modo}")
    text.textLine(f"DATA DO RELATÓRIO: {datetime.now(BR_TIMEZONE).strftime('%d/%m/%Y %H:%M')}")
    text.moveCursor(0, 10)
    text.setFont("Helvetica", 11)
    text.textLine(f"Resultado da Análise: {status}")
    text.textLine(f"Atraso Estimado: {risco:.2f} dias")
    c.drawText(text)

    # Imagem
    graf_buf.seek(0)
    temp_img = f"tmp_{id_obra}.png"
    with open(temp_img, "wb") as f: f.write(graf_buf.read())
    c.drawImage(temp_img, 2*cm, height - 16*cm, width=17*cm, preserveAspectRatio=True)
    
    c.showPage()
    c.save()
    if os.path.exists(temp_img): os.remove(temp_img)
    pdf_buf.seek(0)
    return pdf_buf

# ======================================================
# PROCESSAMENTO DE MENSAGENS (BUSCA E IA)
# ======================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip().upper()
    user_id = update.effective_user.id
    lang = database.get_language(user_id)
    mode = database.get_storage_mode(user_id)

    # Busca flexível (Case Insensitive e Parcial)
    if mode == "SUPABASE" and engine:
        try:
            df = pd.read_sql(f"SELECT * FROM dashboard_obras WHERE UPPER(id_obra) LIKE '%%{user_input}%%'", engine)
        except:
            df = df_base[df_base["id_obra"].str.upper().str.contains(user_input, na=False)]
    else:
        df = df_base[df_base["id_obra"].str.upper().str.contains(user_input, na=False)]

    if df.empty:
        await update.message.reply_text(f"❌ ID `{user_input}` não localizado ({mode}).")
        return

    wait_msg = await update.message.reply_text("⏳ **Gerando Relatório de Engenharia...**", parse_mode=ParseMode.MARKDOWN)

    try:
        # IA
        X = df.reindex(columns=features_order, fill_value=0)
        risco = float(pipeline.predict(X).mean())
        status = "🔴 CRÍTICO" if risco > 10 else "🟡 ALERTA" if risco > 7 else "🟢 NORMAL"
        id_real = df.iloc[0]['id_obra']

        # Texto Detalhado
        relatorio = (
            f"🏗️ **RELATÓRIO CCBJJ**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 **Obra:** `{id_real}`\n"
            f"🔌 **Dados:** `{mode}`\n"
            f"🚦 **Status:** {status}\n"
            f"⏳ **Impacto:** `{risco:.2f} dias`\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        await update.message.reply_text(relatorio, parse_mode=ParseMode.MARKDOWN)

        # Gráfico e PDF
        graf_buf = gerar_grafico_ia(risco, id_real)
        await update.message.reply_photo(photo=graf_buf)
        
        pdf = gerar_pdf_final(id_real, risco, status, mode, graf_buf)
        await update.message.reply_document(document=InputFile(pdf, filename=f"CCBJJ_{id_real}.pdf"))
        
        await wait_msg.delete()
    except Exception as e:
        logging.error(e)
        await update.message.reply_text("⚠️ Erro no processamento.")

# ======================================================
# APP STARTUP
# ======================================================
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
