# handlers/common_handlers.py
from contextlib import suppress
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.error import BadRequest
import random
import io
import base64
import re
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from typing import List, Optional, Tuple
from datetime import datetime
import shutil

import database
import keyboards
import config
from utils import safe_md, beautify_text, add_library_item, now_iso

# --- Admin IDs compatibility helper ---
def _admin_ids():
    return getattr(config, 'ADMIN_IDS', getattr(config, 'ADMIN_USER_IDS', []))

# --- Simple text→image helper (centered text, auto-wrap naive) ---
def _text_to_image(lines: List[str], width: int = 1080, height: int = 1350) -> io.BytesIO:
    """Render a rich study card image from plain text lines."""

    def _grad_bg(w: int, h: int) -> Image.Image:
        top = (37, 56, 149)
        bottom = (14, 23, 63)
        bg = Image.new('RGBA', (w, h))
        draw_bg = ImageDraw.Draw(bg)
        for y in range(h):
            ratio = y / max(h - 1, 1)
            r = int(top[0] * (1 - ratio) + bottom[0] * ratio)
            g = int(top[1] * (1 - ratio) + bottom[1] * ratio)
            b = int(top[2] * (1 - ratio) + bottom[2] * ratio)
            draw_bg.line([(0, y), (w, y)], fill=(r, g, b, 255))
        return bg

    def _load_font(candidates: List[str], size: int) -> ImageFont.FreeTypeFont:
        for path in candidates:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
        return ImageFont.load_default()

    font_candidates_main = [
        '/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
        '/System/Library/Fonts/Supplemental/GeezaPro.ttf',
        '/System/Library/Fonts/SFNSRounded.ttf',
        '/Library/Fonts/Arial Unicode.ttf',
        '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    ]
    font_candidates_title = [
        '/System/Library/Fonts/SFNSDisplay.ttf',
        '/System/Library/Fonts/Supplemental/Al Bayan.ttc',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    ]

    title_font = _load_font(font_candidates_title, 64)
    lead_font = _load_font(font_candidates_title, 28)
    body_font = _load_font(font_candidates_main, 36)
    meta_font = _load_font(font_candidates_main, 28)

    cleaned = [str(line or '').strip() for line in lines if str(line or '').strip()]
    card_title = "Smart Study Snapshot"
    if cleaned:
        candidate = cleaned[0]
        if len(candidate) <= 65 and ' ' in candidate:
            card_title = candidate
            cleaned = cleaned[1:]
        else:
            card_title = candidate[:65]

    if not cleaned:
        cleaned = [card_title]

    bg = _grad_bg(width, height)

    margin = 90
    card_w = width - margin * 2
    card_h = height - margin * 2
    card = Image.new('RGBA', (card_w, card_h), (255, 255, 255, 235))
    card_draw = ImageDraw.Draw(card)

    shadow = Image.new('RGBA', (card_w + 60, card_h + 60), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((30, 30, card_w + 30, card_h + 30), radius=48, fill=(0, 0, 0, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    bg.alpha_composite(shadow, (margin - 30, margin - 30))

    card_draw.rounded_rectangle((0, 0, card_w, card_h), radius=44, fill=(255, 255, 255, 240))

    accent_color = (92, 120, 255)
    meta_color = (103, 116, 155)
    body_color = (24, 32, 58)

    card_draw.rounded_rectangle((40, 40, card_w - 40, 120), radius=26, fill=(240, 244, 255, 255))
    card_draw.text((60, 62), "Al Madina Focus Sheet", font=lead_font, fill=accent_color)

    card_draw.text((60, 150), card_title, font=title_font, fill=body_color)
    timestamp = datetime.now().strftime('%d %B %Y – %I:%M %p')
    card_draw.text((60, 150 + title_font.size + 32), timestamp, font=meta_font, fill=meta_color)

    body_start_y = 150 + title_font.size + 32 + meta_font.size + 48
    text_left = 80
    bullet_indent = 36
    max_text_width = card_w - text_left - 60

    def wrap_text(line: str, font: ImageFont.FreeTypeFont, limit: int) -> List[str]:
        words = line.split()
        if not words:
            return ['']
        wrapped: List[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if font.getlength(candidate) <= limit:
                current = candidate
            else:
                wrapped.append(current)
                current = word
        wrapped.append(current)
        return wrapped

    def is_bullet(text_line: str) -> bool:
        stripped_line = text_line.lstrip()
        prefixes = ('- ', '• ', '▪', '· ', '— ', '– ', '* ', '❓', '✅', '⚠️', '🔥', '🎯', '🧠', '🧪', '🚀', '📌')
        return any(stripped_line.startswith(prefix) for prefix in prefixes)

    y_cursor = body_start_y
    for raw in cleaned:
        if not raw.strip():
            y_cursor += int(body_font.size * 0.8)
            continue

        bullet = is_bullet(raw)
        text_line = raw.lstrip('-•▪·—–* ')
        if bullet and len(raw) >= 2 and raw.strip()[0] in {'❓', '✅', '⚠️', '🔥', '🎯', '🧠', '🧪', '🚀', '📌'}:
            emoji = raw.strip()[0]
            text_line = raw.strip()[2:].lstrip()
        else:
            emoji = None

        pieces = wrap_text(text_line, body_font, max_text_width if not bullet else max_text_width - bullet_indent)
        for idx, piece in enumerate(pieces):
            if y_cursor > card_h - 100:
                break
            x_pos = text_left
            if bullet:
                if idx == 0:
                    if emoji:
                        card_draw.text((x_pos, y_cursor), emoji, font=body_font, fill=accent_color)
                    else:
                        card_draw.ellipse((x_pos, y_cursor + 14, x_pos + 12, y_cursor + 26), fill=accent_color)
                    x_pos += bullet_indent
                else:
                    x_pos += bullet_indent
            card_draw.text((x_pos, y_cursor), piece, font=body_font, fill=body_color)
            y_cursor += body_font.size + 12
        if y_cursor > card_h - 100:
            break
        y_cursor += 8

    composed = Image.new('RGBA', (width, height))
    composed.alpha_composite(bg)
    composed.alpha_composite(card, (margin, margin))

    final_img = composed.convert('RGB')
    bio = io.BytesIO()
    final_img.save(bio, format='PNG', optimize=True)
    bio.seek(0)
    return bio

from ai_services import (
    ai_summarize_bilingual,
    ai_call_with_fallback,
    extract_audio_from_youtube,
    clamp_text,
    ai_generate_flashcards,
    ai_generate_study_plan,
    ai_generate_focus_notes,
    ai_translate_dual,
    preclean_text_for_ai,
    extract_glossary_json,
)
from file_generator import (
    build_pdf_from_lines_weasy as build_stylish_pdf,
    build_dual_language_pdf,
    build_text_to_pdf
)
from telegraph_utils import publish_bilingual_to_telegraph, publish_lines_to_telegraph
from medical_glossary import find_terms_in_text, merge_glossaries

logger = logging.getLogger(__name__)

# ==================================
# ===== Subscription Checker =======
# ==================================
from functools import wraps

async def is_user_subscribed(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    settings = database.get_settings()
    channel = settings.get("force_sub_channel")
    if not channel:
        return True # Bypass if no channel is set

    try:
        member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
        return member.status in ['creator', 'administrator', 'member']
    except BadRequest as e:
        if "user not found" in str(e).lower(): return False
        if "chat not found" in str(e).lower():
            logger.error(f"Force-subscribe channel '{channel}' not found. Check settings.")
            return True # Bypass check if channel is misconfigured
        logger.error(f"Error checking subscription for {user_id} in {channel}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in is_user_subscribed: {e}")
        return False

def check_subscription(func):
    """Decorator to check for channel subscription before executing a command."""
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if not await is_user_subscribed(user_id, context):
            # You should fetch the invite link dynamically or from settings if possible
            invite_link = "https://t.me/+QwQwQwQwQwQwYjY0  "
            text = (
                "🛑 **عذرًا، يجب عليك الاشتراك في القناة أولاً لاستخدام البوت.**\n\n"
                "1. اشترك في القناة.\n"
                "2. ارجع واضغط /start مرة أخرى."
            )
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 الاشتراك في القناة", url=invite_link)]])
            if update.callback_query:
                await update.callback_query.answer("يرجى الاشتراك أولاً.", show_alert=True)
                # Send a new message because you can't always edit a message to have a URL button
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=keyboard)
            else:
                await update.effective_message.reply_text(text, reply_markup=keyboard)
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

# ==================================
# ======== Command Handlers ========
# ==================================
@check_subscription
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """الدالة الرئيسية اللي بتتعامل مع /start وأزرار الرجوع."""
    user = database.ensure_user(update.effective_user.id, update.effective_user.full_name)
    context.user_data['user'] = user

    caption_text = (
        f"👋 أهلاً بك يا {safe_md(user['name'])}!\n\n"
        f"أنا **Al Madina Al Taalimia**، مساعدك التعليمي الذكي.\n"
        "\nاختر ميزة وابدأ فورًا:"
        "\n- 📝 ملخص: حول نصك لملخص مذاكرة شامل"
        "\n- 💡 شرح: تبسيط + أمثلة + أسئلة مراجعة"
        "\n- 🧠 خريطة ذهنية: Mind Map منظمة"
        "\n- 🎲 اختبار ذكي: أسئلة اختيار من متعدد"
        "\n- ⚙️ مزايا إضافية: أدوات تحويل سريعة (OCR/نص→PDF/صورة)"
    )

    final_state = config.MAIN_MENU # الافتراضي هو القائمة الرئيسية
    
    ask_for_phone = not user.get("phone_number")
    if ask_for_phone:
        caption_text += "\n✨ للحصول على أفضل تجربة، يرجى مشاركة رقم هاتفك."
        reply_markup = keyboards.ask_for_phone_kb()
        final_state = config.WAITING_INPUT # لو هيطلب الرقم، يبقى الحالة هي انتظار الإدخال
    else:
        if user["session"].get("last_text"):
            caption_text += "\nاختر ما تريد عمله بالمحتوى الذي أرسلته:"
            reply_markup = keyboards.main_menu_kb(user)
        else:
            caption_text += "\n🗂️ لبدء استخدامي، أرسل ملف PDF، نص، أو صورة تعليمية."
            reply_markup = None
            final_state = config.WAITING_INPUT # لو مفيش محتوى، يبقى الحالة هي انتظار الإدخال

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(caption_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Error editing message in start_cmd: {e}")
                await context.bot.send_message(chat_id=update.effective_chat.id, text=caption_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
                with suppress(Exception):
                    await update.callback_query.message.delete()
    else:
        await update.effective_message.reply_text(caption_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    # ✨ --- أهم تعديل: نرجع الحالة الصحيحة عشان ConversationHandler يشتغل صح --- ✨
    return final_state
async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    contact = update.effective_message.contact
    user_id = update.effective_user.id
    
    if user_id != contact.user_id:
        await update.effective_message.reply_text("من فضلك، شارك جهة الاتصال الخاصة بك فقط.")
        return config.WAITING_INPUT

    user = database.ensure_user(user_id, update.effective_user.full_name)
    user['phone_number'] = contact.phone_number
    database._update_user_in_db(user_id, user)

    await update.effective_message.reply_text(
        "✅ شكرًا لك! تم التحقق بنجاح.", reply_markup=ReplyKeyboardRemove()
    )
    # After getting contact, show the main message again
    await start_cmd(update, context)
    return config.MAIN_MENU

async def myid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(f"🆔 ID الخاص بك: `{update.effective_user.id}`", parse_mode=ParseMode.MARKDOWN)

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text("⏹️ تم الإلغاء. أرسل /start للبدء من جديد.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def unknown_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("🤷‍♂️ أمر غير معروف. أرسل /start للوصول للقائمة الرئيسية.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception while handling an update:", exc_info=context.error)
    if isinstance(context.error, BadRequest) and "Message is not modified" in str(context.error):
        return
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ حدث خطأ غير متوقع.\n"
                "تم تسجيل الخطأ وسيتم إصلاحه قريبًا بإذن الله."
            )
    except Exception as e:
        logger.error(f"Failed to send error message to user: {e}")


# ==================================
# ===== Features Callback Router =====
# ==================================
# FIXED: A single router for all "feature_" buttons. This is much cleaner.

async def _make_pdf_and_prompt_download(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: dict,
    title: str,
    lines: List[str],
    session_key: str,
    *,
    pdf_builder=None,
    builder_kwargs: Optional[dict] = None,
    lang: str = 'ar',
    send_direct: bool = False,
    show_main_menu: bool = True
):
    query = update.callback_query
    bot_username = (await context.bot.get_me()).username
    telegraph_url = None
    if pdf_builder:
        builder_kwargs = builder_kwargs or {}
        pdf_bytes, pdf_fname = pdf_builder(title=title, author_username=bot_username, **builder_kwargs)
    else:
        # Normalize bullets for better readability in both PDF and Telegraph
        normalized_text = _explode_inline_bullets("\n".join(lines))
        norm_lines = [ln for ln in normalized_text.split('\n')]
        norm_lines = _normalize_summary_lines(norm_lines)
        pdf_bytes, pdf_fname = build_stylish_pdf(title, bot_username, norm_lines, lang=lang)
        # Try posting a read-friendly web version on Telegraph for standard lines
        try:
            telegraph_url = await publish_lines_to_telegraph(title, norm_lines)
            if telegraph_url:
                user.setdefault('session', {})[f'link_{session_key}'] = telegraph_url
        except Exception as exc:
            logger.debug(f"Telegraph publish failed (non-blocking): {exc}")
    pdf_b64 = base64.b64encode(pdf_bytes.getvalue()).decode('utf-8')
    user['session'][f'file_{session_key}'] = {'pdf': {'data': pdf_b64, 'fname': pdf_fname}}
    database._update_user_in_db(user['id'], user)
    if send_direct:
        # Clean the previous UI and send the document directly
        with suppress(Exception):
            await query.message.delete()
        try:
            await context.bot.send_document(chat_id=user['id'], document=pdf_bytes, filename=pdf_fname, caption=f"✅ {title}")
        except Exception as e:
            logger.error(f"Failed to send document directly: {e}")
        if telegraph_url:
            with suppress(Exception):
                await context.bot.send_message(chat_id=user['id'], text=f"🔗 نسخة ويب: {telegraph_url}")
        # بعد الإرسال المباشر، أظهر القائمة الرئيسية لبدء إجراء جديد
        if show_main_menu:
            with suppress(Exception):
                await context.bot.send_message(chat_id=user['id'], text="اختر إجراءً آخر من القائمة:", reply_markup=keyboards.main_menu_kb(user))
        return
    else:
        rows = [[InlineKeyboardButton('📄 تحميل PDF', callback_data=f'download_pdf_{session_key}')]]
        if telegraph_url:
            rows.append([InlineKeyboardButton('🔗 فتح كصفحة ويب', url=telegraph_url)])
        rows.append([InlineKeyboardButton('⬅️ رجوع', callback_data='start_home')])
        kb = InlineKeyboardMarkup(rows)
        await query.edit_message_text(f"✅ **{title} جاهز!**\n\nاضغط لتحميل الملف.", parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
        # أرسل رسالة منفصلة بالقائمة الرئيسية ليستطيع المستخدم البدء فورًا بخطوة جديدة
        if show_main_menu:
            with suppress(Exception):
                await context.bot.send_message(chat_id=user['id'], text="اختر إجراءً آخر من القائمة:", reply_markup=keyboards.main_menu_kb(user))


async def _send_feature_preview(context: ContextTypes.DEFAULT_TYPE, user: dict, title: str, lines: List[str], *, max_chars: int = 1200) -> None:
    """Send a short preview of the generated content before offering the PDF download."""
    # Respect user's preference to disable previews (default False for clean UX)
    if not user.get('session', {}).get('previews_on', False):
        return
    snippet_lines: List[str] = []
    consumed = 0
    for raw in lines:
        text = (raw or "").rstrip()
        if not text:
            if snippet_lines and snippet_lines[-1] == "":
                continue
            snippet_lines.append("")
            consumed += 1
            continue
        snippet_lines.append(text)
        consumed += len(text) + 1
        if consumed >= max_chars:
            break

    snippet = "\n".join(snippet_lines).strip()
    if not snippet:
        return

    if consumed >= max_chars and len(lines) > len(snippet_lines):
        snippet += "\n...\n(اكمل القراءة عبر ملف الـ PDF 👆)"

    header = f"{title} – معاينة سريعة:\n\n"
    try:
        await context.bot.send_message(chat_id=user['id'], text=header + snippet)
    except Exception as exc:
        logger.debug(f"Failed to send preview message: {exc}")


AI_BOOSTS_FOLDER_ID = 'ai_boosts'


def _ensure_ai_folder(user: dict) -> str:
    """Ensure the dedicated AI Boosts folder exists and return its ID."""
    library = user.setdefault('library', {"folders": {"default": {"name": "📂 عام", "items": []}}, "items": {}})
    folders = library.setdefault('folders', {})
    library.setdefault('items', {})
    if AI_BOOSTS_FOLDER_ID not in folders:
        folders[AI_BOOSTS_FOLDER_ID] = {"name": "🚀 AI Boosts", "items": []}
    return AI_BOOSTS_FOLDER_ID


def _store_feature_in_library(
    user: dict,
    title: str,
    lines: List[str],
    *,
    feature_key: str,
    session_key: str,
    extra: Optional[dict] = None
) -> Tuple[Optional[str], Optional[str]]:
    """Persist generated feature content into the smart library."""
    try:
        folder_id = _ensure_ai_folder(user)
        content = "\n".join(lines).strip()
        history = user.setdefault('session', {}).setdefault('ai_history', [])
        payload = {'feature': feature_key, 'session_key': session_key}
        if extra:
            payload.update(extra)

        item_id = add_library_item(
            user,
            type_='ai_boost',
            title=title,
            content=content,
            folder_id=folder_id,
            extra=payload
        )
        history.append({'item_id': item_id, 'title': title, 'feature': feature_key, 'ts': now_iso()})
        if len(history) > 15:
            del history[:-15]
        database._update_user_in_db(user['id'], user)
        return item_id, folder_id
    except Exception as exc:
        logger.error("Failed to store AI feature in library", exc_info=exc)
        return None, None


def _parse_ts(ts: Optional[str]) -> float:
    try:
        return datetime.fromisoformat(ts).timestamp()
    except Exception:
        return 0.0


def _get_recent_ai_items(user: dict, limit: int = 5) -> List[dict]:
    library = user.get('library', {})
    items = library.get('items', {})
    boosts = [item for item in items.values() if item.get('type') == 'ai_boost']
    boosts.sort(key=lambda item: _parse_ts(item.get('ts')), reverse=True)
    return boosts[:limit]


def _get_library_item(user: dict, item_id: str) -> Optional[dict]:
    return user.get('library', {}).get('items', {}).get(item_id)


async def _send_saved_pdf(context: ContextTypes.DEFAULT_TYPE, user: dict, session_key: str) -> bool:
    entry = user.get('session', {}).get(f'file_{session_key}', {})
    pdf = entry.get('pdf') if isinstance(entry, dict) else None
    if not pdf or not pdf.get('data'):
        return False
    try:
        raw = base64.b64decode(pdf['data'])
    except Exception:
        return False
    bio = io.BytesIO(raw)
    bio.name = pdf.get('fname', 'document.pdf')
    await context.bot.send_document(chat_id=user['id'], document=bio, filename=bio.name, caption="✅ تم التحميل.")
    return True


async def _send_item_content(context: ContextTypes.DEFAULT_TYPE, user: dict, item: dict) -> None:
    content = item.get('content') or ''
    if not content.strip():
        await context.bot.send_message(chat_id=user['id'], text='⚠️ لا يوجد محتوى نصي محفوظ في هذا العنصر.')
        return
    if len(content) <= 3500:
        await context.bot.send_message(chat_id=user['id'], text=content)
    else:
        bio = io.BytesIO(content.encode('utf-8'))
        safe_title = (item.get('title') or 'content').replace(' ', '_')[:40]
        bio.name = f"{safe_title or 'content'}.txt"
        await context.bot.send_document(chat_id=user['id'], document=bio, filename=bio.name, caption='📄 تم إرسال النص الكامل كملف.')


def _explode_inline_bullets(text: str) -> str:
    """Split multiple inline bullets into separate lines to improve readability.
    - Turns pattern like "... - 📚 term ... - 📚 another ..." into new lines per bullet.
    - Also splits after sentence punctuation followed by a dash-bullet.
    """
    s = text or ""
    BULLET_EMOJIS = "📚📖🧠💡📌📝📊✅⚠️🔎🔍🚀🎯🧩"
    # Hyphen then emoji → newline + emoji
    s = re.sub(rf"\s+-\s+([{BULLET_EMOJIS}])", r"\n\1", s)
    s = re.sub(rf"\s+-([{BULLET_EMOJIS}])", r"\n\1", s)
    # Sentence end then hyphen bullet → newline
    s = re.sub(r"([\.!?،؛])\s+-\s+", r"\1\n- ", s)
    return s


def _normalize_summary_lines(lines: List[str]) -> List[str]:
    """Post-process summary/explanation lines for better layout.
    - Collapse "Contents" block into one inline enumerated line
    - Remove "Executive Snapshot" section entirely (heading + its bullets) 
    - Strip tree glyphs (└─, ├─, │) and normalize dashes
    """
    out: List[str] = []
    i = 0
    n = len(lines)
    HEADINGS_STOP = {
        'Complete Outline', 'Concepts & Definitions', 'Key Facts & Numbers',
        'Symbols & Notation', 'Formulas & Calculations', 'Processes & Steps',
        'Examples & Analogies', 'Common Pitfalls', 'Q&A Checkpoints', 'Final Takeaway',
        'المخطط الكامل', 'المفاهيم والتعاريف', 'حقائق وأرقام', 'الرموز والاصطلاحات', 'معادلات وحسابات',
        'العمليات والخطوات', 'أمثلة وتشبيهات', 'مزالق شائعة', 'أسئلة ومراجعات', 'الخلاصة النهائية'
    }
    while i < n:
        ln = (lines[i] or '').rstrip()
        # Strip tree glyphs
        ln = ln.replace('└─', '').replace('├─', '').replace('│', '').strip()

        # Collapse Contents block
        if ln.strip() in ("Contents", "Document Contents", "محتويات المستند", "محتويات"):
            i += 1
            items = []
            while i < n and (lines[i] or '').strip() and (not (lines[i] or '').strip().startswith('<h2>')):
                item = (lines[i] or '').strip(' -•').strip()
                if item and item.lower() != 'executive snapshot':
                    items.append(item)
                i += 1
            if items:
                enum = ' · '.join(f"{idx+1}) {it}" for idx, it in enumerate(items))
                out.append(enum)
            continue

        # Drop Executive Snapshot section completely
        if ln.strip().lower() == 'executive snapshot' or ln.strip() == '<h2>Executive Snapshot</h2>':
            i += 1
            while i < n:
                nxt = (lines[i] or '').strip()
                if not nxt:
                    i += 1
                    break
                if nxt in HEADINGS_STOP or nxt.startswith('<h2>'):
                    break
                i += 1
            continue

        out.append(ln)
        i += 1
    return out


_FOCUS_EN_RE = re.compile(r"[A-Za-z]")
_FOCUS_AR_RE = re.compile(r"[\u0600-\u06FF]")


def _looks_english_focus(line: str) -> bool:
    stripped = (line or '').strip()
    if not stripped:
        return False
    return bool(_FOCUS_EN_RE.search(stripped)) and not _FOCUS_AR_RE.search(stripped)


def _looks_arabic_focus(line: str) -> bool:
    stripped = (line or '').strip()
    if not stripped:
        return False
    return bool(_FOCUS_AR_RE.search(stripped))


def _focus_marker_and_body(segment: str) -> tuple[str, str]:
    markers = ['- ❓', '- ✅', '- 🔥', '- ⚠️', '- 🧠', '- 🧪', '- 🚀', '- 📌', '- 🎯', '- ', '• ', '– ', '— ', '▪︎ ', '· ', '❓ ', '✅ ']
    for marker in markers:
        if segment.startswith(marker):
            return marker, segment[len(marker):].lstrip()
    if segment.startswith('-'):
        return '- ', segment[1:].lstrip()
    return '', segment


def _focus_auto_bold(text: str) -> str:
    if '<b>' in text:
        return text
    match = re.match(r"([^:：]+)([:：])(.*)", text)
    if match and len(match.group(1).strip()) <= 48:
        lead = match.group(1).strip()
        rest = match.group(3).strip()
        colon = match.group(2)
        if lead:
            rest_part = f" {rest}" if rest else ''
            return f"<b>{lead}</b>{colon}{rest_part}"
    return text


def _wrap_focus_line(line: str, role: str) -> str:
    if "focus-line" in line:
        return line
    prefix_ws = re.match(r"\s*", line).group(0)
    core = line[len(prefix_ws):]
    marker, body = _focus_marker_and_body(core)
    formatted = _focus_auto_bold(body)
    return f"{prefix_ws}{marker}<span class='focus-line focus-{role}'>{formatted}</span>"


def _decorate_focus_lines(lines: List[str]) -> List[str]:
    decorated: List[str] = []
    idx = 0
    total = len(lines)
    while idx < total:
        current = lines[idx]
        stripped = (current or '').lstrip()
        starts_with_marker = stripped.startswith('-') or stripped.startswith('❓') or stripped.startswith('✅')
        if starts_with_marker and _looks_english_focus(current):
            next_line = lines[idx + 1] if idx + 1 < total else ''
            if _looks_arabic_focus(next_line):
                decorated.append(_wrap_focus_line(current, 'en'))
                decorated.append(_wrap_focus_line(next_line, 'ar'))
                idx += 2
                continue
            decorated.append(_wrap_focus_line(current, 'en'))
            idx += 1
            continue
        if starts_with_marker and _looks_arabic_focus(current):
            decorated.append(_wrap_focus_line(current, 'ar'))
            idx += 1
            continue
        decorated.append(current)
        idx += 1
    return decorated

async def health_check_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick diagnostics about keys and local tools."""
    try:
        user = database.ensure_user(update.effective_user.id, update.effective_user.full_name)
    except Exception:
        user = None
    checks = []
    # Keys
    import config
    checks.append(f"Telegram token: {'✅ موجود' if bool(getattr(config, 'TELEGRAM_BOT_TOKEN', '')) else '❌ مفقود'}")
    checks.append(f"Gemini key: {'✅ موجود' if bool(getattr(config, 'GEMINI_API_KEY', '')) else '❌ مفقود'}")
    checks.append(f"HuggingFace key: {'✅ موجود' if bool(getattr(config, 'HUGGINGFACE_API_KEY', '')) else '❌ مفقود'}")
    checks.append(f"Telegraph token: {'✅ موجود' if bool(getattr(config, 'TELEGRAPH_ACCESS_TOKEN', None)) else '❌ مفقود'}")
    # Modules/tools
    def has_mod(name):
        try:
            __import__(name)
            return True
        except Exception:
            return False
    checks.append(f"PyMuPDF (fitz): {'✅' if has_mod('fitz') else '❌'}")
    checks.append(f"yt_dlp: {'✅' if has_mod('yt_dlp') else '❌'}")
    checks.append(f"pydub: {'✅' if has_mod('pydub') else '❌'}")
    checks.append(f"pytesseract: {'✅' if has_mod('pytesseract') else '❌'}")
    checks.append(f"weasyprint: {'✅' if has_mod('weasyprint') else '❌'}")
    checks.append(f"ffmpeg (اختياري): {'✅' if shutil.which('ffmpeg') else '❌'}")
    checks.append(f"tesseract (اختياري): {'✅' if shutil.which('tesseract') else '❌'}")
    # Session snapshot
    if user:
        has_ctx = bool(user.get('session', {}).get('last_text'))
        checks.append(f"Session content: {'📄 موجود' if has_ctx else '📭 فارغ'}")
    text = "🩺 فحص النظام\n\n" + "\n".join(f"- {c}" for c in checks)
    await update.effective_message.reply_text(text)


def _clean_ai_artifacts(text: str) -> str:
    """Remove stray instruction phrases or leaked prompt lines the model might emit."""
    s = text or ""
    # Drop common instruction lines/phrases entirely
    bad_patterns = [
        r"ABSOLUTE\s+OUTPUT\s+SHAPE.*",
        r"MEDICAL\s+CONSISTENCY.*",
        r"ADD\s+A\s+FINAL\s+GLOSSARY.*",
        r"Optionally\s+append\s+key\s+takeaways.*",
        r"Then\s+output\s+EXACTLY.*",
        r"turn\s+inline\s+enumerations.*",
        r"Use\s+<b>.*only.*highlight.*",
        r"Maintain\s+strict\s+1:1.*",
        r"Keep\s+bullets/numbering.*",
        r"Source\s+text:.*",
        r"^---$",
    ]
    for pat in bad_patterns:
        s = re.sub(pat, "", s, flags=re.IGNORECASE | re.MULTILINE)
    # Remove any accidental closing/opening tag remnants if leaked inside content
    s = re.sub(r"\[/?(?:HEAD_EN|HEAD_AR|ENG|ARB|TAKEAWAYS_AR|GLOSSARY_JSON)\]", "", s, flags=re.IGNORECASE)
    # Normalize whitespace
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s


def _extract_dual_segments(raw_text: str) -> List[Tuple[str, str, str, str, List[str]]]:
    """Extract segments with optional per-segment headings.
    Returns list of tuples: (eng, arb, head_en, head_ar, takeaways_ar)
    """
    segments: List[Tuple[str, str, str, str, List[str]]] = []
    # We support optional HEAD_EN/HEAD_AR preceding ENG/ARB
    block_re = re.compile(
        r'(?:\[HEAD_EN\](.*?)\[/HEAD_EN\]\s*)?'
        r'(?:\[HEAD_AR\](.*?)\[/HEAD_AR\]\s*)?'
        r'\[ENG\](.*?)\[/ENG\]\s*\[ARB\](.*?)\[/ARB\]'
        r'(?:\s*\[TAKEAWAYS_AR\](.*?)\[/TAKEAWAYS_AR\])?'
        , flags=re.DOTALL | re.IGNORECASE)
    def _map_heading(en: str, ar: str) -> Tuple[str, str]:
        en_norm = (en or '').strip().lower()
        ar_norm = (ar or '').strip()
        # If Arabic missing, infer from common English headings
        if not ar_norm and en_norm:
            mapping = [
                (r'^\s*types?\s+of\s+studies\b', 'أنواع الدراسات'),
                (r'^\s*study\s+design\b', 'تصميم الدراسة'),
                (r'^\s*advantages\b', 'المزايا'),
                (r'^\s*disadvantages\b', 'العيوب'),
            ]
            for pat, rep in mapping:
                if re.search(pat, en_norm):
                    ar_norm = rep
                    break
        # If English missing but Arabic exists, infer basic English
        if not en_norm and ar_norm:
            back_map = {
                'أنواع الدراسات': 'Types of Studies',
                'تصميم الدراسة': 'Study Design',
                'المزايا': 'Advantages',
                'العيوب': 'Disadvantages',
            }
            en_norm = back_map.get(ar_norm, en_norm)
        return (en if en else en_norm, ar if ar else ar_norm)

    for m in block_re.finditer(raw_text or ''):
        head_en = _clean_ai_artifacts((m.group(1) or '').strip())
        head_ar = _clean_ai_artifacts((m.group(2) or '').strip())
        eng = _clean_ai_artifacts((m.group(3) or '').strip())
        arb = _clean_ai_artifacts((m.group(4) or '').strip())
        head_en, head_ar = _map_heading(head_en, head_ar)
        tks_raw = (m.group(5) or '').strip()
        takeaways = []
        if tks_raw:
            for ln in tks_raw.splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                ln = re.sub(r'^[-•\d\)\.]\s*', '', ln)
                ln = _clean_ai_artifacts(ln)
                if ln:
                    takeaways.append(ln)
        segments.append((eng, arb, head_en, head_ar, takeaways))
    return segments


async def _run_ai_feature(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: dict,
    *,
    title: str,
    session_key: str,
    generator,
    loading_text: str,
    feature_key: str,
) -> None:
    """Helper to execute an AI-powered feature end-to-end."""
    query = update.callback_query
    context_text = preclean_text_for_ai((user['session'].get('last_text') or '').strip())
    if not context_text:
        await query.message.reply_text('⚠️ لا يوجد محتوى لمعالجته. قم بإرسال نص أو ملف أولاً.')
        return

    await query.edit_message_text(loading_text)

    try:
        result_text = await generator(clamp_text(context_text))
    except Exception as exc:
        logger.exception("AI feature generation failed", exc_info=exc)
        await query.edit_message_text("⚠️ حدث خطأ أثناء توليد المحتوى. حاول مرة أخرى لاحقًا.")
        return

    if not result_text or result_text.startswith('⚠️'):
        await query.edit_message_text(result_text or '⚠️ تعذر توليد المحتوى.')
        return

    lines = [ln.rstrip() for ln in result_text.split('\n')]
    if feature_key == 'focus_notes':
        lines = _decorate_focus_lines(lines)
    if feature_key != 'dual_translation':
        await _send_feature_preview(context, user, title, lines)

    pdf_builder = None
    builder_kwargs = {}
    extra_meta = {}
    glossary = None
    if feature_key == 'dual_translation':
        segments = _extract_dual_segments(result_text)
        if segments:
            pdf_builder = build_dual_language_pdf
            # Merge AI-provided glossary (if any) with locally detected terms
            ai_gloss = extract_glossary_json(result_text) or []
            def _seg_eng(seg):
                try:
                    if isinstance(seg, (list, tuple)) and len(seg) >= 1:
                        return str(seg[0] or '')
                    if isinstance(seg, dict):
                        return str(seg.get('eng', '') or '')
                    return str(seg)
                except Exception:
                    return ''
            english_text = "\n".join(_seg_eng(s) for s in segments)
            local_terms = find_terms_in_text(english_text)
            glossary = merge_glossaries(ai_gloss, local_terms)
            # Enrich missing definitions/arabic via AI if needed
            missing_terms = [it['term'] for it in glossary if not it.get('arabic') or not it.get('definition')]
            if missing_terms:
                try:
                    from ai_services import ai_generate_arabic_glossary
                    enriched = await ai_generate_arabic_glossary(missing_terms)
                except Exception:
                    enriched = None
                if enriched:
                    # Index enriched by normalized term
                    def _norm(s: str):
                        import re
                        return re.sub(r"\s+", " ", (s or "").lower()).strip()
                    eidx = {_norm(it['term']): it for it in enriched if it.get('term')}
                    new_gloss = []
                    for it in glossary:
                        key = _norm(it.get('term'))
                        if key in eidx:
                            eg = eidx[key]
                            # Fill blanks only; keep existing values
                            it['arabic'] = it.get('arabic') or eg.get('arabic')
                            it['definition'] = it.get('definition') or eg.get('definition')
                        new_gloss.append(it)
                    glossary = new_gloss
            builder_kwargs = {'segments': segments, 'glossary': glossary, 'layout': 'stacked'}
            extra_meta['segment_count'] = len(segments)
            extra_meta['layout'] = 'dual'

    await _make_pdf_and_prompt_download(
        update,
        context,
        user,
        title,
        lines,
        session_key=session_key,
        pdf_builder=pdf_builder,
        builder_kwargs=builder_kwargs,
        send_direct=(feature_key == 'dual_translation')
    )
    # Optional Telegraph publish for dual translation
    if feature_key == 'dual_translation' and builder_kwargs.get('segments'):
        try:
            telegraph_url = await publish_bilingual_to_telegraph(title, builder_kwargs['segments'], glossary=glossary)
        except Exception as exc:
            telegraph_url = None
            logger.debug("Telegraph publish error: %s", exc)
        if telegraph_url:
            try:
                await context.bot.send_message(chat_id=user['id'], text=f"🔗 نُشرت نسخة ويب على Telegraph:\n{telegraph_url}")
                # store in session
                user.setdefault('session', {})[f'link_{session_key}'] = telegraph_url
                database._update_user_in_db(user['id'], user)
            except Exception:
                pass
    item_id, folder_id = _store_feature_in_library(
        user,
        title,
        lines,
        feature_key=feature_key,
        session_key=session_key,
        extra=extra_meta if extra_meta else None
    )
    if item_id and folder_id:
        folder_name = user['library']['folders'].get(folder_id, {}).get('name', '📂')
        info_text = (
            f"💾 تم حفظ **{title}** تلقائيًا داخل المكتبة الذكية في مجلد {folder_name}.\n"
            "يمكنك الرجوع إليه أو مشاركته في أي وقت." 
        )
        try:
            await context.bot.send_message(chat_id=user['id'], text=info_text, parse_mode=ParseMode.MARKDOWN)
        except Exception as exc:
            logger.debug(f"Failed to notify user about library save: {exc}")
        if feature_key == 'dual_translation':
            detail = (
                "📚 طريقة العرض: العمود الأيسر للإنجليزية كما وردت، والعمود الأيمن للترجمة العربية مع إبراز المصطلحات."\
                "\nيمكنك طباعة الـPDF للمذاكرة الثنائية بسهولة." )
            with suppress(Exception):
                await context.bot.send_message(chat_id=user['id'], text=detail)

async def features_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    user = database.ensure_user(query.from_user.id, query.from_user.full_name)
    context_text = (user['session'].get('last_text') or '').strip()

    explanations = {
        'feature_flashcards': "🃏 بطاقات الفلاش تولّد أسئلة وإجابات ثنائية اللغة جاهزة للمراجعة الخاطفة.",
        'feature_focus_notes': "🎯 ورقة التركيز الفاخرة تجمع أهم النقاط + التحذيرات + أسئلة التحقق في صفحة واحدة.",
        'feature_study_plan': "🧭 خطة مذاكرة أسبوعية موزونة بالمهام اليومية، المراجعة النشطة، والتنبيهات الذكية.",
        'feature_text_to_pdf': "📄 يحوّل نصك إلى PDF فاخر بغلاف، مؤشرات تقدم، وشارات جاهزة للطباعة أو المشاركة.",
        'feature_text_to_image': "🖼️ يصمّم بطاقة دراسة متدرجة الألوان تعرض أبرز النقاط في لقطة واحدة.",
        'feature_summarize_pdf': "⚡ ملخص PDF فوري يلخّص المستند الطويل إلى أقسام واضحة مع إمكانية التنزيل.",
        'feature_download_media': "⬇️ حمّل الصوت أو النص من رابط يوتيوب ثم واصل مع بقية الأدوات الذكية.",
        'feature_translate_dual': "🌐 ترجمة ثنائية فاخرة تعرض الإنجليزية مع الشرح العربي داخل PDF أنيق.",
        'feature_achievements': "🏅 استعرض إنجازاتك الشخصية والخطوات التالية التي تقترحها المنصة.",
        'feature_weekly_report': "📈 تقرير أسبوعي يلخّص نشاطك، الرصيد، ونصائح الاستفادة القصوى.",
        'feature_toggle_spiritual': "🔔 بدّل استقبال الرسائل الروحانية (حديث/آية مع تعليق بسيط) حسب رغبتك.",
    }

    if data in explanations:
        with suppress(Exception):
            await query.message.reply_text(explanations[data])
        if data == 'feature_toggle_spiritual':
            curr = user.setdefault('session', {}).get('spiritual_on', True)
            user['session']['spiritual_on'] = not curr
            database._update_user_in_db(user['id'], user)
            status = '✅ تم التشغيل' if user['session']['spiritual_on'] else '⏹️ تم الإيقاف'
            await query.message.reply_text(f"حالة الإشعارات الروحانية: {status}")
            return

    if data == 'feature_exam_drill':
        await query.message.reply_text(
            '🛑 تدريب الأسئلة متعدد الخيارات تم إيقافه مؤقتًا. جرّب ورقة التركيز أو بطاقات الفلاش بدلًا منه.'
        )
        return

    ai_feature_specs = {
        'feature_flashcards': {
            'title': 'بطاقات فلاش دراسية خارقة',
            'session_key': 'ai_flashcards',
            'generator': ai_generate_flashcards,
            'loading_text': '🃏 جارٍ بناء بطاقات الفلاش الخارقة الخاصة بك...',
            'feature_key': 'flashcards'
        },
        'feature_focus_notes': {
            'title': 'ورقة تركيز سريعة',
            'session_key': 'ai_focus_sheet',
            'generator': ai_generate_focus_notes,
            'loading_text': '🎯 نجمع الآن أقوى النقاط التي تحتاجها قبل الامتحان...',
            'feature_key': 'focus_notes'
        },
        'feature_study_plan': {
            'title': 'خطة مذاكرة أسبوعية',
            'session_key': 'ai_study_plan',
            'generator': ai_generate_study_plan,
            'loading_text': '🧭 نصمم لك خطة أسبوعية ذكية مبنية على محتواك...',
            'feature_key': 'study_plan'
        },
        'feature_translate_dual': {
            'title': 'ترجمة ثنائية منظمة',
            'session_key': 'ai_translate',
            'generator': ai_translate_dual,
            'loading_text': '🌐 جارٍ تجهيز الترجمة الإنجليزية/العربية بكل دقة...',
            'feature_key': 'dual_translation'
        },
    }

    if data in ai_feature_specs:
        await _run_ai_feature(update, context, user, **ai_feature_specs[data])
        return

    if data == 'feature_menu_quick':
        await query.edit_message_text('⚡ اختر أداة فورية:', reply_markup=keyboards.productivity_quick_tools_kb())
        return
    if data == 'feature_menu_ai':
        if not context_text:
            await query.edit_message_text('⚠️ أرسل نصًا أو ملفًا أولًا لاستخدام معامل الذكاء الدراسي.', reply_markup=keyboards.back_home_kb())
        else:
            await query.edit_message_text('🧠 اختر معامل الذكاء الدراسي:', reply_markup=keyboards.productivity_ai_suite_kb())
        return
    if data == 'feature_recent_outputs':
        items = _get_recent_ai_items(user)
        if not items:
            await query.edit_message_text(
                '📦 لا يوجد مخرجات محفوظة بعد. جرّب توليد إحدى الأدوات الذكية أولًا!',
                reply_markup=keyboards.productivity_ai_suite_kb()
            )
            return
        await query.edit_message_text(
            '📦 اختر مخرجًا حديثًا لاستعراضه:',
            reply_markup=keyboards.ai_recent_outputs_kb(items)
        )
        return
    if data.startswith('feature_recent_open_'):
        item_id = data.split('_', 3)[3]
        item = _get_library_item(user, item_id)
        if not item:
            await query.answer('العنصر لم يعد موجودًا.', show_alert=True)
            await query.edit_message_text('⚠️ العنصر غير موجود.', reply_markup=keyboards.productivity_ai_suite_kb())
            return
        session_key = (item.get('extra') or {}).get('session_key')
        has_pdf = bool(session_key and user.get('session', {}).get(f'file_{session_key}', {}).get('pdf'))
        preview_raw = item.get('content', '')[:800]
        if len(item.get('content', '')) > 800:
            preview_raw += '\n...'
        preview = safe_md(preview_raw)
        header = f"📄 **{safe_md(item.get('title', 'مستند'))}**\n\n"
        await query.edit_message_text(
            header + (preview or 'لا يوجد محتوى نصي.'),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.ai_recent_item_actions_kb(item_id, has_pdf)
        )
        return
    if data.startswith('feature_recent_download_'):
        item_id = data.split('_', 3)[3]
        item = _get_library_item(user, item_id)
        session_key = (item or {}).get('extra', {}).get('session_key') if item else None
        if not session_key or not await _send_saved_pdf(context, user, session_key):
            await query.answer('ملف الـPDF غير متوفر.', show_alert=True)
        else:
            await query.answer('📄 تم الإرسال.', show_alert=False)
        return
    if data.startswith('feature_recent_send_'):
        item_id = data.split('_', 3)[3]
        item = _get_library_item(user, item_id)
        if not item:
            await query.answer('العنصر غير موجود.', show_alert=True)
            return
        await _send_item_content(context, user, item)
        await query.answer('📨 تم الإرسال.', show_alert=False)
        return
    if data.startswith('feature_recent_openlib_'):
        item_id = data.split('_', 3)[3]
        item = _get_library_item(user, item_id)
        if not item:
            await query.answer('العنصر غير موجود.', show_alert=True)
            return
        folder_id = _ensure_ai_folder(user)
        folder_name = user['library']['folders'].get(folder_id, {}).get('name', '📂')
        msg = (
            f"📚 للوصول الكامل إلى **{safe_md(item.get('title', 'المستند'))}**:\n"
            f"1. افتح المكتبة من القائمة الرئيسية.\n"
            f"2. افتح مجلد {folder_name}.\n"
            f"3. ستجد المخرج محفوظًا بالاسم نفسه."
        )
        await query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        await query.answer()
        return
    if data == 'feature_menu_growth':
        await query.edit_message_text('🌟 أدوات التحفيز والتقدم:', reply_markup=keyboards.productivity_growth_kb())
        return
    if data == 'productivity_features_menu':
        await query.edit_message_text('⚙️ اختر نوع الميزة:', reply_markup=keyboards.productivity_features_kb())
        return

    if data == 'feature_text_to_pdf':
        if not context_text:
            await query.message.reply_text('⚠️ مفيش نص في السياق. ابعت نص أو PDF الأول.')
            return
        lines = [ln.rstrip() for ln in context_text.split('\n') if ln.strip()]
        await _make_pdf_and_prompt_download(
            update,
            context,
            user,
            'مستند PDF من نصك',
            lines,
            session_key='prod_textpdf',
            pdf_builder=build_text_to_pdf,
            builder_kwargs={'lines': lines},
            send_direct=True,
            show_main_menu=False
        )
        item_id, folder_id = _store_feature_in_library(
            user,
            'مستند PDF من نصك',
            lines,
            feature_key='text_pdf',
            session_key='prod_textpdf'
        )
        folder_hint = ''
        if item_id and folder_id:
            folder_name = user['library']['folders'].get(folder_id, {}).get('name', '📂')
            folder_hint = f"\n📚 محفوظ تلقائيًا داخل مجلد {safe_md(folder_name)} في مكتبتك الذكية."
        success_msg = (
            "📄 **ملف PDF الفاخر جاهز!**\n"
            "كل فقرة صيغت بتصميم أنيق ومقروء."
            f"{folder_hint}\n\n"
            "💡 اختر الخطوة التالية من القائمة الذكية أسفله."
        )
        await context.bot.send_message(
            chat_id=user['id'],
            text=success_msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.feature_success_kb('text_pdf')
        )
        return

    if data == 'feature_text_to_image':
        if not context_text:
            await query.message.reply_text('⚠️ مفيش نص في السياق. ابعت نص أو PDF الأول.')
            return
        img_bio = _text_to_image(context_text.split('\n'))
        await query.message.reply_photo(photo=img_bio, caption='🖼️ تم توليد صورة من النص.')
        followup_msg = (
            "🖼️ **بطاقتك المرئية جاهزة!**\n"
            "استعمل الأزرار للإنتاج السريع لباقي الأدوات."
        )
        await context.bot.send_message(
            chat_id=user['id'],
            text=followup_msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.feature_success_kb('text_image')
        )
        return

    if data == 'feature_summarize_pdf':
        if not context_text:
            await query.message.reply_text('⚠️ مفيش نص/سياق PDF. ابعت PDF أو نص الأول.')
            return
        await query.edit_message_text('⏳ جاري التلخيص الشامل...')
        summary = await ai_summarize_bilingual(clamp_text(context_text))
        if not summary or summary.startswith('⚠️'):
            await query.edit_message_text(summary or '⚠️ فشل التلخيص.')
            return
        lines = [ln for ln in summary.split('\n') if ln.strip()]
        await _make_pdf_and_prompt_download(update, context, user, 'ملخص PDF', lines, session_key='prod_sum')
        item_id, folder_id = _store_feature_in_library(user, 'ملخص PDF', lines, feature_key='pdf_summary', session_key='prod_sum')
        if item_id and folder_id:
            folder_name = user['library']['folders'].get(folder_id, {}).get('name', '📂')
            note = f"💾 تم حفظ الملخص في المكتبة ضمن {folder_name}."
            await query.message.reply_text(note)
        return

    if data == 'feature_make_pptx':
        await query.message.reply_text('📽️ جاري تجهيز مولد الشرائح. ترقّب تحديث قادم يتيح لك تحميل PPTX مرتب تلقائيًا!')
        return

    if data == 'feature_download_media':
        context.user_data['mode'] = 'download_media_wait_url'
        await query.edit_message_text('🔗 ابعت رابط يوتيوب (https://...) لتحويله إلى نص/صوت.', reply_markup=keyboards.back_home_kb())
        return

    if data == 'feature_ocr':
        await query.edit_message_text('📸 أرسل الآن صورة أو سكنر وسأحوّلها فورًا إلى نص قابل للتحرير ثم أعد استخدامه مع أي أداة.', reply_markup=keyboards.back_home_kb())
        return

    if data == 'feature_lucky_draw':
        await query.message.reply_text('🎲 سيتم إعلان الفائز في السحب من خلال القناة الرسمية قريبًا. استمر في استخدام البوت لزيادة فرصتك!')
        return

    if data == 'feature_achievements':
        files_done = user.get('files_processed', 0)
        milestones = [
            (1, '🚀 أول خطوة تمت!'),
            (5, '🎯 خمسة ملفات منجزة'),
            (10, '🏅 عشرة ملفات كاملة'),
            (25, '🥈 خمسة وعشرون إنجازًا'),
            (50, '🥇 خمسون ملفًا — بطل حقيقي!'),
            (100, '💎 مائة ملف — أسطورة مذاكرة!'),
        ]
        earned = [label for threshold, label in milestones if files_done >= threshold]
        next_goal = next((threshold for threshold, _ in milestones if threshold > files_done), None)

        text = f"🏆 **لوحة إنجازاتك يا {safe_md(user['name'])}**\n\n"
        if earned:
            text += "تم الحصول على:\n" + "\n".join([f"- {item}" for item in earned]) + "\n\n"
        else:
            text += "- لم تبدأ بعد! أرسل أول ملفك اليوم وابدأ سلسلة إنجازاتك.\n\n"
        if next_goal:
            remaining = next_goal - files_done
            text += f"🎯 الهدف القادم عند {next_goal} ملف (متبقي {remaining})."
        else:
            text += "💫 لقد كسرت كل الأهداف الحالية!"
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return

    if data in ('feature_leaderboard', 'feature_top10'):
        try:
            users = database.get_all_users_detailed()
        except Exception as exc:
            logger.error(f"Failed to fetch leaderboard: {exc}")
            await query.message.reply_text('⚠️ تعذر تحميل لوحة الصدارة الآن.')
            return
        ranked = sorted(users, key=lambda u: u.get('files_processed', 0), reverse=True)[:10]
        if not ranked:
            await query.message.reply_text('لا يوجد نشاط كافٍ لعرض لوحة الصدارة حتى الآن.')
            return
        lines = [f"{idx+1}. {safe_md(u['name'])} — {u.get('files_processed', 0)} ملف" for idx, u in enumerate(ranked)]
        board = "🏅 **الأكثر تفاعلاً (حسب عدد الملفات)**\n\n" + "\n".join(lines)
        await query.message.reply_text(board, parse_mode=ParseMode.MARKDOWN)
        return

    if data == 'feature_badge':
        files_done = user.get('files_processed', 0)
        if files_done >= 50:
            badge = '💎 أسطورة المذاكرة'
        elif files_done >= 25:
            badge = '🥇 بطل مستمر'
        elif files_done >= 10:
            badge = '🥈 متفوق نشيط'
        elif files_done >= 3:
            badge = '🥉 منطلق بثقة'
        else:
            badge = '⭐ مبتدئ واعد'
        await query.message.reply_text(f"شارتك الحالية: {badge} ({files_done} ملف منجز)")
        return

    if data == 'feature_night_mode':
        user['session']['night_mode'] = not user['session'].get('night_mode', False)
        database._update_user_in_db(user['id'], user)
        msg = '🌙 تم تفعيل الوضع الليلي!' if user['session']['night_mode'] else '☀️ تم إيقاف الوضع الليلي.'
        await query.message.reply_text(msg)
        return

    if data == 'feature_weekly_report':
        tokens = user.get('tokens', 0)
        files_done = user.get('files_processed', 0)
        activity = '📄 يوجد محتوى جاهز للاستكمال.' if context_text else '📭 لا يوجد محتوى محفوظ حاليًا.'
        library_items = len(user.get('library', {}).get('items', {}))
        recent_ai = (user.get('session', {}).get('ai_history', []) or [])[-1:] or []
        last_ai_line = ''
        if recent_ai:
            last_ai = recent_ai[-1]
            last_ai_line = f"- آخر مخرج ذكي: {safe_md(last_ai.get('title', 'بدون عنوان'))}\n"
        report = (
            f"📈 **تقريرك الأسبوعي**\n\n"
            f"- الملفات المعالجة إجمالًا: {files_done}\n"
            f"- الرصيد الحالي من التوكنز: {tokens:,}\n"
            f"- العناصر المحفوظة في المكتبة: {library_items}\n"
            f"{last_ai_line}"
            f"- حالة الجلسة الحالية: {safe_md(activity)}"
        )
        await query.message.reply_text(report, parse_mode=ParseMode.MARKDOWN)
        return

    if data == 'feature_weekly_goal':
        goals = [
            "🎯 ذاكر 3 ساعات مركزة مع استخدام تقنية البومودورو.",
            "📘 أنجز ملخصين جديدين اليوم وراجع واحدًا قديمًا.",
            "🧠 جرّب اختبارًا سريعًا بعد كل جلسة مذاكرة للتثبيت.",
            "📅 وزّع المذاكرة على 4 أيام مع مراجعة خفيفة في اليوم الخامس."
        ]
        await query.message.reply_text(random.choice(goals))
        return

    if data == 'feature_monthly_challenge':
        challenge = (
            "📅 تحدي الشهر:\n"
            "- جهّز 5 ملخصات احترافية.\n"
            "- حل 3 اختبارات Drill.\n"
            "- شارك إنجازك مع زملائك لتحفّزهم!"
        )
        await query.message.reply_text(challenge)
        return

    if data == 'feature_quote':
        quotes = [
            "💡 العلم نور، والذكاء الاصطناعي هو المصباح الجديد.",
            "🚀 المستحيل مجرد رأي، استمر بالخطوات الصغيرة.",
            "📚 المذاكرة اليومية تبني صرح النجاح.",
            "🧠 درّب عقلك كما تدرب عضلاتك، التكرار قوة."
        ]
        await query.message.reply_text(random.choice(quotes))
        return

    if data == 'feature_download_media_done':
        # legacy placeholder (if used elsewhere)
        return

    if data == 'admin_panel':
        await admin_panel(update, context)
        return
    if data == 'report_issue':
        await report_issue(update, context)
        return
    if data == 'contact_admin':
        await contact_admin(update, context)
        return
    if data == 'start_home':
        await start_cmd(update, context)
        return

    await query.message.reply_text('🚧 هذه الميزة قيد التطوير حالياً.')

async def download_pdf_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a previously prepared PDF stored in the user's session (base64)."""
    query = update.callback_query
    await query.answer()
    user = database.ensure_user(query.from_user.id, query.from_user.full_name)
    data = query.data  # e.g., download_pdf_prod_sum
    try:
        key = data.replace('download_pdf_', '', 1)
        entry = user.get('session', {}).get(f'file_{key}', {})
        pdf = entry.get('pdf') if isinstance(entry, dict) else None
        if not pdf or not pdf.get('data'):
            await query.edit_message_text("⚠️ لم أجد الملف المطلوب أو انتهت صلاحيته.")
            return
        import base64, io
        raw = base64.b64decode(pdf['data'])
        bio = io.BytesIO(raw)
        bio.name = pdf.get('fname', 'document.pdf')
        await context.bot.send_document(
            chat_id=user['id'],
            document=bio,
            filename=bio.name,
            caption="✅ تم التحميل."
        )
    except Exception as e:
        logger.exception("Failed to send stored PDF")
        await query.edit_message_text("⚠️ حدث خطأ أثناء تجهيز الملف.")

# ============================
# ==== New Menu Functions ====
# ============================

async def report_issue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data['mode'] = 'report_wait_text'
    await q.edit_message_text("📝 اكتب وصف المشكلة وسيتم إرساله للإدارة.", reply_markup=keyboards.back_home_kb())

async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data['mode'] = 'contact_wait_text'
    await q.edit_message_text("✉️ اكتب رسالتك وسيتم توصيلها للإدارة.", reply_markup=keyboards.back_home_kb())

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if update.effective_user.id not in _admin_ids():
        await q.edit_message_text("❌ هذا القسم مخصص للإدارة فقط.", reply_markup=keyboards.back_home_kb())
        return
    await q.edit_message_text("🛡️ لوحة الأدمن:", reply_markup=keyboards.admin_panel_kb())

from telegram.ext import ContextTypes
from telegram import Update

async def route_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes text input depending on context.user_data['mode'] set by buttons."""
    text = update.effective_message.text or ""
    mode = context.user_data.get('mode')

    # Admin broadcast text
    if mode == 'broadcast_waiting_text':
        # TODO: Replace with real DB users iteration
        try:
            users = [u['id'] for u in database.get_all_users_detailed()]
        except Exception:
            users = []
        sent = 0
        for uid in users:
            try:
                await context.bot.send_message(chat_id=uid, text=text)
                sent += 1
            except Exception:
                pass
        await update.effective_message.reply_text(f"تم إرسال البث إلى {sent} مستخدم.")
        context.user_data['mode'] = None
        return

    # Admin reply flow: first expects user_id, then the reply text
    elif mode == 'admin_reply_wait_user_id':
        context.user_data['reply_user_id'] = text.strip()
        context.user_data['mode'] = 'admin_reply_wait_text'
        await update.effective_message.reply_text("اكتب نص الرد:")
        return
    elif mode == 'admin_reply_wait_text':
        try:
            uid = int(context.user_data.get('reply_user_id', '0') or '0')
        except Exception:
            uid = 0
        if uid:
            try:
                await context.bot.send_message(chat_id=uid, text=f"رد الإدارة:\n{text}")
                await update.effective_message.reply_text("تم إرسال الرد.")
            except Exception as e:
                await update.effective_message.reply_text(f"تعذّر الإرسال: {e}")
        context.user_data['mode'] = None
        context.user_data.pop('reply_user_id', None)
        return

    # User flows: report / contact
    elif mode == 'report_wait_text':
        # TODO: سجل البلاغ في قاعدة البيانات وأرسله للأدمن
        try:
            admin_ids = getattr(config, 'ADMIN_IDS', [])
            for aid in admin_ids:
                try:
                    await context.bot.send_message(chat_id=aid, text=f"بلاغ جديد من {update.effective_user.id}:\n{text}")
                except Exception:
                    pass
        except Exception:
            pass
        await update.effective_message.reply_text("تم استلام البلاغ وسيتم مراجعته.")
        context.user_data['mode'] = None
        return
    elif mode == 'contact_wait_text':
        # TODO: أرسل الرسالة إلى الأدمن
        try:
            admin_ids = getattr(config, 'ADMIN_IDS', [])
            for aid in admin_ids:
                try:
                    await context.bot.send_message(chat_id=aid, text=f"رسالة للمشرف من {update.effective_user.id}:\n{text}")
                except Exception:
                    pass
        except Exception:
            pass
        await update.effective_message.reply_text("تم إرسال رسالتك للإدارة.")
        context.user_data['mode'] = None
        return

    elif mode == 'download_media_wait_url':
        url = (text or '').strip()
        await update.effective_message.reply_text('⏳ جاري تنزيل الصوت وتفريغه...')
        result = await extract_audio_from_youtube(url)
        context.user_data['mode'] = None
        if not result or result.startswith('⚠️'):
            await update.effective_message.reply_text(result or '⚠️ لم أتمكن من المعالجة.')
            return
        # حفظ التفريغ كنص سياقي دون عرضه بالكامل
        user = database.ensure_user(update.effective_user.id, update.effective_user.full_name)
        user['session']['last_text'] = result
        database._update_user_in_db(user['id'], user)
        await update.effective_message.reply_text(
            '✅ تم تفريغ الفيديو إلى نص.\n+\nاختر الآن: ترجمة ثنائية، ملخص، شرح، خريطة ذهنية، أو أسئلة MCQ.',
            reply_markup=keyboards.main_menu_kb(user)
        )
        return

    # Default
    else:
        await update.effective_message.reply_text("تم استلام رسالتك. استخدم الأزرار للتنقل.")
        # في نهاية ملف handlers/common_handlers.py

async def contact_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the process of sending a message to the admin."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "✍️ اكتب رسالتك الآن وسيتم إرسالها مباشرةً إلى إدارة البوت."
    )
    return config.WAITING_ADMIN_CONTACT
async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Forwards the user's message to all admins and ends the contact process."""
    user_message = update.message.text
    user = update.effective_user
    
    # التأكد من أن الرسالة ليست فارغة
    if not user_message or not user_message.strip():
        await update.message.reply_text("⚠️ لم تكتب أي رسالة. يرجى المحاولة مرة أخرى.")
        # نرجع المستخدم للقائمة الرئيسية
        await start_cmd(update, context)
        return ConversationHandler.END

    forward_text = (
        f"📩 **رسالة جديدة من مستخدم** 📩\n\n"
        f"**من:** {user.full_name}\n"
        f"**يوزر:** @{user.username or 'N/A'}\n"
        f"**ID:** `{user.id}`\n\n"
        f"**الرسالة:**\n---\n{user_message}"
    )
    
    success_count = 0
    # إرسال الرسالة لكل الأدمن
    for admin_id in config.ADMIN_USER_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=forward_text, parse_mode=ParseMode.MARKDOWN)
            success_count += 1
            logger.info(f"Successfully forwarded message from {user.id} to admin {admin_id}")
        except Exception as e:
            logger.error(f"Failed to forward message to admin {admin_id}: {e}")

    # إرسال تأكيد للمستخدم
    if success_count > 0:
        await update.message.reply_text("✅ تم إرسال رسالتك بنجاح إلى الإدارة. شكراً لتواصلك معنا!")
    else:
        await update.message.reply_text(
            f"⚠️ عذرًا، حدث خطأ أثناء محاولة إيصال رسالتك. يرجى التواصل مباشرة مع الدعم الفني: {config.ADMIN_SUPPORT_USERNAME}"
        )
            
    # الرجوع للقائمة الرئيسية وإنهاء المحادثة
    await start_cmd(update, context)
    return ConversationHandler.END
async def report_bug_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the bug reporting process."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📝 يرجى وصف المشكلة التي واجهتها بالتفصيل. سيتم إرسال بلاغك للإدارة لمراجعته."
    )
    return config.WAITING_BUG_REPORT
async def forward_bug_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Forwards the user's bug report to all admins."""
    report_message = update.message.text
    user = update.effective_user

    # التأكد من أن البلاغ ليس فارغًا
    if not report_message or not report_message.strip():
        await update.message.reply_text("⚠️ لم تكتب أي بلاغ. يرجى المحاولة مرة أخرى.")
        # نرجع المستخدم للقائمة الرئيسية
        await start_cmd(update, context)
        return ConversationHandler.END
    
    forward_text = (
        f"🐞 **بلاغ جديد بمشكلة** 🐞\n\n"
        f"**من:** {user.full_name} (`{user.id}`)\n"
        f"**يوزر:** @{user.username or 'N/A'}\n\n"
        f"**نص البلاغ:**\n---\n{report_message}"
    )
    
    success_count = 0
    for admin_id in config.ADMIN_USER_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=forward_text, parse_mode=ParseMode.MARKDOWN)
            success_count += 1
            logger.info(f"Successfully forwarded bug report from {user.id} to admin {admin_id}")
        except Exception as e:
            logger.error(f"Failed to forward bug report to admin {admin_id}: {e}")
            
    # إرسال تأكيد للمستخدم
    if success_count > 0:
        await update.message.reply_text("✅ شكراً لك! تم استلام بلاغك وسيتم مراجعته في أقرب وقت.")
    else:
        await update.message.reply_text(
            f"⚠️ عذرًا، حدث خطأ أثناء محاولة إرسال بلاغك. يرجى التواصل مباشرة مع الدعم الفني: {config.ADMIN_SUPPORT_USERNAME}"
        )
            
    # الرجوع للقائمة الرئيسية وإنهاء المحادثة
    await start_cmd(update, context)
    return ConversationHandler.END
