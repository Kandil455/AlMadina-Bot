# handlers/main_handler.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.error import BadRequest
from PIL import Image
import io
import base64
from PyPDF2 import PdfReader

import database
import keyboards
import config
from utils import safe_md
from ai_services import (
    ai_summarize_bilingual, ai_summarize_en,
    ai_explain_bilingual, ai_explain_en,
    ai_mindmap, ai_extract_from_image, ai_call_with_fallback
)
from file_generator import (
    build_pdf_from_lines_weasy as build_stylish_pdf,
    build_mindmap_text_pdf
)

logger = logging.getLogger(__name__)

# --- File/Text Ingestion ---

def _pdf_to_text(file_bytes: bytes) -> str:
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
        return await do_mindmap(update, context)

    if action in ["summarize", "explain"]:
        # حفظ الإجراء المطلوب ثم عرض قائمة اختيار الأسلوب
        context.user_data['pending_action'] = action
        await query.edit_message_text(
            "اختر الأسلوب المفضل:",
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

    await query.edit_message_text(f"⏳ جاري إنشاء {title}...")
    
    try:
        result_text = await ai_func(context_text)
        lines = result_text.split('\n')
        
        if not lines or result_text.startswith("⚠️"):
            await query.edit_message_text(result_text or "⚠️ لم يتمكن الذكاء الاصطناعي من إنشاء رد.")
            return config.MAIN_MENU

        await _prepare_and_send_pdf(update, context, user, f"{action}_{style}", title, lines, is_mindmap=False, lang=lang)
    except Exception as e:
        logger.exception(f"Error in style_selection_handler for {action}_{style}")
        await query.edit_message_text("⚠️ حدث خطأ فني.")
    
    return config.MAIN_MENU

async def do_mindmap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = database.ensure_user(query.from_user.id, query.from_user.full_name)
    context_text = user["session"]["last_text"]
    
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

async def _prepare_and_send_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE, user: dict, session_key: str, title: str, content: list, is_mindmap: bool = False, lang: str = 'ar'):
    query = update.callback_query
    bot_username = (await context.bot.get_me()).username
    
    # 1. Generate the PDF file in memory
    if is_mindmap:
        pdf_bytes, pdf_fname = build_mindmap_text_pdf(title, bot_username, "\n".join(content))
    else:
        pdf_bytes, pdf_fname = build_stylish_pdf(title, bot_username, content, lang=lang)
    
    # 2. Delete the "Generating..." message
    try:
        await query.message.delete()
    except Exception as e:
        logger.warning(f"Could not delete message before sending PDF: {e}")

    # 3. Send the generated PDF file directly to the user
    await context.bot.send_document(
        chat_id=user['id'],
        document=pdf_bytes,
        filename=pdf_fname,
        caption=f"✅ تفضل، ملفك '{title}' جاهز!",
        reply_markup=keyboards.back_to_menu_kb() # Add a back button for convenience
    )

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