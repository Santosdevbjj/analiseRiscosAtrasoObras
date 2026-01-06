import os 
import sys
import logging
import warnings
import joblib
import pandas as pd
import pytz
import io
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine

# Garantir que o Python encontre os módulos locais
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
from handlers import (
    start_command, help_command, about_command, 
    status_command, language_callback, resolve_language,
    language_manual_command, healthcheck_command
)

# Configuração Global de Fuso Horário
BR_TIMEZONE = pytz.timezone('America/Sao_Paulo')

logging.basicConfig(level=logging.INFO)
warnings.filterwarnings("ignore")

# CONFIGURAÇÕES DE CAMINHOS
BASE_DIR = Path(__file__).resolve().parent.parent
LOGO_PATH = BASE_DIR / "assets" / "logo_ccbjj.png"
PIPELINE_PATH = BASE_DIR / "models" / "pipeline_random_forest.pkl"
FEATURES_PATH = BASE_DIR / "models" / "features_metadata.joblib"
DB_PATH = BASE_DIR / "data" / "processed" / "df_mestre_consolidado.csv.gz"

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
DATABASE_URL = os.getenv("DATABASE_URL")

# Inicialização de Recursos
pipeline = joblib.load(PIPELINE_PATH)
features_order = joblib.load(FEATURES_PATH)
engine = create_engine(DATABASE_URL.replace("postgres://", "postgresql://")) if DATABASE_URL else None
df_base = pd.read_csv(DB_PATH, compression="gzip")

# ======================================================
# GERAÇÃO DE RELATÓRIOS MELHORADA
# ======================================================

def gerar_grafico_ia(risco_valor, id_obra):
    """Gera gráfico com legenda explicativa integrada."""
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(10, 5))
    
    cor = 'green' if risco_valor <= 7 else 'orange' if risco_valor <= 10 else 'red'
    ax.barh(['Impacto Previsto'], [risco_valor], color=cor, height=0.5)
    
    ax.set_xlim(0, max(15, risco_valor + 3))
    ax.set_title(f'Análise de Dispersão de Risco - {id_obra}', fontsize=14, fontweight='bold')
    ax.set_xlabel('Dias de Atraso (Projeção IA)')
    
    # Legenda explicativa dentro da imagem
    legenda_texto = (
        "Legenda:\n"
        "🟢 0-7 dias: Baixo Risco\n"
        "🟡 8-10 dias: Médio Risco (Alerta)\n"
        "🔴 >10 dias: Risco Crítico"
    )
    plt.figtext(0.15, -0.05, legenda_texto, fontsize=10, bbox=dict(facecolor='white', alpha=0.5))

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=120)
    buf.seek(0)
    plt.close(fig)
    return buf

def gerar_pdf_corporativo(id_obra, risco, status, modo, graf_buf):
    """Gera PDF com Capa, Logo, Texto Detalhado e Gráfico."""
    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=A4)
    width, height = A4
    now_br = datetime.now(BR_TIMEZONE).strftime('%d/%m/%Y %H:%M:%S')

    # --- 1. CAPA ---
    if LOGO_PATH.exists():
        c.drawImage(str(LOGO_PATH), width/2 - 2.5*cm, height - 5*cm, width=5*cm, preserveAspectRatio=True)
    
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width/2, height - 8*cm, "CCBJJ ENGENHARIA")
    c.setFont("Helvetica", 16)
    c.drawCentredString(width/2, height - 9*cm, "Relatório Preditivo de Inteligência de Risco")
    
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(width/2, height - 10*cm, f"Emitido em: {now_br} (Horário de Brasília)")
    
    c.setStrokeColor(colors.black)
    c.line(2*cm, height - 11*cm, width - 2*cm, height - 11*cm)

    # --- 2. RELATÓRIO TEXTUAL DETALHADO ---
    text = c.beginText(2*cm, height - 12.5*cm)
    text.setFont("Helvetica-Bold", 14)
    text.textLine("1. RESUMO EXECUTIVO DA ANÁLISE")
    text.setFont("Helvetica", 12)
    text.moveCursor(0, 10)
    text.textLine(f"• Identificador da Unidade: {id_obra}")
    text.textLine(f"• Origem dos Dados: Sistema {modo}")
    text.textLine(f"• Classificação de Risco: {status}")
    text.textLine(f"• Impacto Estimado em Cronograma: {risco:.2f} dias")
    
    text.moveCursor(0, 15)
    text.setFont("Helvetica-Bold", 12)
    text.textLine("2. METODOLOGIA APLICADA")
    text.setFont("Helvetica", 11)
    text.textLine("Esta análise utiliza o algoritmo Random Forest Regressor treinado com dados")
    text.textLine("históricos de logística, clima e produtividade da CCBJJ Engenharia.")
    c.drawText(text)

    # --- 3. GRÁFICO COM LEGENDA ---
    graf_buf.seek(0)
    temp_img = f"pdf_tmp_{id_obra}.png"
    with open(temp_img, "wb") as f:
        f.write(graf_buf.read())
    
    c.drawImage(temp_img, 2*cm, 4*cm, width=17*cm, preserveAspectRatio=True)
    
    # Rodapé
    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(width/2, 1.5*cm, "CCBJJ Engenharia & Inteligência de Risco - Uso Confidencial")

    c.showPage()
    c.save()
    if os.path.exists(temp_img): os.remove(temp_img)
    pdf_buf.seek(0)
    return pdf_buf

# ======================================================
# FUNÇÕES DE APOIO
# ======================================================

def obter_menu_infra():
    keyboard = [[
        InlineKeyboardButton("📂 Modo CSV Local", callback_data='set_CSV'),
        InlineKeyboardButton("☁️ Modo Supabase Cloud", callback_data='set_DB'),
    ]]
    return InlineKeyboardMarkup(keyboard)

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = resolve_language(update)
    await update.message.reply_text(TEXTS[lang]["infra_select"], reply_markup=obter_menu_infra())

async def config_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mode = "CSV" if query.data == 'set_CSV' else "SUPABASE"
    database.set_storage_mode(query.from_user.id, mode)
    lang = resolve_language(update)
    await query.edit_message_text(text=f"✅ Infraestrutura configurada: **{mode}**", parse_mode=ParseMode.MARKDOWN)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_obra = update.message.text.strip().upper()
    user_id = update.effective_user.id
    lang = database.get_language(user_id)
    modo_pref = database.get_storage_mode(user_id)

    # Busca de dados
    if modo_pref == "SUPABASE" and engine:
        try:
            df = pd.read_sql(f"SELECT * FROM dashboard_obras WHERE id_obra = '{id_obra}'", engine)
            modo_real = "SUPABASE"
        except:
            df = df_base[df_base["id_obra"] == id_obra]
            modo_real = "CSV (Fallback)"
    else:
        df = df_base[df_base["id_obra"] == id_obra]
        modo_real = "CSV"

    if df.empty:
        await update.message.reply_text(f"❌ Obra `{id_obra}` não encontrada no modo {modo_real}.")
        return

    wait = await update.message.reply_text("🤖 **Iniciando Processamento de IA CCBJJ...**")

    try:
        # Predição
        X = df.reindex(columns=features_order, fill_value=0)
        risco = float(pipeline.predict(X).mean())
        status = "🔴 CRÍTICO" if risco > 10 else "🟡 ALERTA" if risco > 7 else "🟢 NORMAL"
        
        # 1. Relatório Texto Detalhado
        relatorio_texto = (
            f"🏗️ **RELATÓRIO DE ANÁLISE PREDITIVA**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 **ID da Obra:** `{id_obra}`\n"
            f"📡 **Fonte de Dados:** `{modo_real}`\n"
            f"📅 **Data/Hora:** `{datetime.now(BR_TIMEZONE).strftime('%d/%m/%Y %H:%M')}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🧠 **Diagnóstico da IA:**\n"
            f"O modelo Random Forest detectou uma tendência de desvio no cronograma original. "
            f"Com base nas variáveis de infraestrutura e histórico, o impacto projetado é de:\n\n"
            f"⏳ **Atraso Estimado:** `{risco:.2f} dias`\n"
            f"🚦 **Classificação de Risco:** {status}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"_Aguarde o gráfico e o documento PDF oficial..._"
        )
        await update.message.reply_text(relatorio_texto, parse_mode=ParseMode.MARKDOWN)

        # 2. Gráfico
        graf_buf = gerar_grafico_ia(risco, id_obra)
        await update.message.reply_photo(photo=graf_buf, caption="📊 **Visualização Técnica de Dispersão de Risco**", parse_mode=ParseMode.MARKDOWN)

        # 3. PDF
        pdf_buf = gerar_pdf_corporativo(id_obra, risco, status, modo_real, graf_buf)
        await update.message.reply_document(
            document=InputFile(pdf_buf, filename=f"CCBJJ_Relatorio_{id_obra}.pdf"),
            caption="📄 **Relatório Oficial de Engenharia (PDF)**"
        )
        await wait.delete()

    except Exception as e:
        logging.error(f"Erro: {e}")
        await update.message.reply_text("⚠️ Ocorreu um erro ao gerar o relatório detalhado.")

# ======================================================
# EXECUÇÃO FASTAPI
# ======================================================
app = FastAPI()
ptb_app = None

@app.on_event("startup")
async def startup():
    global ptb_app
    ptb_app = ApplicationBuilder().token(TOKEN).build()
    ptb_app.add_handler(CommandHandler("start", start_command))
    ptb_app.add_handler(CommandHandler("settings", settings_command))
    ptb_app.add_handler(CallbackQueryHandler(config_callback, pattern='^set_'))
    ptb_app.add_handler(CallbackQueryHandler(language_callback, pattern='^lang_'))
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
