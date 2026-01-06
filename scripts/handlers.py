import pytz
import logging
import os
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

# Importações customizadas do seu projeto
from i18n import TEXTS
from database import get_language, set_language

# Configuração de Fuso Horário
BR_TIMEZONE = pytz.timezone('America/Sao_Paulo')

def get_now_br():
    """Retorna a hora atual de Brasília formatada."""
    return datetime.now(BR_TIMEZONE).strftime("%d/%m/%Y %H:%M:%S")

def resolve_language(update: Update):
    """Resolve o idioma do usuário consultando o SQLite."""
    user_id = update.effective_user.id if update.effective_user else None
    if not user_id: 
        return "pt"
    lang = get_language(user_id)
    return lang if lang else "pt"

# --- HANDLERS DE COMANDO ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando inicial: Força a exibição do menu de idiomas.
    """
    # Sempre buscamos o idioma atual para a saudação, mas mostramos as opções
    lang = resolve_language(update)
    
    keyboard = [[
        InlineKeyboardButton("🇧🇷 Português", callback_data="lang_pt"),
        InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")
    ]]
    
    await update.message.reply_text(
        text=TEXTS[lang]["start"],
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe o guia de comandos baseado no idioma salvo."""
    lang = resolve_language(update)
    await update.message.reply_text(TEXTS[lang]["help"], parse_mode=ParseMode.MARKDOWN)

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Explica sobre a CCBJJ."""
    lang = resolve_language(update)
    await update.message.reply_text(TEXTS[lang]["about"], parse_mode=ParseMode.MARKDOWN)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra o status do servidor e hora local."""
    hora_br = get_now_br()
    status_text = f"🖥️ **Server Status (Render)**\n✅ Online\n⏰ BRT: `{hora_br}`"
    await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)

async def language_manual_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /language para troca rápida via texto."""
    user_id = update.effective_user.id
    if context.args:
        new_lang = context.args[0].lower()
        if new_lang in ["pt", "en"]:
            set_language(user_id, new_lang)
            msg = "✅ Idioma alterado!" if new_lang == "pt" else "✅ Language changed!"
            await update.message.reply_text(msg)
            return
    await update.message.reply_text("Use: `/language pt` ou `/language en`", parse_mode=ParseMode.MARKDOWN)

async def healthcheck_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verificação simples de integridade."""
    await update.message.reply_text("✅ System Healthy")

# --- CALLBACKS DE BOTÕES ---

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Processa a escolha do idioma e engatilha o menu de infraestrutura.
    """
    query = update.callback_query
    await query.answer()
    
    # Extração segura dos dados do callback (ex: lang_pt -> pt)
    try:
        lang_choice = query.data.split("_")[1]
    except (IndexError, AttributeError):
        lang_choice = "pt"

    user_id = query.from_user.id
    
    # Salva no Banco SQLite local (Persistência)
    set_language(user_id, lang_choice)
    
    # 1. Edita a mensagem original para confirmar o idioma e REMOVER as bandeiras
    await query.edit_message_text(
        text=TEXTS[lang_choice]["language_changed"],
        parse_mode=ParseMode.MARKDOWN
    )
    
    # 2. Envia o menu de infraestrutura como uma NOVA mensagem
    # Importação local para evitar importação circular com telegram_bot.py
    try:
        from telegram_bot import obter_menu_infra
        await query.message.reply_text(
            text=TEXTS[lang_choice]["infra_select"],
            reply_markup=obter_menu_infra(),
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logging.error(f"Erro ao carregar menu de infraestrutura: {e}")
        # Fallback caso o menu falhe
        await query.message.reply_text("Configuração salva. Digite o ID da obra para analisar.")
