"""
Módulo de Internacionalização (i18n) - CCBJJ Engenharia
Versão: 2.0.0
Última atualização: 2026-01-06
"""

import logging
logger = logging.getLogger(__name__)

TEXTS = {
    "pt": {
        "start": "🏗️ **CCBJJ ENGENHARIA & AI**\n\nSelecione o idioma para começar:",
        "welcome": "🏗️ **CCBJJ ENGENHARIA & AI**\n\nSelecione o idioma para começar:",
        "language_changed": "✅ Idioma alterado para Português.",
        "language_changed_full": "✅ Idioma alterado para Português.\n\n{infra_select}",
        "infra_select": "Selecione o modo de infraestrutura de dados:",
        "setup_complete": (
            "✅ **Configuração Concluída!**\n\n🌐 Idioma: `PT`\n🔌 Fonte: `{modo}`\n\n"
            "Digite o ID da obra para análise (ex: CCBJJ-100)."
        ),
        "mode_changed_full": (
            "✅ Modo definido para `{modo}`.\nAgora digite o ID da obra para análise (ex: CCBJJ-100)."
        ),

        "help": (
            "❓ **Central de Ajuda CCBJJ**\n\n"
            "1. Envie o **ID da Obra** para gerar relatórios preditivos.\n"
            "2. Use /settings para trocar entre CSV e Supabase.\n"
            "3. Use /language para alterar o idioma.\n\n"
            "O sistema utiliza IA para prever atrasos com base no histórico logístico."
        ),

        "processing": "🔍 **Processando Inteligência de Dados...**",
        "not_found": "❌ Obra `{id_obra}` não localizada na base `{modo}`.",

        "report_header": "🏗️ **ANÁLISE PREDITIVA CCBJJ**",
        "report_impact": "⏳ **Impacto Projetado:** `{risco:.2f} dias`",
        "report_status": "🚦 **Risco:** {status}",
        "report_note": (
            "📝 **Parecer Técnico:**\nO modelo detectou variações baseadas em tendências históricas. "
            "A classificação {status} sugere revisão imediata dos marcos críticos."
        ),
        "sending_files": "_Gerando gráficos e PDF oficial..._",

        "pdf_title": "RELATÓRIO TÉCNICO DE INTELIGÊNCIA PREDITIVA",
        "pdf_section_1": "1. DIAGNÓSTICO DA UNIDADE",
        "pdf_section_2": "2. ANÁLISE DO MODELO PREDITIVO (ML)",
        "pdf_footer": "Confidencial - CCBJJ Engenharia & Inteligência",

        "chart_title": "Impacto Previsto no Cronograma",
        "chart_legend": "Verde: Normal | Amarelo: Alerta | Vermelho: Crítico"
    },

    "en": {
        "start": "🏗️ **CCBJJ ENGINEERING & AI**\n\nSelect your language to begin:",
        "welcome": "🏗️ **CCBJJ ENGINEERING & AI**\n\nSelect your language to begin:",
        "language_changed": "✅ Language changed to English.",
        "language_changed_full": "✅ Language changed to English.\n\n{infra_select}",
        "infra_select": "Select the data infrastructure mode:",
        "setup_complete": (
            "✅ **Setup Complete!**\n\n🌐 Language: `EN`\n🔌 Source: `{modo}`\n\n"
            "Send the Project ID for analysis (e.g., CCBJJ-100)."
        ),
        "mode_changed_full": (
            "✅ Mode set to `{modo}`.\nNow send the Project ID for analysis (e.g., CCBJJ-100)."
        ),

        "help": (
            "❓ **CCBJJ Help Center**\n\n"
            "1. Send the **Project ID** to generate predictive reports.\n"
            "2. Use /settings to toggle between CSV and Supabase.\n"
            "3. Use /language to change language.\n\n"
            "The system uses AI to predict delays based on logistics history."
        ),

        "processing": "🔍 **Processing Data Intelligence...**",
        "not_found": "❌ Project `{id_obra}` not found in `{modo}` source.",

        "report_header": "🏗️ **CCBJJ PREDICTIVE ANALYSIS**",
        "report_impact": "⏳ **Projected Impact:** `{risco:.2f} days`",
        "report_status": "🚦 **Risk Status:** {status}",
        "report_note": (
            "📝 **Technical Note:**\nThe model identified variations based on historical trends. "
            "The {status} status suggests an immediate review of critical milestones."
        ),
        "sending_files": "_Generating official charts and PDF..._",

        "pdf_title": "PREDICTIVE INTELLIGENCE TECHNICAL REPORT",
        "pdf_section_1": "1. UNIT DIAGNOSTICS",
        "pdf_section_2": "2. PREDICTIVE MODEL ANALYSIS (ML)",
        "pdf_footer": "Confidential - CCBJJ Engineering & Data Intelligence",

        "chart_title": "Predicted Schedule Impact",
        "chart_legend": "Green: Normal | Yellow: Warning | Red: Critical"
    }
}

def get_text(lang: str, key: str, **kwargs) -> str:
    """
    Retorna a mensagem traduzida com suporte a placeholders e fallback seguro.
    Uso: get_text("pt", "not_found", id_obra="CCBJJ-100", modo="CSV")
    """
    language_pack = TEXTS.get(lang, TEXTS.get("en", TEXTS["pt"]))
    message = language_pack.get(key, f"⚠️ Missing translation for: {key}")
    try:
        return message.format(**kwargs) if kwargs else message
    except KeyError as e:
        logger.warning(f"Missing placeholder {e} for key '{key}' (lang='{lang}')")
        return f"{message} (Error: missing placeholder {e})"
