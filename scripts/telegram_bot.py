"""
scripts/telegram_bot.py — Bot de Inteligência Preditiva MRV
Versão Final Consolidada: Data Science + Business Intelligence + Visualizações + PDF

Recursos:
- Token via variável de ambiente (TELEGRAM_TOKEN)
- Predição com RandomForest usando encoding consistente (encoder salvo, se disponível; fallback para get_dummies)
- Relatório consolidado por obra (risco médio previsto, pior etapa, fornecedor/material mais crítico)
- Gráfico por etapas da obra (risco previsto médio)
- Gráfico comparativo entre cidades (risco previsto médio)
- Exportação de relatório + gráficos em PDF consolidado para análise offline
- Logging e mensagens de erro amigáveis
"""

import os
import logging
from io import BytesIO
from typing import List, Optional

import numpy as np
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

# -----------------------------
# Configurações de Caminho
# -----------------------------
MODEL_PATH = "models/modelo_random_forest.pkl"
# Base detalhada (obra + etapa + material). Necessária para predição e gráficos.
BASE_DETALHADA_PATH = "data/raw/base_consulta_bot.csv"
# Opcional: base consolidada gerada (não usada para predição, apenas referência)
BASE_CONSOLIDADA_PATH = "data/raw/relatorio_consolidado.csv"
# Encoder salvo do treino (opcional, recomendado para consistência)
ENCODER_PATH = "models/onehot_encoder.pkl"
# Pasta para exportar PDFs
REPORTS_PATH = "data/reports"
os.makedirs(REPORTS_PATH, exist_ok=True)

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("telegram_bot_mrv")

# -----------------------------
# Carregamento de Recursos
# -----------------------------
def load_model(path: str):
    try:
        model = joblib.load(path)
        logger.info("✅ Modelo RandomForest carregado.")
        return model
    except Exception as e:
        logger.error(f"❌ Erro ao carregar modelo: {e}")
        return None

def load_csv(path: str) -> Optional[pd.DataFrame]:
    try:
        df = pd.read_csv(path)
        logger.info(f"✅ Base carregada: {path}")
        return df
    except Exception as e:
        logger.error(f"❌ Erro ao carregar CSV ({path}): {e}")
        return None

def load_encoder(path: str):
    if not os.path.exists(path):
        logger.info("ℹ️ Encoder não encontrado, usando get_dummies com alinhamento.")
        return None
    try:
        enc = joblib.load(path)
        logger.info("✅ Encoder carregado.")
        return enc
    except Exception as e:
        logger.warning(f"⚠️ Não foi possível carregar o encoder: {e}. Usando get_dummies.")
        return None

model = load_model(MODEL_PATH)
df_base = load_csv(BASE_DETALHADA_PATH)
df_consolidada = load_csv(BASE_CONSOLIDADA_PATH)  # opcional, não obrigatório
encoder = load_encoder(ENCODER_PATH)

# Colunas de treino (fallback se não houver encoder com nomes)
COLUNAS_TREINO: List[str] = [
    "orcamento_estimado", "rating_confiabilidade", "taxa_insucesso_fornecedor",
    "complexidade_obra", "risco_etapa",
    "material_Aço", "material_Brita", "material_Cimento", "material_Madeira",
    "material_Piso", "material_Revestimento", "material_Tintas",
    "cidade_Belo Horizonte", "cidade_Curitiba", "cidade_Rio de Janeiro",
    "cidade_Salvador", "cidade_São Paulo",
    "etapa_Acabamento", "etapa_Estrutura", "etapa_Fundação"
]

# Se o encoder fornecer nomes de features, tente usar dinamicamente
try:
    if encoder is not None and hasattr(encoder, "get_feature_names_out"):
        # Para OneHotEncoder moderno, é melhor construir nomes com base nas colunas categóricas
        # mas como temos features numéricas também, manteremos fallback manual e usaremos encoder só na transformação.
        logger.info("ℹ️ Usando nomes de features do encoder apenas para as categorias durante transformação.")
except Exception:
    pass

# -----------------------------
# Utilitários de ML
# -----------------------------
def alinhar_colunas_treino(X_encoded: pd.DataFrame, colunas_treino: List[str]) -> pd.DataFrame:
    for col in colunas_treino:
        if col not in X_encoded.columns:
            X_encoded[col] = 0
    return X_encoded[colunas_treino]

def preparar_features(df_obra: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara features para predição:
    - Remove id_obra
    - One-hot nas colunas categóricas (encoder salvo se disponível; senão get_dummies)
    - Alinha com COLUNAS_TREINO
    """
    X_input = df_obra.drop(columns=["id_obra"], errors="ignore")
    cat_cols = ["material", "cidade", "etapa"]

    if encoder is not None:
        try:
            X_num = X_input.drop(columns=cat_cols, errors="ignore")
            X_cat = X_input[cat_cols].astype(str)
            X_cat_enc = encoder.transform(X_cat)  # sparse/denso
            # Feature names podem ou não existir; se existirem, use-os
            try:
                cat_feature_names = encoder.get_feature_names_out(cat_cols)
            except Exception:
                cat_feature_names = [f"cat_{i}" for i in range(
                    X_cat_enc.shape[1] if hasattr(X_cat_enc, "shape") else len(X_cat_enc[0])
                )]
            X_cat_df = pd.DataFrame(
                X_cat_enc.toarray() if hasattr(X_cat_enc, "toarray") else X_cat_enc,
                columns=cat_feature_names
            )
            X_encoded = pd.concat([X_num.reset_index(drop=True), X_cat_df.reset_index(drop=True)], axis=1)
        except Exception as e:
            logger.warning(f"⚠️ Falha no uso do encoder salvo: {e}. Usando get_dummies.")
            X_encoded = pd.get_dummies(X_input, columns=cat_cols)
    else:
        X_encoded = pd.get_dummies(X_input, columns=cat_cols)

    # Alinhar com colunas de treino (fallback manual)
    X_final = alinhar_colunas_treino(X_encoded, COLUNAS_TREINO)
    return X_final

def prever(df_obra: pd.DataFrame) -> np.ndarray:
    X_final = preparar_features(df_obra)
    return model.predict(X_final).astype(float)

def emoji_risco(dias: float) -> str:
    if dias > 15:
        return "🔴"
    if dias > 5:
        return "🟡"
    return "🟢"

# -----------------------------
# Relatórios e Visualizações
# -----------------------------
def gerar_relatorio_inteligente(id_obra: str, df_obra: pd.DataFrame) -> str:
    """
    Relatório preditivo por obra:
    - Predição linha a linha (etapa/material)
    - Risco médio previsto
    - Pior cenário (maior atraso previsto)
    - Fornecedor/material mais crítico (maior taxa de insucesso na obra)
    """
    predicoes = prever(df_obra)
    df_obra = df_obra.copy()
    df_obra["predicao_atraso"] = predicoes

    risco_medio_previsto = float(df_obra["predicao_atraso"].mean())
    idx_pior = int(df_obra["predicao_atraso"].idxmax())
    pior_linha = df_obra.loc[idx_pior]

    cidade = str(df_obra["cidade"].iloc[0])
    orcamento = float(df_obra["orcamento_estimado"].iloc[0])
    fornecedor_critico = str(df_obra.loc[df_obra["taxa_insucesso_fornecedor"].idxmax(), "material"])
    taxa_critica = float(df_obra["taxa_insucesso_fornecedor"].max())

    status_geral = emoji_risco(risco_medio_previsto)

    relatorio = (
        f"{status_geral} *RELATÓRIO PREDITIVO MRV*\n"
        f"-------------------------------------------\n"
        f"📍 *Obra:* {id_obra}\n"
        f"🏢 *Cidade:* {cidade}\n"
        f"💰 *Orçamento:* R$ {orcamento:,.2f}\n"
        f"-------------------------------------------\n"
        f"📊 *MÉTRICAS DE IA*\n"
        f"• Risco Médio Estimado: `{risco_medio_previsto:.1f} dias`\n"
        f"• Fornecedor mais crítico: {fornecedor_critico} (taxa insucesso {taxa_critica:.2%})\n\n"
        f"⚠️ *PIOR CENÁRIO*\n"
        f"• Etapa: {pior_linha['etapa']}\n"
        f"• Componente (material): {pior_linha['material']}\n"
        f"• Atraso Previsto: `{pior_linha['predicao_atraso']:.1f} dias`\n"
        f"• Taxa Fornecedor: {pior_linha['taxa_insucesso_fornecedor']:.2%}\n"
        f"-------------------------------------------\n"
        f"💡 *Sugestão:* Avalie redundância de fornecedores na etapa de {pior_linha['etapa']}."
    )
    return relatorio

def gerar_grafico_etapas_previstas(id_obra: str, df_obra: pd.DataFrame) -> BytesIO:
    """
    Gráfico de barras do risco previsto médio por etapa (para a obra consultada).
    """
    predicoes = prever(df_obra)
    df_obra = df_obra.copy()
    df_obra["predicao_atraso"] = predicoes

    etapas_prev = df_obra.groupby("etapa")["predicao_atraso"].mean().sort_values()

    plt.figure(figsize=(6.5, 4.5))
    etapas_prev.plot(kind="bar", color="#5DADE2", edgecolor="black")
    plt.title(f"Risco previsto médio por etapa — {id_obra}")
    plt.ylabel("Dias de atraso (previsto)")
    plt.xlabel("Etapa")
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()
    return buf

def gerar_grafico_cidades_previstas(df_detalhada: pd.DataFrame) -> BytesIO:
    """
    Gráfico comparativo de risco previsto médio por cidade (todas as obras).
    """
    # Predição para toda a base detalhada (pode ser custoso se a base for muito grande)
    df_all = df_detalhada.copy()
    pred_all = prever(df_all)
    df_all["predicao_atraso"] = pred_all

    cidades_prev = df_all.groupby("cidade")["predicao_atraso"].mean().sort_values()

    plt.figure(figsize=(7.5, 5))
    cidades_prev.plot(kind="bar", color="#F5B041", edgecolor="black")
    plt.title("Comparativo — Risco previsto médio por cidade (todas as obras)")
    plt.ylabel("Dias de atraso (previsto)")
    plt.xlabel("Cidade")
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()
    return buf

def gerar_pdf_relatorio(id_obra: str, df_obra: pd.DataFrame, df_detalhada: pd.DataFrame) -> str:
    """
    Gera PDF consolidado com:
    - Página 1: relatório textual
    - Página 2: gráfico por etapas (obra)
    - Página 3: gráfico comparativo por cidades (todas as obras)
    """
    pdf_path = os.path.join(REPORTS_PATH, f"relatorio_{id_obra}.pdf")

    # Página textual (sem Markdown/itálico no PDF)
    relatorio_texto = gerar_relatorio_inteligente(id_obra, df_obra).replace("*", "").replace("`", "")

    with PdfPages(pdf_path) as pdf:
        # Página 1 — texto
        fig, ax = plt.subplots(figsize=(8.5, 11))
        ax.axis("off")
        ax.text(0.06, 0.95, relatorio_texto, va="top", fontsize=12, wrap=True)
        pdf.savefig(fig)
        plt.close(fig)

        # Página 2 — gráfico por etapas
        buf_etapas = gerar_grafico_etapas_previstas(id_obra, df_obra)
        img = plt.imread(buf_etapas)
        fig2, ax2 = plt.subplots(figsize=(8.5, 6))
        ax2.imshow(img)
        ax2.axis("off")
        pdf.savefig(fig2)
        plt.close(fig2)

        # Página 3 — gráfico comparativo cidades
        buf_cidades = gerar_grafico_cidades_previstas(df_detalhada)
        img2 = plt.imread(buf_cidades)
        fig3, ax3 = plt.subplots(figsize=(8.5, 6))
        ax3.imshow(img2)
        ax3.axis("off")
        pdf.savefig(fig3)
        plt.close(fig3)

    return pdf_path

# -----------------------------
# Handlers do Telegram
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏗️ *Sistema de Risco MRV Ativo*\n\n"
        "Envie o ID da obra (ex: `MRV-100`) para receber:\n"
        "• Relatório preditivo consolidado\n"
        "• Gráfico por etapas\n"
        "• Comparativo por cidades\n"
        "• PDF consolidado para análise offline",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_usuario = update.message.text.upper().strip()
    logger.info(f"Consulta: {id_usuario}")

    if df_base is None or model is None:
        await update.message.reply_text("❌ Sistema offline. Verifique os arquivos .pkl e .csv em data/raw.")
        return

    df_obra = df_base[df_base["id_obra"] == id_usuario]
    if df_obra.empty:
        await update.message.reply_text(f"❌ Obra `{id_usuario}` não encontrada na base detalhada.", parse_mode=ParseMode.MARKDOWN)
        return

    await update.message.reply_text("🔍 Processando modelos de IA, gerando gráficos e montando PDF...")

    try:
        # 1) Relatório textual
        texto_relatorio = gerar_relatorio_inteligente(id_usuario, df_obra)
        await update.message.reply_text(texto_relatorio, parse_mode=ParseMode.MARKDOWN)

        # 2) Gráfico por etapas
        grafico_etapas = gerar_grafico_etapas_previstas(id_usuario, df_obra)
        await update.message.reply_photo(photo=grafico_etapas, caption="📊 Risco previsto médio por etapa")

        # 3) Gráfico comparativo por cidades
        grafico_cidades = gerar_grafico_cidades_previstas(df_base)
        await update.message.reply_photo(photo=grafico_cidades, caption="🌍 Comparativo de risco previsto médio por cidade")

        # 4) PDF consolidado
        pdf_path = gerar_pdf_relatorio(id_usuario, df_obra, df_base)
        with open(pdf_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=os.path.basename(pdf_path),
                caption="📑 Relatório consolidado em PDF"
            )

    except Exception as e:
        logger.error(f"Erro no processamento: {e}")
        await update.message.reply_text(
            "❌ Erro ao gerar predição/relatórios. Verifique o alinhamento das colunas, encoder e base.",
            parse_mode=ParseMode.MARKDOWN
        )

# -----------------------------
# Execução
# -----------------------------
def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("ERRO: Defina a variável de ambiente TELEGRAM_TOKEN")
        print("ERRO: Defina a variável de ambiente TELEGRAM_TOKEN")
        return

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    logger.info("🚀 Bot MRV Online!")
    app.run_polling()

if __name__ == "__main__":
    main()
