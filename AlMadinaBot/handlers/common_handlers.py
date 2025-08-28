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
from PIL import Image, ImageDraw
from typing import List

import database
import keyboards
import config
from utils import safe_md, beautify_text

# --- Admin IDs compatibility helper ---
def _admin_ids():
    return getattr(config, 'ADMIN_IDS', getattr(config, 'ADMIN_USER_IDS', []))

# --- Simple text→image helper (centered text, auto-wrap naive) ---
def _text_to_image(lines: List[str], width: int = 1080, height: int = 1350):
    img = Image.new('RGB', (width, height), color=(245, 245, 245))
    draw = ImageDraw.Draw(img)
    y = 60
    margin = 60
    for raw in lines:
        text = str(raw or '').strip()
        if not text:
            y += 28
            continue
        # naive wrap by length
        while len(text) > 0:
            chunk = text[:48]
            text = text[48:]
            draw.text((margin, y), chunk, fill=(20, 20, 20))
            y += 36
            if y > height - 60:
                break
        if y > height - 60:
            break
    bio = io.BytesIO()
    img.save(bio, format='PNG')
    bio.seek(0)
    return bio

from ai_services import ai_summarize_bilingual, ai_call_with_fallback, extract_audio_from_youtube, clamp_text
from file_generator import build_pdf_from_lines_weasy as build_stylish_pdf

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

async def _make_pdf_and_prompt_download(update: Update, context: ContextTypes.DEFAULT_TYPE, user: dict, title: str, lines: List[str], session_key: str):
    query = update.callback_query
    bot_username = (await context.bot.get_me()).username
    pdf_bytes, pdf_fname = build_stylish_pdf(title, bot_username, lines, lang='ar')
    pdf_b64 = base64.b64encode(pdf_bytes.getvalue()).decode('utf-8')
    user['session'][f'file_{session_key}'] = {'pdf': {'data': pdf_b64, 'fname': pdf_fname}}
    database._update_user_in_db(user['id'], user)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton('📄 تحميل PDF', callback_data=f'download_pdf_{session_key}')],
        [InlineKeyboardButton('⬅️ رجوع', callback_data='start_home')]
    ])
    await query.edit_message_text(f"✅ **{title} جاهز!**\n\nاضغط لتحميل الملف.", parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

async def features_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # Always answer the callback quickly
    
    data = query.data
    user = database.ensure_user(query.from_user.id, query.from_user.full_name)

    # --- Productivity Features ---
    if data == "feature_lucky_draw":
        # This should ideally be an admin-triggered command, not user
        await query.message.reply_text("🎲 سيتم إعلان الفائز في السحب قريبًا من قبل الإدارة!")
    elif data == "feature_achievements":
        files = user.get('files_processed', 0)
        ach = []
        if files >= 1: ach.append("🎉 أول ملف!")
        if files >= 10: ach.append("🏅 10 ملفات!")
        if files >= 50: ach.append("🏆 50 ملف!")
        msg = "🏆 إنجازاتك:\n" + ("\n".join(ach) if ach else "لا يوجد إنجازات بعد. ابدأ الآن!")
        await query.message.reply_text(msg)
    elif data == "feature_monthly_challenge":
        await query.message.reply_text("📅 تحدي الشهر: قم بتلخيص 5 ملفات هذا الشهر واحصل على 1000 توكنز هدية!")
    elif data == "feature_leaderboard":
        users = database.get_all_users_detailed()
        ranked = sorted(users, key=lambda u: u.get('files_processed', 0), reverse=True)[:10]
        msg = "🏅 الأكثر تفاعلاً (حسب الملفات):\n" + "\n".join([f"{i+1}. {u['name']} - {u.get('files_processed', 0)} ملف" for i, u in enumerate(ranked)])
        await query.message.reply_text(beautify_text(msg))

    # --- Smart Features ---
    elif data == "feature_quote":
        quotes = ["💡 العلم نور.", "🚀 لا يوجد مستحيل مع الإرادة.", "📚 المذاكرة طريق النجاح."]
        await query.message.reply_text(random.choice(quotes))
    elif data == "feature_badge":
        files = user.get('files_processed', 0)
        badge = "🏆 بطل" if files > 20 else ("🥇 نشيط" if files > 10 else "⭐ مبتدئ")
        await query.message.reply_text(f"شارتك الحالية: {badge}")
    elif data == "feature_top10":
        # This is the same as leaderboard, maybe change its purpose later
        await features_callback_router(Update(update.update_id, callback_query=query.from_dict({'id': query.id, 'from': query.from_user.to_dict(), 'message': query.message.to_dict(), 'chat_instance': query.chat_instance, 'data': 'feature_leaderboard'})), context)
    elif data == "feature_night_mode":
        user['session']['night_mode'] = not user['session'].get('night_mode', False)
        database._update_user_in_db(user['id'], user)
        msg = "🌙 تم تفعيل الوضع الليلي!" if user['session']['night_mode'] else "☀️ تم إيقاف الوضع الليلي."
        await query.message.reply_text(msg)
    elif data == "feature_weekly_report":
        msg = f"📈 تقريرك الأسبوعي:\n- الملفات المعالجة: {user.get('files_processed', 0)}\n- التوكنز المتبقية: {user.get('tokens', 0)}"
        await query.message.reply_text(beautify_text(msg))
    elif data == "feature_weekly_goal":
        goals = ["🎯 ذاكر 3 ساعات هذا الأسبوع!", "🎯 أنجز ملخصين جديدين!"]
        await query.message.reply_text(random.choice(goals))

    # --- Wired Productivity (End-to-End) ---
    elif data == 'feature_text_to_pdf':
        context_text = (user['session'].get('last_text') or '').strip()
        if not context_text:
            await query.message.reply_text('⚠️ مفيش نص في السياق. ابعت نص أو PDF الأول.')
        else:
            lines = [ln for ln in context_text.split('\n') if ln.strip()]
            await _make_pdf_and_prompt_download(update, context, user, 'مستند PDF من نصك', lines, session_key='prod_textpdf')
    elif data == 'feature_text_to_image':
        context_text = (user['session'].get('last_text') or '').strip()
        if not context_text:
            await query.message.reply_text('⚠️ مفيش نص في السياق. ابعت نص أو PDF الأول.')
        else:
            img_bio = _text_to_image(context_text.split('\n'))
            await query.message.reply_photo(photo=img_bio, caption='🖼️ تم توليد صورة من النص.')
    elif data == 'feature_summarize_pdf':
        context_text = (user['session'].get('last_text') or '').strip()
        if not context_text:
            await query.message.reply_text('⚠️ مفيش نص/سياق PDF. ابعت PDF أو نص الأول.')
        else:
            await query.edit_message_text('⏳ جاري التلخيص...')
            summary = await ai_summarize_bilingual(clamp_text(context_text))
            if not summary or summary.startswith('⚠️'):
                await query.edit_message_text(summary or '⚠️ فشل التلخيص.')
            else:
                lines = [ln for ln in summary.split('\n') if ln.strip()]
                await _make_pdf_and_prompt_download(update, context, user, 'ملخص PDF', lines, session_key='prod_sum')
    elif data == 'feature_make_pptx':
        await query.message.reply_text('🧩 توليد شرائح PPTX هيُضاف قريبًا بصيغة ملف قابل للتحميل.')
    elif data == 'feature_download_media':
        context.user_data['mode'] = 'download_media_wait_url'
        await query.edit_message_text('🔗 ابعت رابط يوتيوب (https://...) لتحويله إلى نص/صوت.', reply_markup=keyboards.back_home_kb())

    # --- Menu Navigation ---
    elif data == "productivity_features_menu":
        await query.edit_message_text("🚀 اختر ميزة إنتاجية:", reply_markup=keyboards.productivity_features_kb())
    elif data == "admin_panel":
        await admin_panel(update, context)
    elif data == "report_issue":
        await report_issue(update, context)
    elif data == "contact_admin":
        await contact_admin(update, context)
    elif data == "start_home":
        await start_cmd(update, context)
    # After sending a text message, it's good practice to show the main menu again if appropriate
    # This part can be refined based on desired user flow

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
        await update.effective_message.reply_text('⏳ جاري جلب الصوت...')
        result = await extract_audio_from_youtube(url)
        context.user_data['mode'] = None
        await update.effective_message.reply_text(result if result else '⚠️ لم أتمكن من المعالجة.')
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