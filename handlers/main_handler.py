# handlers/main_handler.py
import logging
from contextlib import suppress
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.error import BadRequest
from PIL import Image
import io
import base64
import uuid
from PyPDF2 import PdfReader
try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

import database
import keyboards
import config
from utils import safe_md
from ai_services import (
    ai_summarize_bilingual, ai_summarize_en,
    ai_explain_bilingual, ai_explain_en,
    ai_mindmap, ai_extract_from_image, ai_call_with_fallback, clamp_text
)
from file_generator import (
    build_pdf_from_lines_weasy as build_stylish_pdf,
    build_mindmap_text_pdf,
    build_study_pro_pdf
)

logger = logging.getLogger(__name__)

# --- File/Text Ingestion ---

def _pdf_to_text(file_bytes: bytes) -> str:
    # Prefer PyMuPDF for better layout handling, fallback to PyPDF2
    if fitz is not None:
        try:
            doc = fitz.open(stream=file_bytes, filetype='pdf')
            parts = []
            for page in doc:
                parts.append(page.get_text("text"))
            text = "\n".join(parts)
            return text[:config.MAX_TEXT_CHARS]
        except Exception as e:
            logger.warning(f"PyMuPDF failed, falling back to PyPDF2: {e}")
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        text = "\n".join(page.extract_text() or "" for page in reader.pages if page.extract_text())
        return text[:config.MAX_TEXT_CHARS]
    except Exception as e:
        logger.error(f"PDF parse error: {e}")
        return ""

async def _process_uploaded_content(update: Update, context: ContextTypes.DEFAULT_TYPE, text_content: str, source_name: str) -> int:
    user = context.user_data.get('user')
    if not user:
         user = database.ensure_user(update.effective_user.id, update.effective_user.full_name)
         context.user_data['user'] = user

    if not text_content or not text_content.strip():
        await update.effective_message.reply_text("⚠️ لم أتمكن من استخراج أي نص صالح من الملف.")
        return config.WAITING_INPUT

    user["session"]["last_text"] = text_content
    database._update_user_in_db(user['id'], user)
    
    await update.effective_message.reply_text(
        f"✅ تم استلام ومعالجة **{safe_md(source_name)}**.\n\nاختر الإجراء المطلوب:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.main_menu_kb(user)
    )
    # --- ✨✨ هذا هو التعديل الأهم: نضمن أن البوت ينتقل للحالة الصحيحة ✨✨ ---
    return config.MAIN_MENU

async def handle_document_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['user'] = database.ensure_user(update.effective_user.id, update.effective_user.full_name)
    doc = update.effective_message.document
    thinking_msg = await update.effective_message.reply_text("⏳ جاري معالجة الملف...")
    try:
        f = await doc.get_file()
        b = await f.download_as_bytearray()
        text = ""
        filename = doc.file_name or "file"
        if doc.mime_type.endswith("/pdf") or filename.lower().endswith(".pdf"):
            text = _pdf_to_text(b)
        elif "text" in doc.mime_type:
            text = b.decode("utf-8", errors="ignore")[:config.MAX_TEXT_CHARS]
        else:
            await thinking_msg.edit_text("⚠️ صيغة الملف غير مدعومة.")
            return config.WAITING_INPUT
        await thinking_msg.delete()
        return await _process_uploaded_content(update, context, text, filename)
    except Exception as e:
        logger.error(f"File handling error: {e}")
        await thinking_msg.edit_text("⚠️ حدث خطأ أثناء معالجة الملف.")
        return config.WAITING_INPUT

async def handle_photo_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['user'] = database.ensure_user(update.effective_user.id, update.effective_user.full_name)
    thinking_msg = await update.effective_message.reply_text("🖼️ جاري تحليل الصورة...")
    try:
        photo = update.effective_message.photo[-1]
        f = await photo.get_file()
        b = await f.download_as_bytearray()
        img = Image.open(io.BytesIO(b)).convert("RGB")
        extracted = await ai_extract_from_image(img)
        if extracted.startswith("⚠️"):
            await thinking_msg.edit_text(extracted)
            return config.WAITING_INPUT
        await thinking_msg.delete()
        return await _process_uploaded_content(update, context, extracted, "Image")
    except Exception as e:
        logger.error(f"Photo handling error: {e}")
        await thinking_msg.edit_text("⚠️ حدث خطأ أثناء معالجة الصورة.")
        return config.WAITING_INPUT

async def handle_text_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['user'] = database.ensure_user(update.effective_user.id, update.effective_user.full_name)
    txt = update.effective_message.text
    return await _process_uploaded_content(update, context, txt, "Text Snippet")

# --- ✨ [دالة جديدة] راوتر القائمة الرئيسية ---
async def main_menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يوجه أزرار القائمة الرئيسية مثل تلخيص، شرح، وخريطة ذهنية."""
    query = update.callback_query
    await query.answer()
    user = database.ensure_user(query.from_user.id, query.from_user.full_name)
    action = query.data

    if not user["session"].get("last_text"):
        await query.edit_message_text(
            "⚠️ لا يوجد محتوى للعمل عليه. يرجى إرسال نص أو ملف أولاً.",
            reply_markup=keyboards.back_to_menu_kb()
        )
        return config.MAIN_MENU

    if action == "mindmap":
        with suppress(Exception):
            await query.message.reply_text("🧠 سنحوّل المحتوى إلى خريطة ذهنية منظمة على هيئة PDF لسهولة المراجعة.")
        return await do_mindmap(update, context)

    if action in ["summarize", "explain"]:
        # حفظ الإجراء المطلوب ثم عرض قائمة اختيار الأسلوب
        context.user_data['pending_action'] = action
        intro = (
            "📝 سيحوّل النص إلى ملخص دراسي منظم (إنجليزي أو ثنائي)."
            if action == "summarize"
            else "💡 سيجهز لك شرحًا متعمقًا منظمًا (إنجليزي أو ثنائي) مع أمثلة، سلاسل سبب→نتيجة، وتدريب ذاتي."
        )
        await query.edit_message_text(
            intro + "\n\nاختر الأسلوب المفضل:",
            reply_markup=keyboards.language_style_kb()
        )
        return config.MAIN_MENU

    return config.MAIN_MENU


# --- Style Selection Handler ---
async def style_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    user = database.ensure_user(query.from_user.id, query.from_user.full_name)
    context_text = user["session"].get("last_text")
    action = context.user_data.pop('pending_action', None)
    style = query.data

    if not action or not context_text:
        await query.edit_message_text("⚠️ حدث خطأ. يرجى البدء من جديد.", reply_markup=keyboards.back_to_menu_kb())
        return config.MAIN_MENU

    action_map = {
        ('summarize', 'style_en'): (ai_summarize_en, "English Summary", 'en'),
        ('summarize', 'style_bilingual'): (ai_summarize_bilingual, "ملخص ثنائي اللغة", 'ar'),
        ('explain', 'style_en'): (ai_explain_en, "English Explanation", 'en'),
        ('explain', 'style_bilingual'): (ai_explain_bilingual, "شرح ثنائي اللغة", 'ar'),
    }
    
    ai_func, title, lang = action_map.get((action, style), (None, None, None))

    if not ai_func:
        return config.MAIN_MENU

    # Store for next step (template selection)
    context.user_data['pending_action'] = action
    context.user_data['pending_style'] = style
    context.user_data['pending_ai_func'] = ai_func
    context.user_data['pending_lang'] = lang
    try:
        template_prompt = "اختر قالب ملف الملخص (PDF):" if action == "summarize" else "اختر قالب ملف الشرح (PDF):"
        await query.edit_message_text(template_prompt, reply_markup=keyboards.summary_template_kb())
    except BadRequest as exc:
        if "Message is not modified" not in str(exc):
            raise
        # message already shows the same template prompt; ignore
    return config.MAIN_MENU

import re

def _explode_inline_bullets_local(s: str) -> str:
    s = s or ''
    s = re.sub(r"\s-\s(?=[^\n]*-\s)", "\n- ", s)
    s = re.sub(r"([\.!?،؛])\s-\s+", r"\1\n- ", s)
    return s

def _normalize_summary_text_local(text: str) -> str:
    t = (text or '')
    # Remove Executive Snapshot
    t = re.sub(r"<h2>\s*Executive Snapshot\s*</h2>.*?(?=<h2>|\Z)", "", t, flags=re.DOTALL | re.IGNORECASE)
    t = re.sub(r"(?:^|\n)\s*Executive Snapshot\s*\n.*?(?=(?:\n\s*<h2>)|\Z)", "\n", t, flags=re.DOTALL | re.IGNORECASE)
    # Collapse Contents
    def repl_contents(m):
        body = m.group('body')
        items = []
        for ln in body.splitlines():
            tln = ln.strip(' -•').strip()
            if not tln:
                continue
            if tln.lower().startswith('executive snapshot'):
                continue
            if tln.startswith('<h2>'):
                break
            items.append(tln)
        if not items:
            return ''
        return ' · '.join(f"{i+1}) {it}" for i, it in enumerate(items)) + "\n"
    pat = re.compile(r"(?P<hdr>^(?:Contents|Document Contents|محتويات المستند|محتويات)\s*$)\n(?P<body>(?:.(?!^<h2>))*?)", re.MULTILINE | re.DOTALL | re.IGNORECASE)
    t = pat.sub(repl_contents, t)
    t = t.replace('└─', '').replace('├─', '').replace('│', '')
    # Normalize headings wording
    t = t.replace('Concepts & Definitions', 'Definitions')
    t = t.replace('المفاهيم والتعاريف', 'التعريفات')
    # Remove blockquote wrappers
    t = t.replace('<blockquote>', '').replace('</blockquote>', '')
    t = _explode_inline_bullets_local(t)
    return t

async def template_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    tpl = query.data
    user = database.ensure_user(query.from_user.id, query.from_user.full_name)
    context_text = user["session"].get("last_text")

    ai_func = context.user_data.pop('pending_ai_func', None)
    style = context.user_data.pop('pending_style', None)
    lang = context.user_data.pop('pending_lang', 'ar')
    action = context.user_data.pop('pending_action', 'summarize')
    is_explain = action == 'explain'

    if not ai_func or not context_text:
        fallback_msg = "⚠️ حدث خطأ. يرجى البدء من جديد." if not is_explain else "⚠️ حدث خطأ. حاول اختيار الشرح من جديد."
        await query.edit_message_text(fallback_msg)
        return config.MAIN_MENU

    progress_text = "⏳ جاري تجهيز الشرح المتعمق…" if is_explain else "⏳ جاري إنشاء الملخص…"
    await query.edit_message_text(progress_text)
    try:
        long_text = clamp_text(context_text)
        result_text = await ai_func(long_text)
        if result_text.startswith('⚠️'):
            await query.edit_message_text(result_text)
            return config.MAIN_MENU
        if tpl == 'tpl_pdf2':
            from file_generator import build_summary_pdf_v2
            if is_explain:
                lines = result_text.split('\n')
                await _prepare_and_send_pdf(
                    update,
                    context,
                    user,
                    f"{action}_{style}_pdf2",
                    "شرح متعمق (قالب Ultra)",
                    lines,
                    is_mindmap=False,
                    lang=lang,
                    custom_pdf_builder=build_summary_pdf_v2,
                )
            else:
                norm = _normalize_summary_text_local(result_text)
                lines = norm.split('\n')
                await _prepare_and_send_pdf(
                    update,
                    context,
                    user,
                    f"{action}_{style}_pdf2",
                    "ملخص منظم (قالب Ultra)",
                    lines,
                    is_mindmap=False,
                    lang=lang,
                    custom_pdf_builder=build_summary_pdf_v2,
                )
        else:
            lines = result_text.split('\n')
            display_title = "شرح متعمق (قالب كلاسيكي)" if is_explain else "ملخص منظم (قالب كلاسيكي)"
            await _prepare_and_send_pdf(
                update,
                context,
                user,
                f"{action}_{style}_pdf1",
                display_title,
                lines,
                is_mindmap=False,
                lang=lang,
            )
    except Exception:
        logger.exception("Error in template_selection_handler")
        error_text = "⚠️ حدث خطأ أثناء إنشاء الشرح." if is_explain else "⚠️ حدث خطأ أثناء إنشاء الملخص."
        await query.edit_message_text(error_text)
    return config.MAIN_MENU

async def do_mindmap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = database.ensure_user(query.from_user.id, query.from_user.full_name)
    context_text = clamp_text(user["session"]["last_text"])
    
    await query.edit_message_text("🧠 جاري رسم خريطتك الذهنية التفصيلية...")
    
    try:
        mindmap_text = await ai_mindmap(context_text)
        if not mindmap_text or mindmap_text.startswith("⚠️"):
            await query.edit_message_text(mindmap_text or "⚠️ لم أتمكن من استخلاص هيكل للخريطة.")
            return config.MAIN_MENU
        
        lines = mindmap_text.split('\n')
        root_title = lines[0].strip() if lines else "Mind Map"
        await _prepare_and_send_pdf(update, context, user, "mindmap", root_title, lines, is_mindmap=True)
    except Exception as e:
        logger.exception("Error in do_mindmap")
        await query.edit_message_text("⚠️ حدث خطأ فني.")
    return config.MAIN_MENU

# --- ✨✨✨✨ التعديل الرئيسي هنا ✨✨✨✨ ---
async def _prepare_and_send_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE, user: dict, session_key: str, title: str, content: list, is_mindmap: bool = False, lang: str = 'ar', custom_pdf_builder=None, custom_builder_kwargs: dict | None = None):
    """
    الدالة المعدلة التي ترسل الملف في رسالة، ثم القائمة الرئيسية في رسالة منفصلة.
    """
    query = update.callback_query
    bot_username = (await context.bot.get_me()).username
    
    # 1. توليد ملف الـ PDF في الذاكرة
    if is_mindmap:
        pdf_bytes, pdf_fname = build_mindmap_text_pdf(title, bot_username, "\n".join(content))
    else:
        if custom_pdf_builder is not None:
            kwargs = custom_builder_kwargs or {}
            pdf_bytes, pdf_fname = custom_pdf_builder(title, bot_username, content, **kwargs)
        else:
            # Use Study-Pro template if content contains section headings for better navigation
            joined = "\n".join(content)
            if '<h2>' in joined.lower() or '<H2>' in joined:
                pdf_bytes, pdf_fname = build_study_pro_pdf(title, bot_username, content)
            else:
                pdf_bytes, pdf_fname = build_stylish_pdf(title, bot_username, content, lang=lang)

    if not is_mindmap and session_key.startswith('explain'):
        new_name = f"شرح_{uuid.uuid4().hex[:8]}.pdf"
        pdf_bytes.name = new_name
        pdf_fname = new_name

    # 2. حذف رسالة "جاري الإنشاء..." لتنظيف الشات
    try:
        await query.message.delete()
    except Exception as e:
        logger.warning(f"Could not delete message before sending PDF: {e}")

    # 3. إرسال ملف الـ PDF للمستخدم (بدون أي أزرار)
    await context.bot.send_document(
        chat_id=user['id'],
        document=pdf_bytes,
        filename=pdf_fname,
        caption=f"✅ تفضل، ملفك '{title}' جاهز!"
    )

    # 4. إرسال رسالة جديدة منفصلة تحتوي على القائمة الرئيسية
    await context.bot.send_message(
        chat_id=user['id'],
        text="اختر الإجراء التالي من القائمة الرئيسية:",
        reply_markup=keyboards.main_menu_kb(user)
    )
# --- ✨✨✨✨ نهاية التعديل الرئيسي ✨✨✨✨ ---


async def do_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات المستخدم."""
    query = update.callback_query
    await query.answer()
    
    user = database.ensure_user(query.from_user.id, query.from_user.full_name)
    
    stats_text = (
        f"📊 **إحصائياتك يا {safe_md(user['name'])}**\n\n"
        f"- 📂 عدد الملفات التي تمت معالجتها: **{user.get('files_processed', 0)}**\n"
        f"- 🎟️ رصيد التوكينز المتبقي: **{user.get('tokens', 0):,}**\n"
        f"- 📦 الحد الأقصى للملفات المجانية: **{user.get('subscription_limit', config.FREE_TIER_FILE_LIMIT)}**\n\n"
        "استمر في التعلم والإنجاز! ✨"
    )
    
    await query.edit_message_text(
        stats_text,
        reply_markup=keyboards.back_to_menu_kb(),
        parse_mode=ParseMode.MARKDOWN
    )

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة باقات الاشتراك."""
    query = update.callback_query
    await query.answer()
    
    text = "⭐ اختر باقة الاشتراك المناسبة لك لفتح إمكانيات غير محدودة:\n\n"
    text += "كل باقة تمنحك رصيد توكنز أكبر وتزيد من حد معالجة الملفات الشهرية."
    
    await query.edit_message_text(text, reply_markup=keyboards.subscriptions_menu_kb())
    return config.MAIN_MENU

# --- ✨ [دوال جديدة] لمعالجة تدفق الاشتراك ---
async def handle_package_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعالج اختيار المستخدم لباقة اشتراك معينة."""
    query = update.callback_query
    await query.answer()
    
    package_key = query.data.split("_")[-1]
    package = config.SUBSCRIPTION_PACKAGES.get(package_key)

    if not package:
        await query.edit_message_text("❌ الباقة المحددة غير صالحة.", reply_markup=keyboards.back_to_menu_kb())
        return config.MAIN_MENU

    instructions = (
        f"💎 لتفعيل **{package['name']}**:\n\n"
        f"1. قم بتحويل مبلغ **{package['price']} جنيه مصري** إلى الرقم التالي عبر فودافون كاش:\n"
        f"   📞 `{config.VODAFONE_CASH_NUMBER}`\n\n"
        f"2. **هام جدًا:** خذ لقطة شاشة (Screenshot) لإيصال التحويل.\n\n"
        f"3. اضغط على زر **'✅ لقد قمت بالتحويل'** بالأسفل وأرسل لقطة الشاشة للإدارة لمراجعة وتفعيل اشتراكك فورًا."
    )
    
    await query.edit_message_text(
        instructions,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.payment_instructions_kb(package_key)
    )
    return config.MAIN_MENU

async def handle_payment_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعالج ضغط المستخدم على زر 'لقد قمت بالتحويل' ويخطر الإدارة."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    
    package_key = query.data.split("_")[-1]
    package = config.SUBSCRIPTION_PACKAGES.get(package_key)

    if not package:
        await query.edit_message_text("❌ حدث خطأ، الباقة غير معروفة.", reply_markup=keyboards.back_to_menu_kb())
        return config.MAIN_MENU
        
    admin_notification = (
        f"🔔 **طلب تفعيل اشتراك جديد** 🔔\n\n"
        f"**المستخدم:** {user.full_name}\n"
        f"**اليوزر:** @{user.username}\n"
        f"**ID:** `{user.id}`\n"
        f"**الباقة المطلوبة:** {package['name']}\n"
        f"**السعر:** {package['price']} جنيه\n\n"
        f"⏳ في انتظار إرسال المستخدم لإيصال الدفع. عند التأكيد، اضغط الزر أدناه للتفعيل الفوري."
    )
    
    admin_keyboard = keyboards.admin_subscription_activation_kb(user.id, package_key)
    
    for admin_id in config.ADMIN_USER_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_notification,
                reply_markup=admin_keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Failed to send subscription notification to admin {admin_id}: {e}")

    user_reply = (
        f"✅ تم إرسال طلبك للإدارة.\n\n"
        f"الخطوة التالية: يرجى التواصل مع الدعم الفني عبر اليوزر التالي وإرسال **لقطة شاشة إيصال التحويل**:\n"
        f"👤 **الدعم:** {config.ADMIN_SUPPORT_USERNAME}\n\n"
        "سيتم تفعيل اشتراكك فور التحقق من عملية الدفع."
    )
    await query.edit_message_text(user_reply, reply_markup=keyboards.back_to_menu_kb())
    return config.MAIN_MENU


async def handle_document_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = database.ensure_user(update.effective_user.id, update.effective_user.full_name)
    question = update.message.text
    context_text = user["session"].get("last_text")

    if not context_text:
        await update.message.reply_text("⚠️ انقطع سياق المستند. أرسله مرة أخرى.", reply_markup=keyboards.main_menu_kb(user))
        return ConversationHandler.END

    thinking_message = await update.message.reply_text("⏳ عين الصقر تبحث في المستند...")
    
    prompt = f"Based on the following context, answer the user's question in Arabic.\n\nContext:\n{context_text}\n\nQuestion:\n{question}\n\nAnswer:"
    answer = await ai_call_with_fallback(prompt)
    
    await thinking_message.edit_text(answer, parse_mode=ParseMode.MARKDOWN)
    return config.DOCUMENT_QA_MODE
