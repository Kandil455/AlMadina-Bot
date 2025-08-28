# bot.py
import os
from dotenv import load_dotenv
load_dotenv()

import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, PicklePersistence, PollAnswerHandler
)

import config
import database

# --- استيراد المعالجات من الملفات المنظمة ---
from handlers.common_handlers import (
    start_cmd, myid_cmd, cancel_cmd, unknown_cmd, error_handler, contact_handler,
    contact_admin_start, forward_to_admin, report_bug_start, forward_bug_report
)
from handlers.main_handler import (
    handle_document_entry, handle_photo_entry, handle_text_entry,
    main_menu_router,
    style_selection_handler, handle_document_question,
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
    admin_entry, admin_panel_router, do_broadcast, admin_set_channel_prompt, admin_set_channel_apply,
    handle_admin_dm_wait, handle_admin_pick_user, admin_credit_sub_apply,
    admin_activate_sub_from_button, admin_exit_to_main
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

def main():
    """Starts the bot."""
    if not config.TELEGRAM_BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN is missing! Bot cannot start.")
        return

    database.setup_database()
    persistence = PicklePersistence(filepath="bot_persistence")
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).persistence(persistence).build()

    # --- بناء معالجات المحادثات (Conversations) ---

    # ✨ --- [التعديل الأول] إضافة محادثة جديدة ومستقلة للتواصل والبلاغات --- ✨
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

    # هذا هو الكود الأصلي بتاعك بدون تغيير، مع حذف الحالات التي تم نقلها
    main_conversation = ConversationHandler(
        entry_points=[
            # نقاط الدخول الأساسية
            CommandHandler("start", start_cmd),
            MessageHandler(filters.Document.ALL, handle_document_entry),
            MessageHandler(filters.PHOTO, handle_photo_entry),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_entry),
            MessageHandler(filters.CONTACT, contact_handler),
            
            # نقاط الدخول للميزات التي يمكن الوصول إليها من أي مكان
            CallbackQueryHandler(quiz_command_entry, pattern=r"^quiz$"),
            CallbackQueryHandler(library_entry, pattern=r"^library$"),
            CallbackQueryHandler(admin_entry, pattern=r"^act_admin$"),
            # ✨ --- [التعديل الثاني] يجب أيضًا وضع أزرار التواصل هنا كنقاط دخول للمحادثة الجديدة --- ✨
            CallbackQueryHandler(contact_admin_start, pattern=r"^contact_admin$"),
            CallbackQueryHandler(report_bug_start, pattern=r"^report_issue$"),
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
                CallbackQueryHandler(do_stats, pattern=r"^stats$"),
                CallbackQueryHandler(subscribe, pattern=r"^subscribe$"),
                CallbackQueryHandler(handle_package_selection, pattern=r"^sub_package_"),
                CallbackQueryHandler(handle_payment_confirmation, pattern=r"^payment_sent_"),
                CallbackQueryHandler(contact_admin_start, pattern=r"^contact_admin$"),
                CallbackQueryHandler(report_bug_start, pattern=r"^report_issue$"),
                CallbackQueryHandler(start_cmd, pattern=r"^act_back_to_menu$"),
                # يجب تكرار نقاط الدخول هنا للسماح بالانتقال بين الميزات
                CallbackQueryHandler(quiz_command_entry, pattern=r"^quiz$"),
                CallbackQueryHandler(library_entry, pattern=r"^library$"),
                CallbackQueryHandler(admin_entry, pattern=r"^act_admin$"),
            ],
            
            # ✨ --- [التعديل الثالث] حذف حالات التواصل من هنا لأنها انتقلت لمحادثة مستقلة --- ✨
            # config.WAITING_ADMIN_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, forward_to_admin)],
            # config.WAITING_BUG_REPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, forward_bug_report)],

            # === دمج حالات المحادثات الفرعية هنا ===

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
            
            # حالات الأدمن (Admin States)
            config.ADMIN_PANEL: [
                CallbackQueryHandler(admin_panel_router),
                CallbackQueryHandler(admin_exit_to_main, pattern=r"^act_back_to_menu$"),
                CallbackQueryHandler(admin_activate_sub_from_button, pattern=r"^admin_activate_sub_")
            ],
            config.ADMIN_BROADCAST_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, do_broadcast)],
            config.ADMIN_DM_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_dm_wait)],
            config.ADMIN_PICK_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_pick_user)],
            config.ADMIN_SET_CHANNEL_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_channel_apply)],
            config.ADMIN_CREDIT_SUB_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_credit_sub_apply)],
        },
        fallbacks=[
            CommandHandler("start", start_cmd),
            CommandHandler("cancel", cancel_cmd),
        ],
        per_chat=True,
        per_user=True,
        allow_reentry=True
    )

    # --- إضافة المعالجات للتطبيق ---
    # ✨ --- [التعديل الرابع] نضيف المحادثة الجديدة هنا قبل المحادثة الرئيسية --- ✨
    app.add_handler(contact_conv)
    app.add_handler(main_conversation)
    
    # المعالجات المستقلة التي لا تقع ضمن محادثة
    app.add_handler(PollAnswerHandler(handle_quiz_answer))
    app.add_handler(CommandHandler("myid", myid_cmd))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_cmd)) # لالتقاط الأوامر غير المعروفة
    
    # معالج الأخطاء يجب أن يكون آخر شيء
    app.add_error_handler(error_handler)

    # --- بدء تشغيل البوت ---
    logger.info("Starting Al Madina Bot (Final Version)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()