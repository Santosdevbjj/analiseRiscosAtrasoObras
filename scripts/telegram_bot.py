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

# Adiciona o diretório scripts ao PATH para evitar erros de importação no servidor
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

# Servidor e API
from fastapi import FastAPI, Request, Response
import uvicorn

# Telegram
from telegram import Update, InputFile
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Relatórios PDF (ReportLab)
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

# Configurações de Gráficos
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore", category=UserWarning)

# ======================================================
# CONFIGURAÇÕES DE CAMINHOS E FUSO
# ======================================================
BASE_DIR = Path(__file__).resolve().parent.parent
PIPELINE_PATH = BASE_DIR / "models/pipeline_random_forest.pkl"
FEATURES_PATH = BASE_DIR / "models/features_metadata.joblib"
DB_PATH = BASE_DIR / "data/processed/df_mestre_consolidado.csv.gz"
LOGO_PATH = BASE_DIR / "assets/logo_ccbjj.png"
HISTORY_PATH = BASE_DIR / "data/history/analises_history.csv"

# Garantir diretórios
HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
BR_TIMEZONE = pytz.timezone('America/Sao_Paulo')

# Carregamento e Normalização da Base de Dados
pipeline = joblib.load(PIPELINE_PATH)
features_order = joblib.load(FEATURES_PATH)

df_base = pd.read_csv(DB_PATH, compression="gzip")
if "id_obra" in df_base.columns:
    df_base["id_obra"] = df_base["id_obra"].astype(str).str.strip().str.upper()

# ======================================================
# FUNÇÕES AUXILIARES E RELATÓRIOS
# ======================================================

def salvar_historico(user_id, id_obra, risco_medio, status, modo, lang):
    """Registra a consulta no histórico CSV."""
    data_hora = datetime.now(BR_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    file_exists = HISTORY_PATH.exists()
    with open(HISTORY_PATH, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "user_id", "id_obra", "risco_medio", "status", "modo", "lang"])
        writer.writerow([data_hora, user_id, id_obra, f"{risco_medio:.2f}", status, modo, lang])

def gerar_pdf_corporativo(id_obra, texto_md, grafico_buf, lang="pt", modo="Diretor"):
    """Gera PDF com Capa, Logo centralizada e Rodapé Interno."""
    if not REPORTLAB_AVAILABLE: return None
    
    pdf_buf = BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=A4)
    largura, altura = A4
    data_br = datetime.now(BR_TIMEZONE).strftime("%d/%m/%Y %H:%M")

    # --- PÁGINA 1: CAPA CORPORATIVA ---
    if LOGO_PATH.exists():
        c.drawImage(str(LOGO_PATH), (largura/2) - 3*cm, altura - 8*cm, width=6*cm, preserveAspectRatio=True)
    
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(largura/2, altura - 11*cm, "Relatório de Inteligência de Risco")
    
    c.setFont("Helvetica", 12)
    c.drawCentredString(largura/2, altura - 12*cm, "CCBJJ Engenharia & Inteligência")
    
    # Box de Informações
    c.setStrokeColor(colors.dodgerblue)
    c.roundRect(3*cm, 8*cm, largura - 6*cm, 3*cm, 10, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(3.5*cm, 10.3*cm, f"ID DA OBRA: {id_obra}")
    c.drawString(3.5*cm, 9.6*cm, f"DATA/HORA (BRT): {data_br}")
    c.drawString(3.5*cm, 8.9*cm, f"STATUS DO DOCUMENTO: OFICIAL")
    c.drawString(3.5*cm, 8.2*cm, "RESPONSÁVEL TÉCNICO: Sergio Luiz dos Santos")
    
    c.showPage()

    # --- PÁGINA 2: ANÁLISE DETALHADA ---
    if LOGO_PATH.exists():
        c.drawImage(str(LOGO_PATH), largura - 3.5*cm, 0.8*cm, width=2*cm, preserveAspectRatio=True)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(2*cm, 1*cm, f"CCBJJ Risk Intelligence - {id_obra} - Gerado em {data_br}")
    
    # Conteúdo (Remove marcações Markdown para o PDF)
    texto_limpo = texto_md.replace("**", "").replace("`", "").replace("•", "-")
    text_obj = c.beginText(2*cm, altura - 3*cm)
    text_obj.setFont("Helvetica", 10)
    text_obj.setLeading(14)
    for line in texto_limpo.split('\n'):
        text_obj.textLine(line)
    c.drawText(text_obj)

    img_path = f"temp_plot_{id_obra}.png"
    with open(img_path, "wb") as f:
        f.write(grafico_buf.getbuffer())
    c.drawImage(img_path, 2*cm, 3.5*cm, width=17*cm, preserveAspectRatio=True)
    
    c.showPage()
    c.save()
    if os.path.exists(img_path): os.remove(img_path)
    pdf_buf.seek(0)
    return pdf_buf

def preparar_X(df):
    X = df.copy()
    for col in features_order:
        if col not in X.columns: 
            X[col] = 0
    return X[features_order].fillna(0)

def gerar_grafico(df_obra, preds, id_obra):
    # Cores do Logo CCBJJ (Azul Corporativo)
    cor_azul_ccbjj = '#0066CC' 
    
    plt.figure(figsize=(8, 4.5))
    plt.bar(df_obra["etapa"], preds, color=cor_azul_ccbjj, edgecolor='#003366', linewidth=1)
    
    plt.title(f"Atraso Estimado por Etapa - {id_obra}", fontsize=12, fontweight='bold', color='#2c3e50')
    plt.ylabel("Dias de Atraso", fontsize=10)
    plt.grid(axis='y', linestyle='--', alpha=0.3)
    plt.xticks(rotation=20, fontsize=9)
    
    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=120)
    buf.seek(0)
    plt.close()
    return buf

# ======================================================
# HANDLER PRINCIPAL DE ANÁLISE
# ======================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_obra = update.message.text.strip().upper()
    lang = resolve_language(update)
    user_id = update.effective_user.id
    
    df_obra = df_base[df_base["id_obra"] == id_obra]
    
    if df_obra.empty:
        df_obra = df_base[df_base["id_obra"].str.contains(id_obra, na=False, regex=False)]

    if df_obra.empty:
        await update.message.reply_text(TEXTS[lang].get("not_found", "❌ ID da obra não localizado."))
        return

    try:
        # Processamento de IA
        X = preparar_X(df_obra)
        preds = pipeline.predict(X)
        risco_medio = preds.mean()
        
        # Identificação de Ponto Crítico e Insights
        idx_max = preds.argmax()
        etapa_critica = df_obra.iloc[idx_max]["etapa"]
        
        # Extração de dados da primeira linha para o cabeçalho
        cidade = df_obra.iloc[0].get("cidade", "N/A")
        solo = df_obra.iloc[0].get("solo", "N/A")
        chuva = df_obra.iloc[0].get("precipitacao", "0")
        
        status_ia = "🔴 Crítico" if risco_medio > 10 else "🟡 Alerta" if risco_medio > 7 else "🟢 Normal"
        
        # Lógica de Insight Simples
        insight = "Revisar logística e suprimentos."
        if "estrutura" in etapa_critica.lower(): insight = "Revisar logística de aço e formas."
        elif "fundação" in etapa_critica.lower(): insight = "Verificar drenagem e condições do solo."
        elif "acabamento" in etapa_critica.lower(): insight = "Acelerar contratação de mão de obra especializada."

        # Gerar Texto Completo (Inspirado no modelo antigo)
        texto_resp = (
            f"🏗️ **CCBJJ Engenharia & Inteligência de Risco**\n"
            f"----------------------------------\n"
            f"📍 **Obra:** `{id_obra}`\n"
            f"🏙️ **Cidade:** `{cidade}`\n"
            f"⛰️ **Solo:** `{solo}`\n"
            f"🌧️ **Chuva:** `{chuva} mm`\n"
            f"----------------------------------\n"
            f"📊 **Diagnóstico da IA**\n"
            f"• Risco médio: `{risco_medio:.1f} dias`\n"
            f"• Status: {status_ia}\n\n"
            f"⚠️ **Ponto Crítico**\n"
            f"Etapa: `{etapa_critica}`\n"
            f"----------------------------------\n"
            f"💡 **Insight:** {insight}\n\n"
            f"_Desenvolvido por Sergio Luiz dos Santos_"
        )
        
        # Registrar Histórico
        salvar_historico(user_id, id_obra, risco_medio, status_ia, "Automático", lang)
        
        # Gerar Gráfico
        graf_buf = gerar_grafico(df_obra, preds, id_obra)
        
        # 1) Enviar Texto
        await update.message.reply_text(texto_resp, parse_mode=ParseMode.MARKDOWN)
        
        # 2) Enviar Gráfico
        graf_buf.seek(0)
        await update.message.reply_photo(photo=graf_buf, caption="📈 Análise de Tendência de Atrasos")
        
        # 3) Enviar PDF
        if REPORTLAB_AVAILABLE:
            graf_buf.seek(0)
            pdf_file = gerar_pdf_corporativo(id_obra, texto_resp, graf_buf, lang=lang)
            await update.message.reply_document(
                document=InputFile(pdf_file, filename=f"Relatorio_{id_obra}.pdf"),
                caption="📄 Relatório Executivo Completo"
            )
            
    except Exception as e:
        logging.error(f"Erro no processamento: {e}")
        await update.message.reply_text("⚠️ Erro técnico ao processar os dados da obra.")

# ======================================================
# APLICAÇÃO FASTAPI + BOT
# ======================================================
app = FastAPI()
ptb_app = None

@app.on_event("startup")
async def startup():
    global ptb_app
    ptb_app = ApplicationBuilder().token(TOKEN).build()
    
    ptb_app.add_handler(CommandHandler("start", start_command))
    ptb_app.add_handler(CommandHandler("help", help_command))
    ptb_app.add_handler(CommandHandler("about", about_command))
    ptb_app.add_handler(CommandHandler("status", status_command))
    ptb_app.add_handler(CommandHandler("language", language_manual_command))
    ptb_app.add_handler(CommandHandler("example", example_command))
    ptb_app.add_handler(CommandHandler("healthcheck", healthcheck_command))
    ptb_app.add_handler(CallbackQueryHandler(language_callback))
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

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
