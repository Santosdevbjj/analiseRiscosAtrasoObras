import pytz
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from i18n import TEXTS
from database import get_language, set_language

# Configuração de Fuso Horário
BR_TIMEZONE = pytz.timezone('America/Sao_Paulo')

def get_now_br():
    return datetime.now(BR_TIMEZONE).strftime("%d/%m/%Y %H:%M:%S")

def resolve_language(update: Update):
    user_id = update.effective_user.id
    return get_language(user_id) or "pt"

async def start_command(update, context):
    lang = resolve_language(update)
    keyboard = [[
        InlineKeyboardButton("🇧🇷 Português", callback_data="lang_pt"),
        InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")
    ]]
    await update.message.reply_text(
        TEXTS[lang]["start"],
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def help_command(update, context):
    lang = resolve_language(update)
    await update.message.reply_text(TEXTS[lang]["help"], parse_mode=ParseMode.MARKDOWN)

async def language_manual_command(update, context):
    """Implementa /language pt ou /language en"""
    if context.args:
        new_lang = context.args[0].lower()
        if new_lang in ["pt", "en"]:
            set_language(update.effective_user.id, new_lang)
            await update.message.reply_text(TEXTS[new_lang]["language_changed"])
            return
    await update.message.reply_text("Uso / Use: `/language pt` ou `/language en`", parse_mode=ParseMode.MARKDOWN)

async def status_command(update, context):
    """Simula uptime do Render e mostra hora de Brasília"""
    lang = resolve_language(update)
    hora_br = get_now_br()
    status_text = f"🖥️ **Server Status (Render)**\n✅ Online\n⏰ BRT: `{hora_br}`\n📡 Latency: 24ms"
    await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)

async def example_command(update, context):
    lang = resolve_language(update)
    await update.message.reply_text(TEXTS[lang]["example_msg"], parse_mode=ParseMode.MARKDOWN)

async def healthcheck_command(update, context):
    lang = resolve_language(update)
    await update.message.reply_text(TEXTS[lang]["health_ok"])
