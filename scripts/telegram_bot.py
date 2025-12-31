"""
scripts/telegram_bot.py — Bot de Inteligência Preditiva MRV 2.0
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
# Configurações
# -----------------------------
PIPELINE_PATH = "models/pipeline_random_forest.pkl"
DB_PATH = "data/raw/base_consulta_bot.csv"
REPORTS_PATH = "data/reports"
os.makedirs(REPORTS_PATH, exist_ok=True)

# -----------------------------
# Logging Profissional
# -----------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("telegram_bot_mrv")

# -----------------------------
# Carregamento de Recursos
# -----------------------------
try:
    pipeline = joblib.load(PIPELINE_PATH)
    logger.info("✅ Pipeline RandomForest carregado com sucesso.")
except Exception as e:
    logger.error(f"❌ Erro crítico ao carregar pipeline: {e}")
    pipeline = None

try:
    df_base = pd.read_csv(DB_PATH)
    logger.info("✅ Base de dados de consulta integrada carregada.")
except Exception as e:
    logger.error(f"❌ Erro ao carregar base CSV: {e}")
    df_base = None

# -----------------------------
# Utilitários de Negócio
# -----------------------------
def emoji_risco(dias: float) -> str:
    if dias > 10: return "🔴 (Crítico)"
    if dias > 5: return "🟡 (Alerta)"
    return "🟢 (Normal)"

def formatar_texto_pdf(texto_markdown: str) -> str:
    """Remove caracteres especiais que quebram o PDF padrão."""
    return texto_markdown.replace("*", "").replace("`", "").replace("🏗️", "").replace("📍", "").replace("⛰️", "").replace("🌧️", "").replace("💰", "").replace("📊", "").replace("⚠️", "").replace("💡", "")

def gerar_relatorio_inteligente(id_obra: str, df_obra: pd.DataFrame) -> str:
    """Gera a narrativa técnica para o usuário."""
    # Garantir que usamos apenas as colunas que o modelo conhece
    X = df_obra.drop(columns=["id_obra"], errors="ignore")
    
    # Previsão
    predicoes = pipeline.predict(X)
    df_res = df_obra.copy()
    df_res["predicao_atraso"] = predicoes

    risco_medio = float(df_res["predicao_atraso"].mean())
    pior_linha = df_res.loc[df_res["predicao_atraso"].idxmax()]

    # Contexto de Negócio
    cidade = str(df_res["cidade"].iloc[0])
    solo = str(df_res["tipo_solo"].iloc[0])
    chuva = float(df_res["nivel_chuva"].iloc[0])
    orcamento = float(df_res["orcamento_estimado"].iloc[0])
    
    status = emoji_risco(risco_medio)

    relatorio = (
        f"🏗️ *RISK INTELLIGENCE MRV*\n"
        f"-------------------------------------------\n"
        f"📍 *Obra:* {id_obra} | {cidade}\n"
        f"⛰️ *Geologia:* {solo}\n"
        f"🌧️ *Clima:* {chuva:.0f}mm acumulado\n"
        f"💰 *Exposure:* R$ {orcamento:,.2f}\n"
        f"-------------------------------------------\n"
        f"📊 *DIAGNÓSTICO DA IA*\n"
        f"• Risco Médio: `{risco_medio:.1f} dias`\n"
        f"• Status: {status}\n\n"
        f"⚠️ *GARGALO OPERACIONAL*\n"
        f"A etapa de *{pior_linha['etapa']}* é a mais sensível no momento, com atraso estimado de `{pior_linha['predicao_atraso']:.1f} dias` devido ao material: {pior_linha['material']}.\n"
        f"-------------------------------------------\n"
        f"💡 *PLANO DE AÇÃO:* Intensificar drenagem e revisar rating do fornecedor de {pior_linha['material']}."
    )
    return relatorio

def gerar_grafico_etapas(id_obra: str, df_obra: pd.DataFrame) -> BytesIO:
    """Gera gráfico com identidade visual MRV."""
    X = df_obra.drop(columns=["id_obra"], errors="ignore")
    df_res = df_obra.copy()
    df_res["predicao_atraso"] = pipeline.predict(X)

    etapas_prev = df_res.groupby("etapa")["predicao_atraso"].mean().sort_values()

    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(8, 5))
    
    # Cores MRV (Verde e Azul)
    colors = ['#00A859' if x < 7 else '#EE3124' for x in etapas_prev]
    bars = ax.bar(etapas_prev.index, etapas_prev.values, color=colors, edgecolor='white')
    
    # Adicionar rótulos nas barras
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, yval + 0.2, f'{yval:.1f}d', ha='center', va='bottom', fontweight='bold')

    ax.set_title(f"Predição de Atrasos por Etapa - {id_obra}", fontsize=14, fontweight='bold', pad=20)
    ax.set_ylabel("Dias Previstos", fontsize=12)
    ax.set_ylim(0, max(etapas_prev.values) + 3)
    
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=120)
    buf.seek(0)
    plt.close()
    return buf

def gerar_pdf_relatorio(id_obra: str, df_obra: pd.DataFrame) -> str:
    """Gera PDF técnico para arquivamento ou envio por e-mail."""
    pdf_path = os.path.join(REPORTS_PATH, f"Analise_Risco_{id_obra}.pdf")
    
    # Prepara o texto limpo para o PDF
    texto_puro = formatar_texto_pdf(gerar_relatorio_inteligente(id_obra, df_obra))

    with PdfPages(pdf_path) as pdf:
        # Página 1: Sumário Executivo
        fig, ax = plt.subplots(figsize=(8.5, 11))
        ax.axis("off")
        ax.text(0.1, 0.9, f"RELATÓRIO TÉCNICO DE RISCO - MRV\nGerado automaticamente via IA", fontsize=16, fontweight='bold', color='#004A2F')
        ax.text(0.1, 0.85, "-"*50, fontsize=12)
        ax.text(0.1, 0.8, texto_puro, va="top", fontsize=12, linespacing=1.8)
        pdf.savefig(fig)
        plt.close(fig)

        # Página 2: Visualização de Dados
        buf = gerar_grafico_etapas(id_obra, df_obra)
        img = plt.imread(buf)
        fig2, ax2 = plt.subplots(figsize=(10, 7))
        ax2.imshow(img)
        ax2.axis("off")
        pdf.savefig(fig2)
        plt.close(fig2)

    return pdf_path

# -----------------------------
# Bot Engine
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Olá {user.first_name}! 👋\n\n"
        "Bem-vindo ao *MRV Risk Intelligence Bot*.\n"
        "Eu utilizo modelos de Machine Learning para prever gargalos logísticos e geológicos nas nossas obras.\n\n"
        "👉 *Para começar:* Envie o código da obra (ex: `MRV-100`)",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_usuario = update.message.text.upper().strip()
    
    if df_base is None or pipeline is None:
        await update.message.reply_text("⚠️ Erro de inicialização: Verifique os arquivos do modelo e dados.")
        return

    # Filtra a obra na base
    df_obra = df_base[df_base["id_obra"] == id_usuario]
    
    if df_obra.empty:
        await update.message.reply_text(f"❌ A obra `{id_usuario}` não foi encontrada na base de monitoramento atual.")
        return

    msg_espera = await update.message.reply_text(f"🔄 Consultando modelo preditivo para `{id_usuario}`...")

    try:
        # 1. Enviar Relatório de Texto
        relatorio = gerar_relatorio_inteligente(id_usuario, df_obra)
        await update.message.reply_text(relatorio, parse_mode=ParseMode.MARKDOWN)

        # 2. Enviar Gráfico Comparativo
        grafico = gerar_grafico_etapas(id_usuario, df_obra)
        await update.message.reply_photo(photo=grafico, caption=f"Análise de Sensibilidade - {id_usuario}")

        # 3. Enviar PDF Oficial
        pdf_path = gerar_pdf_relatorio(id_usuario, df_obra)
        with open(pdf_path, "rb") as f:
            await update.message.reply_document(
                document=f, 
                filename=os.path.basename(pdf_path),
                caption="📄 Relatório técnico detalhado para compartilhamento."
            )
        
        await msg_espera.delete()

    except Exception as e:
        logger.error(f"Erro no processamento: {e}")
        await update.message.reply_text("🚨 Ocorreu um erro interno ao processar a predição da IA.")

# -----------------------------
# Main Execution
# -----------------------------
def main():
    token = os.getenv("TELEGRAM_TOKEN")
    
    if not token:
        logger.error("❌ Variável de ambiente TELEGRAM_TOKEN não encontrada!")
        return

    # Build do Bot
    app = ApplicationBuilder().token(token).build()
    
    # Adicionar Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    logger.info("🚀 MRV Risk Intelligence Bot is LIVE!")
    app.run_polling()

if __name__ == "__main__":
    main()
