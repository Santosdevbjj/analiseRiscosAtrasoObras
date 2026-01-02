"""
scripts/telegram_bot.py — Bot de Inteligência Preditiva CCbjj 2.0
Foco: Decisão de Diretoria, Logística e Engenharia de Campo
"""

import os
import logging
import warnings
from io import BytesIO
import pandas as pd
import joblib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Ignorar avisos de nomes de features para manter o log limpo
warnings.filterwarnings("ignore", category=UserWarning)

# -----------------------------
# Configurações de Caminhos (Ajustados para o seu ecossistema)
# -----------------------------
PIPELINE_PATH = "models/pipeline_random_forest.pkl"
FEATURES_PATH = "models/features_metadata.joblib"
DB_PATH = "data/processed/df_mestre_consolidado.csv.gz" # Ajustado para o arquivo compactado
REPORTS_PATH = "data/reports"
os.makedirs(REPORTS_PATH, exist_ok=True)

# -----------------------------
# Logging Profissional
# -----------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("telegram_bot_ccbjj")

# -----------------------------
# Carregamento de Recursos (Com validação de ordem de colunas)
# -----------------------------
try:
    pipeline = joblib.load(PIPELINE_PATH)
    features_order = joblib.load(FEATURES_PATH) # Essencial para não quebrar a predição
    logger.info("✅ Pipeline e Metadados carregados com sucesso.")
except Exception as e:
    logger.error(f"❌ Erro crítico ao carregar ativos: {e}")
    pipeline, features_order = None, None

try:
    # Leitura com descompressão automática para economizar memória
    df_base = pd.read_csv(DB_PATH, compression='gzip')
    logger.info("✅ Base de dados consolidada integrada via Gzip.")
except Exception as e:
    logger.error(f"❌ Erro ao carregar base CSV.GZ: {e}")
    df_base = None

# -----------------------------
# Utilitários de Negócio
# -----------------------------
def emoji_risco(dias: float) -> str:
    if dias > 10: return "🔴 (Crítico)"
    if dias > 7: return "🟡 (Alerta)"
    return "🟢 (Normal)"

def formatar_texto_pdf(texto_markdown: str) -> str:
    """Remove caracteres especiais que quebram o PDF padrão."""
    chars = ["*", "`", "🏗️", "📍", "⛰️", "🌧️", "💰", "📊", "⚠️", "💡"]
    for char in chars:
        texto_markdown = texto_markdown.replace(char, "")
    return texto_markdown

def preparar_dados_predicao(df_obra: pd.DataFrame):
    """Garante que o DF tenha as colunas certas na ordem certa."""
    X = df_obra.copy()
    # Remove colunas que não são features do modelo
    if "id_obra" in X.columns: X = X.drop(columns=["id_obra"])
    if "risco_etapa" in X.columns: X = X.drop(columns=["risco_etapa"])
    
    # Reordena as colunas conforme o treinamento (Contrato da IA)
    return X[features_order]

def gerar_relatorio_inteligente(id_obra: str, df_obra: pd.DataFrame) -> str:
    X = preparar_dados_predicao(df_obra)
    predicoes = pipeline.predict(X)
    
    df_res = df_obra.copy()
    df_res["predicao_atraso"] = predicoes

    risco_medio = float(df_res["predicao_atraso"].mean())
    pior_linha = df_res.loc[df_res["predicao_atraso"].idxmax()]

    relatorio = (
        f"🏗️ *CCBJJ RISK INTELLIGENCE*\n"
        f"-------------------------------------------\n"
        f"📍 *Obra:* {id_obra} | {str(df_res['cidade'].iloc[0]).title()}\n"
        f"⛰️ *Geologia:* {str(df_res['tipo_solo'].iloc[0]).title()}\n"
        f"🌧️ *Clima:* {float(df_res['nivel_chuva'].iloc[0]):.0f}mm (Histórico)\n"
        f"💰 *Exposure:* R$ {float(df_res['orcamento_estimado'].iloc[0]):,.2f}\n"
        f"-------------------------------------------\n"
        f"📊 *DIAGNÓSTICO DA IA*\n"
        f"• Risco Médio: `{risco_medio:.1f} dias`\n"
        f"• Status: {emoji_risco(risco_medio)}\n\n"
        f"⚠️ *PONTO DE ATENÇÃO*\n"
        f"A etapa de *{pior_linha['etapa'].title()}* é a mais sensível, com atraso estimado de `{pior_linha['predicao_atraso']:.1f} dias` usando material: {pior_linha['material']}.\n"
        f"-------------------------------------------\n"
        f"💡 *INSIGHT:* Revisar logística de {pior_linha['material']} e rating do fornecedor atual."
    )
    return relatorio

def gerar_grafico_etapas(id_obra: str, df_obra: pd.DataFrame) -> BytesIO:
    X = preparar_dados_predicao(df_obra)
    df_res = df_obra.copy()
    df_res["predicao_atraso"] = pipeline.predict(X)

    etapas_prev = df_res.groupby("etapa")["predicao_atraso"].mean().sort_values()

    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(8, 5))
    
    # Cores CCbjj (Verde e Vermelho para Risco)
    colors = ['#2E7D32' if x < 7 else '#C62828' for x in etapas_prev]
    bars = ax.bar([e.title() for e in etapas_prev.index], etapas_prev.values, color=colors)
    
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, yval + 0.1, f'{yval:.1f}d', ha='center', va='bottom', fontweight='bold')

    ax.set_title(f"Predição de Atrasos por Etapa - {id_obra}", fontsize=12, fontweight='bold')
    ax.set_ylabel("Dias de Atraso")
    
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=100)
    buf.seek(0)
    plt.close()
    return buf

def gerar_pdf_relatorio(id_obra: str, df_obra: pd.DataFrame) -> str:
    pdf_path = os.path.join(REPORTS_PATH, f"Relatorio_CCbjj_{id_obra}.pdf")
    texto_puro = formatar_texto_pdf(gerar_relatorio_inteligente(id_obra, df_obra))

    with PdfPages(pdf_path) as pdf:
        fig, ax = plt.subplots(figsize=(8.5, 11))
        ax.axis("off")
        ax.text(0.1, 0.95, "CCBJJ ENGENHARIA - RELATÓRIO TÉCNICO", fontsize=14, fontweight='bold', color='#1B5E20')
        ax.text(0.1, 0.90, "-"*60)
        ax.text(0.1, 0.85, texto_puro, va="top", family='sans-serif', fontsize=11, linespacing=1.8)
        pdf.savefig(fig)
        plt.close(fig)
    return pdf_path

# -----------------------------
# Bot Engine
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *CCbjj Risk Intelligence Bot*\n\n"
        "Envie o código da obra (ex: `CCbjj-100`) para receber o diagnóstico de risco via IA.",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_obra = update.message.text.strip() # Mantém o case original para bater com o CSV
    
    if df_base is None or pipeline is None:
        await update.message.reply_text("⚠️ Ativos do modelo não carregados.")
        return

    df_obra = df_base[df_base["id_obra"] == id_obra]
    
    if df_obra.empty:
        await update.message.reply_text(f"❌ Obra `{id_obra}` não encontrada.")
        return

    status_msg = await update.message.reply_text("🧠 Processando predições...")

    try:
        # 1. Texto
        await update.message.reply_text(gerar_relatorio_inteligente(id_obra, df_obra), parse_mode=ParseMode.MARKDOWN)
        # 2. Gráfico
        await update.message.reply_photo(photo=gerar_grafico_etapas(id_obra, df_obra))
        # 3. PDF
        pdf = gerar_pdf_relatorio(id_obra, df_obra)
        with open(pdf, "rb") as f:
            await update.message.reply_document(document=f, filename=f"Risco_{id_obra}.pdf")
        
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Erro: {e}")
        await update.message.reply_text("🚨 Erro ao gerar diagnóstico.")

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        print("❌ TELEGRAM_TOKEN não configurado!")
        return
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    logger.info("🚀 Bot CCbjj Online!")
    app.run_polling()

if __name__ == "__main__":
    main()
