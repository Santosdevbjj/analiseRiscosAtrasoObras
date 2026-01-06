import os, sys, io, joblib, pandas as pd, pytz, logging
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib import colors
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import database
from i18n import TEXTS
from handlers import start_command, settings_command

# Configurações
BASE_DIR = Path(__file__).resolve().parent.parent
LOGO_PATH = BASE_DIR / "assets" / "logo_ccbjj.png"
PIPELINE_PATH = BASE_DIR / "models" / "pipeline_random_forest.pkl"
FEATURES_PATH = BASE_DIR / "models" / "features_metadata.joblib"
DB_PATH = BASE_DIR / "data" / "processed" / "df_mestre_consolidado.csv.gz"
BR_TIMEZONE = pytz.timezone('America/Sao_Paulo')

# Carregamento
pipeline = joblib.load(PIPELINE_PATH)
features_order = joblib.load(FEATURES_PATH)
df_base = pd.read_csv(DB_PATH, compression="gzip")
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL.replace("postgres://", "postgresql://")) if DATABASE_URL else None

def obter_menu_infra():
    keyboard = [[
        InlineKeyboardButton("📂 Modo CSV Local", callback_data='set_CSV'),
        InlineKeyboardButton("☁️ Modo Supabase Cloud", callback_data='set_DB')
    ]]
    return InlineKeyboardMarkup(keyboard)

def gerar_grafico_ia(risco_valor, id_obra):
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(10, 5))
    cor = 'green' if risco_valor <= 7 else 'orange' if risco_valor <= 10 else 'red'
    ax.barh(['Impacto Previsto'], [risco_valor], color=cor, height=0.5)
    ax.set_xlim(0, 15)
    ax.set_title(f'Análise de Risco Preditivo: {id_obra}', fontsize=12, fontweight='bold')
    
    # [span_0](start_span)LEGENDA EXPLICATIVA NO GRÁFICO[span_0](end_span)
    legenda = "Legenda de Risco:\n🟢 0-7: Normal\n🟡 7-10: Alerta\n🔴 >10: Crítico"
    plt.figtext(0.8, 0.15, legenda, fontsize=9, bbox=dict(facecolor='white', alpha=0.5))
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    return buf

def gerar_pdf_completo(id_obra, risco, status, modo, graf_buf):
    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=A4)
    width, height = A4
    
    # --- CAPA ---
    if LOGO_PATH.exists():
        c.drawImage(str(LOGO_PATH), width/2 - 2*cm, height - 5*cm, width=4*cm, preserveAspectRatio=True)
    
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(width/2, height - 8*cm, "CCBJJ ENGENHARIA")
    c.setFont("Helvetica", 16)
    c.drawCentredString(width/2, height - 9.5*cm, "RELATÓRIO TÉCNICO DE INTELIGÊNCIA PREDITIVA")
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(width/2, height - 10.5*cm, f"Gerado em: {datetime.now(BR_TIMEZONE).strftime('%d/%m/%Y %H:%M')}")
    c.line(2*cm, height - 11.5*cm, width - 2*cm, height - 11.5*cm)

    # --- TEXTO EXPLICATIVO DETALHADO ---
    text = c.beginText(2*cm, height - 13*cm)
    text.setFont("Helvetica-Bold", 12)
    text.textLine("1. SUMÁRIO EXECUTIVO")
    text.setFont("Helvetica", 11)
    text.textLine(f"Este documento apresenta a análise de risco para a unidade {id_obra}.")
    text.textLine(f"Utilizando a base de dados {modo}, nosso modelo de Machine Learning (Random Forest)")
    text.textLine(f"processou variáveis de cronograma para prever possíveis desvios.")
    text.moveCursor(0, 15)
    text.setFont("Helvetica-Bold", 12)
    text.textLine("2. DIAGNÓSTICO TÉCNICO")
    text.setFont("Helvetica", 11)
    text.textLine(f"• Impacto Projetado: {risco:.2f} dias de atraso.")
    text.textLine(f"• Status de Severidade: {status}")
    text.textLine("• Recomendação: Manter monitoramento contínuo dos marcos críticos.")
    c.drawText(text)

    # --- GRÁFICO COM LEGENDA ---
    graf_buf.seek(0)
    temp_img = f"tmp_{id_obra}.png"
    with open(temp_img, "wb") as f: f.write(graf_buf.read())
    c.drawImage(temp_img, 2*cm, 3*cm, width=17*cm, preserveAspectRatio=True)
    
    c.showPage()
    c.save()
    if os.path.exists(temp_img): os.remove(temp_img)
    pdf_buf.seek(0)
    return pdf_buf

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_obra = update.message.text.strip().upper()
    user_id = update.effective_user.id
    lang = database.get_language(user_id)
    modo = database.get_storage_mode(user_id)

    # Busca Insensível a maiúsculas/minúsculas
    if modo == "SUPABASE" and engine:
        try:
            df = pd.read_sql(f"SELECT * FROM dashboard_obras WHERE UPPER(id_obra) = '{id_obra}'", engine)
        except: df = df_base[df_base["id_obra"].str.upper() == id_obra]
    else:
        df = df_base[df_base["id_obra"].str.upper() == id_obra]

    if df.empty:
        await update.message.reply_text(f"❌ Obra `{id_obra}` não encontrada no modo {modo}.")
        return

    # [span_1](start_span)RELATÓRIO DE TEXTO DETALHADO[span_1](end_span)
    X = df.reindex(columns=features_order, fill_value=0)
    risco = float(pipeline.predict(X).mean())
    status = "🟢 NORMAL" if risco <= 7 else "🟡 ALERTA" if risco <= 10 else "🔴 CRÍTICO"
    
    relatorio = (
        f"🏗️ **RELATÓRIO TÉCNICO CCBJJ**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 **Unidade:** `{id_obra}`\n"
        f"🔌 **Fonte de Inteligência:** `{modo}`\n"
        f"🚦 **Classificação de Risco:** {status}\n"
        f"⏳ **Impacto Preditivo:** `{risco:.2f} dias` de desvio\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔍 **Análise Detalhada:**\n"
        f"Com base no comportamento histórico desta unidade e nos parâmetros de produtividade atuais, "
        f"nosso modelo Random Forest estima um impacto de cronograma dentro da zona {status.split()[-1]}.\n\n"
        f"_Gerando gráficos e PDF oficial..._"
    )
    await update.message.reply_text(relatorio, parse_mode=ParseMode.MARKDOWN)

    graf = gerar_grafico_ia(risco, id_obra)
    await update.message.reply_photo(photo=graf, caption="📊 Análise de Dispersão de Risco com Legenda Técnica.")
    
    pdf = gerar_pdf_completo(id_obra, risco, status, modo, graf)
    await update.message.reply_document(document=InputFile(pdf, filename=f"Relatorio_{id_obra}.pdf"))

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split("_")[1]
    database.set_language(query.from_user.id, lang)
    # FORÇA O MENU DE MODO A APARECER APÓS O IDIOMA
    await query.edit_message_text(
        text=f"{TEXTS[lang]['language_changed']}\n\n{TEXTS[lang]['infra_select']}",
        reply_markup=obter_menu_infra(),
        parse_mode=ParseMode.MARKDOWN
    )

async def config_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    modo = "CSV" if query.data == 'set_CSV' else "SUPABASE"
    database.set_storage_mode(query.from_user.id, modo)
    await query.edit_message_text(f"✅ Configuração Finalizada!\nIdiomas e Infraestrutura (`{modo}`) prontos para análise.")

# Inicialização do App (FastAPI + PTB) ... [Código de inicialização padrão]
