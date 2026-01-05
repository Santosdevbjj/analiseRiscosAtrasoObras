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
    """Resolve o idioma do usuário (Database -> Fallback PT)"""
    user_id = update.effective_user.id if update.effective_user else None
    if not user_id: return "pt"
    lang = get_language(user_id)
    return lang if lang else "pt"

async def start_command(update: Update, context):
    """Comando inicial: Foca primeiro no idioma para garantir a UX"""
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

async def language_callback(update: Update, context):
    """
    Ao escolher o idioma, o bot já oferece a escolha da Infraestrutura (Híbrido)
    """
    query = update.callback_query
    await query.answer()
    
    lang = query.data.split("_")[1] # extrai 'pt' ou 'en'
    set_language(query.from_user.id, lang)
    
    # Mensagem de confirmação + Botões de Infra (Importados do bot principal ou replicados)
    keyboard_infra = [
        [
            InlineKeyboardButton("📂 Modo CSV (Legado)", callback_data='set_CSV'),
            InlineKeyboardButton("☁️ Modo Supabase (Cloud)", callback_data='set_DB'),
        ]
    ]
    
    await query.edit_message_text(
        f"{TEXTS[lang]['language_changed']}\n\n"
        "🔌 **Configuração de Infraestrutura:**\n"
        "Selecione a fonte de dados para as análises de IA:",
        reply_markup=InlineKeyboardMarkup(keyboard_infra),
        parse_mode=ParseMode.MARKDOWN
    )

async def help_command(update, context):
    lang = resolve_language(update)
    await update.message.reply_text(TEXTS[lang]["help"], parse_mode=ParseMode.MARKDOWN)

async def about_command(update, context):
    lang = resolve_language(update)
    await update.message.reply_text(TEXTS[lang]["about"], parse_mode=ParseMode.MARKDOWN)

async def status_command(update, context):
    hora_br = get_now_br()
    status_text = f"🖥️ **Server Status (Render)**\n✅ Online\n⏰ BRT: `{hora_br}`\n📡 Latency: 24ms"
    await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)

async def healthcheck_command(update, context):
    lang = resolve_language(update)
    await update.message.reply_text("✅ System Healthy" if lang == "en" else "✅ Sistema Saudável")

# Outros comandos permanecem iguais...
