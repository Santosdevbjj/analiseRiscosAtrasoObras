from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from i18n import TEXTS
from database import get_language, set_language


def resolve_language(update):
    user_id = update.effective_user.id
    lang = get_language(user_id)
    return lang if lang else "pt"


def start_command(update, context):
    lang = resolve_language(update)

    keyboard = [
        [
            InlineKeyboardButton("🇧🇷 Português", callback_data="lang_pt"),
            InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")
        ]
    ]

    update.message.reply_text(
        TEXTS[lang]["start"],
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


def help_command(update, context):
    lang = resolve_language(update)
    update.message.reply_text(TEXTS[lang]["help"], parse_mode=ParseMode.MARKDOWN)


def about_command(update, context):
    lang = resolve_language(update)
    update.message.reply_text(TEXTS[lang]["about"], parse_mode=ParseMode.MARKDOWN)


def status_command(update, context):
    lang = resolve_language(update)
    update.message.reply_text(TEXTS[lang]["status"])


def language_callback(update, context):
    query = update.callback_query
    lang = query.data.split("_")[1]

    set_language(query.from_user.id, lang)
    query.answer()
    query.edit_message_text(TEXTS[lang]["language_changed"])
