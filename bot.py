# bot.py
import os
from dotenv import load_dotenv
load_dotenv()

import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, PicklePersistence, PollAnswerHandler, ContextTypes
)

import config
import database
from spiritual_feed import get_random_snippets

# --- استيراد المعالجات من الملفات المنظمة ---
from handlers.common_handlers import (
    start_cmd, myid_cmd, cancel_cmd, unknown_cmd, error_handler, contact_handler,
    contact_admin_start, forward_to_admin, report_bug_start, forward_bug_report,
    download_pdf_handler, features_callback_router, health_check_cmd
)
from handlers.main_handler import (
    handle_document_entry, handle_photo_entry, handle_text_entry,
    main_menu_router,
    style_selection_handler, template_selection_handler, handle_document_question,
    do_stats,
    subscribe,
    handle_package_selection,
    handle_payment_confirmation
)
from handlers.quiz_handler import (
    quiz_command_entry, quiz_router, handle_quiz_answer,
    quiz_cancel_handler, quiz_review_handler
)
from handlers.library_handler import (
    library_entry, library_router, library_create_folder_handler, library_search_handler
)
from handlers.admin_handler import (
    admin_entry, admin_panel_router, do_broadcast, handle_admin_pick_user,
    admin_activate_sub_from_button, admin_exit_to_main,
    handle_set_tokens, handle_set_subs, admin_set_channel_apply  # ✨ 1. تم التأكد من استيراد الدالة
)

# --- إعداد تسجيل الأخطاء (Logging) ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

if not config.TELEGRAM_BOT_TOKEN:
    logger.critical("TELEGRAM_BOT_TOKEN is missing! Bot cannot start.")
    exit(1)


async def push_spiritual_tip(context: ContextTypes.DEFAULT_TYPE):
    """Send a pair of spiritual reminders (حديث + آية إن أمكن)."""
    try:
        snippets = get_random_snippets(count=3)
    except Exception as exc:
        logger.error("Failed to select spiritual snippets: %s", exc)
        return

    parts = []
    for idx, snippet in enumerate(snippets, 1):
        header = "📜 <b>حديث نبوي</b>" if snippet.get('type') == 'hadith' else "📖 <b>آية كريمة</b>"
        text = (
            f"{header}\n"
            f"<b>العنوان:</b> {snippet.get('title', 'بدون عنوان')}\n"
            f"<b>النص:</b> {snippet.get('text', '')}\n"
            f"<b>المصدر:</b> {snippet.get('reference', 'غير محدد')}\n"
            f"<b>الشرح:</b> {snippet.get('explanation', '')}"
        )
        parts.append(text)

    message = "🕋 <b>تذكرة إيمانية</b>\n\n" + "\n\n".join(parts)

    try:
        users = database.get_all_users_with_session()
    except Exception as exc:
        logger.error("Failed to fetch users for spiritual broadcast: %s", exc)
        return

    for u in users:
        if not u.get('session', {}).get('spiritual_on', True):
            continue
        try:
            await context.bot.send_message(chat_id=u['id'], text=message, parse_mode=ParseMode.HTML)
        except Exception as send_err:
            logger.debug("Spiritual tip not delivered to %s: %s", u['id'], send_err)


def main():
    """Starts the bot."""
    if not config.TELEGRAM_BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN is missing! Bot cannot start.")
        return

    database.setup_database()
    persistence = PicklePersistence(filepath="bot_persistence")
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).persistence(persistence).build()

    # بث روحاني ثابت كل 10 دقائق
    app.job_queue.run_repeating(push_spiritual_tip, interval=3600, first=120)

    # --- بناء معالجات المحادثات (Conversations) ---

    # --- المحادثة الأولى: خاصة بلوحة تحكم الأدمن فقط ---
    # هذه المحادثة معزولة لضمان عدم تداخل أوامر الأدمن مع أوامر المستخدم
    admin_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_entry, pattern=r"^act_admin$")
        ],
        states={
            config.ADMIN_PANEL: [CallbackQueryHandler(admin_panel_router)],
            config.ADMIN_BROADCAST_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, do_broadcast)],
            config.ADMIN_PICK_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_pick_user)],
            config.ADMIN_SET_TOKENS_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_set_tokens)],
            config.ADMIN_SET_SUBS_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_set_subs)],
            config.ADMIN_SET_CHANNEL_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_channel_apply)], # ✨ 2. تم إضافة الحالة هنا
        },
        fallbacks=[
            CommandHandler("cancel", cancel_cmd),
            CallbackQueryHandler(admin_exit_to_main, pattern=r"^act_back_to_menu$"),
        ],
        per_user=True, per_chat=True,
    )

    # --- المحادثة الثانية: خاصة بالتواصل مع الإدارة والبلاغات ---
    # هذه المحادثة مخصصة فقط لعملية إرسال رسالة أو بلاغ
    contact_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(contact_admin_start, pattern=r"^contact_admin$"),
            CallbackQueryHandler(report_bug_start, pattern=r"^report_issue$"),
        ],
        states={
            config.WAITING_ADMIN_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, forward_to_admin)],
            config.WAITING_BUG_REPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, forward_bug_report)],
        },
        fallbacks=[CommandHandler("cancel", cancel_cmd), CommandHandler("start", start_cmd)],
        per_user=True, per_chat=True,
    )

    # --- المحادثة الثالثة: المحادثة الرئيسية للمستخدم العادي ---
    # تحتوي على كل وظائف المستخدم الأساسية من رفع ملفات، قوائم، كويزات، ومكتبة
    main_conversation = ConversationHandler(
        entry_points=[
            # نقاط الدخول الأساسية
            CommandHandler("start", start_cmd),
            MessageHandler(filters.Document.ALL, handle_document_entry),
            MessageHandler(filters.PHOTO, handle_photo_entry),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_entry),
            MessageHandler(filters.CONTACT, contact_handler),
            
            # نقاط دخول لميزات مستقلة يمكن الوصول لها من القائمة الرئيسية
            CallbackQueryHandler(quiz_command_entry, pattern=r"^quiz$"),
            CallbackQueryHandler(library_entry, pattern=r"^library$"),
        ],
        states={
            # الحالة الابتدائية: انتظار إدخال (ملف، نص، صورة، رقم هاتف)
            config.WAITING_INPUT: [
                MessageHandler(filters.Document.ALL, handle_document_entry),
                MessageHandler(filters.PHOTO, handle_photo_entry),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_entry),
                MessageHandler(filters.CONTACT, contact_handler),
            ],
            
            # الحالة الرئيسية: القائمة التي تظهر بعد رفع ملف
            config.MAIN_MENU: [
                CallbackQueryHandler(main_menu_router, pattern=r"^(summarize|explain|mindmap)$"),
                CallbackQueryHandler(style_selection_handler, pattern=r"^style_"),
                CallbackQueryHandler(style_selection_handler, pattern=r"^style_"),
                CallbackQueryHandler(template_selection_handler, pattern=r"^tpl_pdf[12]$"),
                CallbackQueryHandler(do_stats, pattern=r"^stats$"),
                CallbackQueryHandler(subscribe, pattern=r"^subscribe$"),
                CallbackQueryHandler(handle_package_selection, pattern=r"^sub_package_"),
                CallbackQueryHandler(handle_payment_confirmation, pattern=r"^payment_sent_"),
                CallbackQueryHandler(download_pdf_handler, pattern=r"^download_pdf_"),
                CallbackQueryHandler(start_cmd, pattern=r"^act_back_to_menu$"),
                CallbackQueryHandler(features_callback_router, pattern=r"^feature_"),
                CallbackQueryHandler(features_callback_router, pattern=r"^productivity_features_menu$"),
                # يجب تكرار نقاط الدخول هنا للسماح بالانتقال بين الميزات
                CallbackQueryHandler(quiz_command_entry, pattern=r"^quiz$"),
                CallbackQueryHandler(library_entry, pattern=r"^library$"),
                # أزرار التواصل والبلاغات يجب أن تبدأ محادثتها الخاصة
                CallbackQueryHandler(contact_admin_start, pattern=r"^contact_admin$"),
                CallbackQueryHandler(report_bug_start, pattern=r"^report_issue$"),
                # زر لوحة التحكم يجب أن يبدأ محادثة الأدمن الخاصة
                CallbackQueryHandler(admin_entry, pattern=r"^act_admin$"),
            ],
            
            # حالات الكويز (Quiz States)
            config.QZ_MENU: [CallbackQueryHandler(quiz_router)],
            config.QZ_SETTINGS: [CallbackQueryHandler(quiz_router)],
            config.QZ_RUNNING: [
                CallbackQueryHandler(quiz_cancel_handler, pattern=r"^qz_cancel$"),
                CallbackQueryHandler(quiz_review_handler, pattern=r"^qz_review$"),
                CallbackQueryHandler(quiz_router, pattern=r"^qz_retry_wrong$"),
            ],

            # حالات المكتبة (Library States)
            config.LIB_MAIN: [CallbackQueryHandler(library_router)],
            config.LIB_FOLDER_VIEW: [CallbackQueryHandler(library_router)],
            config.LIB_ITEM_VIEW: [CallbackQueryHandler(library_router)],
            config.LIB_MOVE_ITEM: [CallbackQueryHandler(library_router)],
            config.LIB_CREATE_FOLDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, library_create_folder_handler)],
            config.LIB_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, library_search_handler)],
        },
        fallbacks=[
            CommandHandler("start", start_cmd),
            CommandHandler("cancel", cancel_cmd),
        ],
        per_chat=True,
        per_user=True,
        allow_reentry=True
    )

    # --- إضافة المعالجات للتطبيق بالترتيب الصحيح ---
    # 1. محادثة الأدمن (لأنها الأكثر تخصصًا ولها أولوية)
    app.add_handler(admin_conv)
    # 2. محادثة التواصل (محادثة قصيرة ومحددة)
    app.add_handler(contact_conv)
    # 3. محادثة المستخدم الرئيسية (الأكثر عمومية)
    app.add_handler(main_conversation)
    
    # --- المعالجات المستقلة (Global Handlers) ---
    # هذه المعالجات تعمل في أي وقت بغض النظر عن حالة المحادثة الحالية
    
    # معالج زر تفعيل الاشتراك (مهم جدًا للأدمن)
    app.add_handler(CallbackQueryHandler(admin_activate_sub_from_button, pattern=r"^admin_activate_sub_"))
    
    # معالج إجابات الكويز (يعمل عن طريق استطلاعات الرأي وليس الأزرار)
    app.add_handler(PollAnswerHandler(handle_quiz_answer))

    # زر رجوع عام مستخدم في بعض الشاشات (start_home)
    app.add_handler(CallbackQueryHandler(start_cmd, pattern=r"^start_home$"))
    # زر "رجوع للقائمة الرئيسية" ليعمل من أي حالة محادثة
    app.add_handler(CallbackQueryHandler(start_cmd, pattern=r"^act_back_to_menu$"))

    # الأوامر البسيطة
    app.add_handler(CommandHandler("myid", myid_cmd))
    app.add_handler(CommandHandler("health", health_check_cmd))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_cmd)) # لالتقاط الأوامر غير المعروفة
    
    # معالج الأخطاء يجب أن يكون آخر شيء دائمًا
    app.add_error_handler(error_handler)

    # --- بدء تشغيل البوت ---
    logger.info("Starting Al Madina Bot (Final Version)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
