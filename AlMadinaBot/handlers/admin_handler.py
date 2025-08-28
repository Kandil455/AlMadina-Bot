# handlers/admin_handler.py
import asyncio
import logging
import csv
import tempfile
import datetime
import random
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

import database
from handlers.common_handlers import start_cmd
import keyboards
import config
from utils import safe_md, beautify_text

logger = logging.getLogger(__name__)

def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_USER_IDS

# --- Entry Point ---
async def admin_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        if update.callback_query: await update.callback_query.answer("🚫 غير مصرح لك.", show_alert=True)
        else: await update.effective_message.reply_text("🚫 غير مصرح لك.")
        return ConversationHandler.END

    text = "👑 لوحة تحكم الأدمن"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=keyboards.admin_panel_kb())
    else:
        await update.effective_message.reply_text(text, reply_markup=keyboards.admin_panel_kb())
    return config.ADMIN_PANEL

# لوحة تحكم الأدمن الرئيسية
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = beautify_text("لوحة تحكم الأدمن: اختر إجراء")
    await update.effective_message.reply_text(msg, reply_markup=keyboards.admin_panel_kb())

# --- Main Panel Router ---
async def admin_panel_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    # Quick admin-only safety
    if not is_admin(update.effective_user.id):
        await query.answer("🚫 غير مصرح لك.", show_alert=True)
        return ConversationHandler.END

    # === Simple actions ===
    if data == "admin_stats":
        await admin_stats_handler(update, context)
        return config.ADMIN_PANEL

    if data == "admin_reports":
        await admin_logs_handler(update, context)
        return config.ADMIN_PANEL

    if data == "admin_export_users":
        await admin_export_users(update, context)
        return config.ADMIN_PANEL

    if data == "admin_export_stats":
        await admin_export_stats(update, context)
        return config.ADMIN_PANEL

    if data == "admin_toggle_ai":
        await admin_toggle_ai(update, context)
        return config.ADMIN_PANEL

    if data == "admin_maintenance":
        await admin_maintenance_mode(update, context)
        return config.ADMIN_PANEL

    if data == "admin_reward_all":
        await admin_reward_all(update, context)
        return config.ADMIN_PANEL

    if data == "admin_award_badges":
        await admin_award_badges(update, context)
        return config.ADMIN_PANEL

    if data == "admin_weekly_report":
        await admin_weekly_report(update, context)
        return config.ADMIN_PANEL

    if data == "admin_daily_quote":
        await admin_daily_quote(update, context)
        return config.ADMIN_PANEL

    if data == "admin_top_active_users":
        await admin_top_active_users(update, context)
        return config.ADMIN_PANEL

    if data == "admin_restart_bot":
        await admin_restart_bot(update, context)
        return config.ADMIN_PANEL

    if data == "admin_set_channel":
        return await admin_set_channel_prompt(update, context)

    if data == "admin_dm_start":
        await admin_dm_user(update, context)
        return config.ADMIN_PANEL

    # === Pattern-based actions ===
    if data.startswith("admin_ban_toggle_"):
        try:
            uid = int(data.rsplit("_", 1)[-1])
            user = database._get_user_from_db(uid)
            if not user:
                await query.answer("❌ مستخدم غير موجود.", show_alert=True)
                return config.ADMIN_PANEL
            user["banned"] = not user.get("banned", False)
            database._update_user_in_db(uid, user)
            await query.answer("✅ تم تبديل حالة الحظر.", show_alert=True)
        except Exception:
            await query.answer("⚠️ فشل تبديل حالة الحظر.", show_alert=True)
        return config.ADMIN_PANEL

    if data.startswith("admin_dm_user_"):
        try:
            uid = int(data.rsplit("_", 1)[-1])
            context.user_data['admin_dm_target'] = uid
            await query.edit_message_text(f"✉️ اكتب الرسالة ليتم إرسالها إلى {uid}:")
            return config.ADMIN_DM_WAIT
        except Exception:
            await query.answer("⚠️ صيغة غير صحيحة.", show_alert=True)
            return config.ADMIN_PANEL

    if data == "admin_broadcast":
        await query.edit_message_text("✍️ اكتب الرسالة التي سيتم بثها لجميع المستخدمين:")
        return config.ADMIN_BROADCAST_WAIT
    
    if data == "admin_users" or data.startswith("admin_users_page_"):
        return await admin_users_list(update, context)

    if data == "admin_settings":
        return await admin_settings_menu(update, context)
        
    if data == "admin_pick_user_by_id":
        await query.edit_message_text("👤 أدخل ID المستخدم الذي تريد تعديل بياناته:")
        # We'll create a new state for this to listen for the ID
        return config.ADMIN_PICK_USER 
    
    if data == "back_main":
        from handlers.common_handlers import start_cmd # Avoid circular import
        await start_cmd(update, context)
        return ConversationHandler.END
        
    return config.ADMIN_PANEL


# --- Broadcast Feature ---
async def do_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("⚠️ يرجى إرسال رسالة نصية للبث.")
        return config.ADMIN_BROADCAST_WAIT
        
    user_ids = database.get_all_user_ids()
    sent_count = 0
    failed_count = 0
    
    await update.message.reply_text(f"⏳ جاري بدء البث إلى {len(user_ids)} مستخدم...")

    for user_id in user_ids:
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📢 رسالة من الأدمن:\n\n{text}")
            sent_count += 1
        except Exception:
            failed_count += 1
        await asyncio.sleep(0.1) # To avoid hitting Telegram API limits

    await update.message.reply_text(f"✅ تم إكمال البث.\n\n- نجح: {sent_count}\n- فشل: {failed_count}")
    return ConversationHandler.END


# --- User Management ---
async def admin_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    all_users = database.get_all_users_detailed() # Requires a new DB function
    
    if not all_users:
        await query.edit_message_text("لا يوجد مستخدمون مسجلون بعد.", reply_markup=keyboards.back_to_menu_kb())
        return config.ADMIN_PANEL

    page = int(query.data.split('_')[-1]) if query.data.startswith("admin_users_page_") else 0
    items_per_page = 10
    start_index = page * items_per_page
    end_index = start_index + items_per_page
    users_on_page = all_users[start_index:end_index]

    text_lines = ["👥 **قائمة المستخدمين**\n"]
    for u in users_on_page:
        line = (f"👤 `{u['id']}` - {safe_md(u.get('name', 'N/A'))}\n"
                f"   - 📞: `{u.get('phone_number', 'N/A')}` | 🎟️: {u.get('tokens', 0)}")
        text_lines.append(line)

    keyboard = keyboards.admin_user_list_kb(page, len(all_users), items_per_page)
    await query.edit_message_text("\n".join(text_lines), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return config.ADMIN_PANEL

# ... (We will need to add more admin functions like editing users, but this is a solid start) ...


# --- Settings Management ---
async def admin_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    settings = database.get_settings()
    channel = settings.get("force_sub_channel", "لم يتم التعيين")
    text = f"⚙️ **إعدادات البوت**\n\nالقناة الإجبارية: `{channel}`"
    keyboard = keyboards.admin_settings_kb(channel)
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return config.ADMIN_PANEL

async def admin_set_channel_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    text = ("أرسل يوزر القناة الجديد (e.g., `@mychannel`) أو ID القناة الخاصة (e.g., `-100123...`).\n\n"
            "**مهم:** يجب أن يكون البوت مشرفًا في القناة.")
    await query.edit_message_text(text)
    return config.ADMIN_SET_CHANNEL_WAIT

async def admin_set_channel_apply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    new_channel = update.message.text.strip()
    if not new_channel:
        await update.message.reply_text("⚠️ الإدخال غير صالح.")
        return config.ADMIN_SET_CHANNEL_WAIT
        
    settings = database.get_settings()
    settings["force_sub_channel"] = new_channel
    database.save_settings(settings)
    
    await update.message.reply_text(f"✅ تم تحديث قناة الاشتراك إلى: `{new_channel}`", parse_mode=ParseMode.MARKDOWN)
    await update.message.reply_text("👑 لوحة تحكم الأدمن", reply_markup=keyboards.admin_panel_kb())
    return config.ADMIN_PANEL

# إدارة المستخدمين
async def admin_users_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = database.get_all_users()  # أضفها في database.py
    msg = beautify_text(f"👥 عدد المستخدمين: {len(users)}\nاختر مستخدمًا أو ابحث بالاسم/ID.")
    kb = keyboards.admin_user_list_kb(page=0, total_users=len(users), items_per_page=10)
    await update.effective_message.reply_text(msg, reply_markup=kb)

# عرض إحصائيات البوت
async def admin_stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = database.get_bot_stats()  # أضفها في database.py
    msg = beautify_text(f"📊 إحصائيات البوت:\n- المستخدمون: {stats.get('users', 0)}\n- الملخصات: {stats.get('summaries', 0)}\n- أكثر ميزة: {stats.get('top_feature', 'غير محدد')}")
    await update.effective_message.reply_text(msg)

# إعدادات البوت
async def admin_settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = beautify_text("⚙️ إعدادات البوت: اختر ما تريد تعديله")
    await update.effective_message.reply_text(msg, reply_markup=keyboards.admin_settings_kb(current_channel="@yourchannel"))

# سجل العمليات
async def admin_logs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logs = database.get_last_logs(10)  # أضفها في database.py
    msg = beautify_text("📝 آخر العمليات:\n" + "\n".join(logs))
    await update.effective_message.reply_text(msg)

# إرسال إشعار جماعي
async def admin_broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("✍️ أرسل نص الإشعار ليتم إرساله لكل المستخدمين.")
    context.user_data['admin_broadcast'] = True

async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('admin_broadcast'):
        user_ids = database.get_all_user_ids()
        for uid in user_ids:
            try:
                await context.bot.send_message(uid, beautify_text(update.message.text))
            except Exception:
                continue
        await update.message.reply_text("✅ تم إرسال الإشعار.")
        context.user_data['admin_broadcast'] = False

# --- Admin DM Wait Handler ---
async def handle_admin_dm_wait(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle sending a direct message to a user selected via admin_dm_user_{id}."""
    target = context.user_data.get('admin_dm_target')
    text = (update.message.text or '').strip()
    if not target:
        await update.message.reply_text("⚠️ لا يوجد مستخدم محدد.")
        return config.ADMIN_PANEL
    if not text:
        await update.message.reply_text("⚠️ أرسل نص الرسالة أولاً.")
        return config.ADMIN_DM_WAIT
    try:
        await context.bot.send_message(int(target), beautify_text(text))
        await update.message.reply_text("✅ تم إرسال الرسالة.")
        database.log_admin_action("رسالة خاصة (ID محدد)", f"إلى {target}: {text}")
    except Exception:
        await update.message.reply_text("⚠️ تعذر إرسال الرسالة للمستخدم المستهدف.")
    context.user_data.pop('admin_dm_target', None)
    return config.ADMIN_PANEL

# بحث وتعديل مستخدم
async def admin_search_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("🔍 أرسل اسم أو ID المستخدم للبحث.")
    context.user_data['admin_search'] = True

async def handle_search_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('admin_search'):
        query = update.message.text.strip()
        user = database.find_user(query)  # أضفها في database.py
        if user:
            msg = beautify_text(f"👤 المستخدم: {user['name']}\nID: {user['id']}")
            await update.message.reply_text(msg, reply_markup=keyboards.admin_user_view_kb(user['id']))
        else:
            await update.message.reply_text("❌ لم يتم العثور على المستخدم.")
        context.user_data['admin_search'] = False

# تصدير المستخدمين كـ CSV
async def admin_export_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = database.get_all_users_detailed()
    if not users:
        await update.effective_message.reply_text("لا يوجد مستخدمون للتصدير.")
        return
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.csv', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["id", "name", "phone_number", "tokens", "files_processed"])
        writer.writeheader()
        for u in users:
            writer.writerow(u)
        f.flush()
        f.seek(0)
        await update.effective_message.reply_document(document=f.name, filename="users_export.csv", caption="📥 تم تصدير المستخدمين بنجاح.")
    database.log_admin_action("تصدير مستخدمين")

# تفعيل/تعطيل ميزة ذكاء اصطناعي
async def admin_toggle_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    settings = database.get_settings()
    ai_enabled = settings.get("ai_enabled", "1") == "1"
    settings["ai_enabled"] = "0" if ai_enabled else "1"
    database.save_settings(settings)
    msg = "✅ تم تفعيل الذكاء الاصطناعي." if not ai_enabled else "❌ تم تعطيله مؤقتًا."
    await update.effective_message.reply_text(msg)
    database.log_admin_action("تغيير حالة AI", msg)

# وضع الصيانة
async def admin_maintenance_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    settings = database.get_settings()
    maintenance = settings.get("maintenance", "0") == "1"
    settings["maintenance"] = "0" if maintenance else "1"
    database.save_settings(settings)
    msg = "🔧 تم تفعيل وضع الصيانة. لن يتمكن المستخدمون من استخدام البوت." if not maintenance else "✅ تم إنهاء وضع الصيانة."
    await update.effective_message.reply_text(msg)
    database.log_admin_action("تغيير وضع الصيانة", msg)

# إرسال مكافأة جماعية
async def admin_reward_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = database.get_all_user_ids()
    for uid in users:
        user = database._get_user_from_db(uid)
        if user:
            user["tokens"] = user.get("tokens", 0) + 100
            database._update_user_in_db(uid, user)
            try:
                await context.bot.send_message(uid, "🎁 تم إضافة 100 نقطة هدية لك من الأدمن!")
            except Exception:
                continue
    await update.effective_message.reply_text("✅ تم إرسال المكافأة لكل المستخدمين.")
    database.log_admin_action("مكافأة جماعية")

# مراجعة آخر العمليات
async def admin_review_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logs = database.get_last_logs(20)
    msg = beautify_text("📝 آخر 20 عملية إدارية:\n" + "\n".join(logs))
    await update.effective_message.reply_text(msg)

# جدولة رسالة جماعية
async def admin_schedule_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("🕒 أرسل نص الرسالة متبوعًا بوقت الإرسال (مثال: 2025-08-24 15:00:00)")
    context.user_data['admin_schedule_broadcast'] = True

async def handle_schedule_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('admin_schedule_broadcast'):
        try:
            text, timestr = update.message.text.rsplit(' ', 1)
            send_time = datetime.datetime.strptime(timestr, "%Y-%m-%d %H:%M:%S")
            now = datetime.datetime.now()
            delay = (send_time - now).total_seconds()
            if delay < 0:
                await update.message.reply_text("⚠️ الوقت المدخل قد مضى!")
                return
            await update.message.reply_text(f"⏳ سيتم إرسال الرسالة في {send_time}.")
            await asyncio.sleep(delay)
            user_ids = database.get_all_user_ids()
            for uid in user_ids:
                try:
                    await context.bot.send_message(uid, beautify_text(text))
                except Exception:
                    continue
            await update.message.reply_text("✅ تم إرسال الرسالة المجدولة.")
            database.log_admin_action("جدولة بث", text)
        except Exception:
            await update.message.reply_text("⚠️ صيغة غير صحيحة. أرسل الرسالة ثم التاريخ والوقت.")
        context.user_data['admin_schedule_broadcast'] = False

# إرسال رسالة لمستخدم محدد
async def admin_dm_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("✉️ أرسل ID المستخدم ثم الرسالة (مثال: 123456 مرحبًا بك)")
    context.user_data['admin_dm_user'] = True

async def handle_dm_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('admin_dm_user'):
        try:
            uid, msg = update.message.text.strip().split(' ', 1)
            await context.bot.send_message(int(uid), beautify_text(msg))
            await update.message.reply_text("✅ تم إرسال الرسالة.")
            database.log_admin_action("رسالة خاصة", f"إلى {uid}: {msg}")
        except Exception:
            await update.message.reply_text("⚠️ صيغة غير صحيحة. أرسل ID ثم الرسالة.")
        context.user_data['admin_dm_user'] = False

# تصدير الإحصائيات كـ CSV
async def admin_export_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = database.get_bot_stats()
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.csv', encoding='utf-8') as f:
        writer = csv.writer(f)
        for k, v in stats.items():
            writer.writerow([k, v])
        f.flush()
        f.seek(0)
        await update.effective_message.reply_document(document=f.name, filename="bot_stats.csv", caption="📊 تم تصدير الإحصائيات.")
    database.log_admin_action("تصدير إحصائيات")

# إعادة تشغيل البوت (يتطلب دعم خارجي أو إشعار فقط)
async def admin_restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("🔄 تم إرسال أمر إعادة التشغيل (تأكد من وجود خدمة خارجية تدعم ذلك).")
    database.log_admin_action("إعادة تشغيل البوت")

# مراجعة نشاط مستخدم
async def admin_user_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("🔍 أرسل ID المستخدم لمراجعة نشاطه.")
    context.user_data['admin_user_activity'] = True

async def handle_user_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('admin_user_activity'):
        uid = update.message.text.strip()
        user = database._get_user_from_db(int(uid))
        if user:
            msg = beautify_text(f"👤 {user['name']}\nID: {user['id']}\nالملفات: {user.get('files_processed', 0)}\nالنقاط: {user.get('tokens', 0)}")
            await update.message.reply_text(msg)
            database.log_admin_action("مراجعة نشاط مستخدم", f"{uid}")
        else:
            await update.message.reply_text("❌ لم يتم العثور على المستخدم.")
        context.user_data['admin_user_activity'] = False

# إرسال اقتراح ميزة للمستخدمين
async def admin_suggest_feature(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("💡 أرسل نص الميزة المقترحة ليتم إرسالها لكل المستخدمين للتصويت.")
    context.user_data['admin_suggest_feature'] = True

async def handle_suggest_feature(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('admin_suggest_feature'):
        text = update.message.text.strip()
        user_ids = database.get_all_user_ids()
        for uid in user_ids:
            try:
                await context.bot.send_poll(uid, "ما رأيك في الميزة الجديدة؟", ["ممتازة!", "جيدة", "لا أحتاجها"], explanation=text)
            except Exception:
                continue
        await update.message.reply_text("✅ تم إرسال الاقتراح.")
        database.log_admin_action("اقتراح ميزة", text)
        context.user_data['admin_suggest_feature'] = False

# نظام شارات وجوائز تلقائي
async def admin_award_badges(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = database.get_all_users_detailed()
    top_users = sorted(users, key=lambda u: u.get('files_processed', 0), reverse=True)[:5]
    badges = ["🏆 بطل الأسبوع", "🥇 الأكثر نشاطًا", "🥈 ثاني أكثر نشاط", "🥉 ثالث أكثر نشاط", "⭐ نجم الأسبوع"]
    for i, user in enumerate(top_users):
        try:
            await context.bot.send_message(user['id'], f"{badges[i]}! مبروك لك على نشاطك 🎉")
        except Exception:
            continue
    await update.effective_message.reply_text("✅ تم منح الشارات للأكثر تفاعلًا.")
    database.log_admin_action("منح شارات")

# إرسال تقرير أسبوعي تلقائي
async def admin_weekly_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = database.get_bot_stats()
    users = database.get_all_users_detailed()
    msg = beautify_text(f"📈 تقرير أسبوعي:\n- المستخدمون: {stats.get('users', 0)}\n- الملخصات: {stats.get('summaries', 0)}\n- أكثر ميزة: {stats.get('top_feature', 'غير محدد')}")
    for u in users:
        try:
            await context.bot.send_message(u['id'], msg)
        except Exception:
            continue
    await update.effective_message.reply_text("✅ تم إرسال التقرير الأسبوعي.")
    database.log_admin_action("تقرير أسبوعي")

# تفعيل الوضع الليلي للمستخدمين
async def admin_toggle_night_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = database.get_all_user_ids()
    for uid in users:
        user = database._get_user_from_db(uid)
        if user:
            user['session']['night_mode'] = not user['session'].get('night_mode', False)
            database._update_user_in_db(uid, user)
            try:
                await context.bot.send_message(uid, "🌙 تم تفعيل الوضع الليلي! استمتع بتجربة أهدأ.")
            except Exception:
                continue
    await update.effective_message.reply_text("✅ تم تفعيل الوضع الليلي لكل المستخدمين.")
    database.log_admin_action("تفعيل الوضع الليلي")

# إرسال رسالة ترحيب متحركة (GIF)
async def admin_credit_sub_apply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the admin's command to apply a subscription to a user."""
    admin_id = update.effective_user.id
    try:
        parts = update.message.text.strip().split()
        if len(parts) != 2:
            raise ValueError("Invalid format")

        user_id = int(parts[0])
        package_key = parts[1].lower()

        package = config.SUBSCRIPTION_PACKAGES.get(package_key)
        if not package:
            await update.message.reply_text(f"⚠️ كود الباقة '{package_key}' غير صحيح.")
            return config.ADMIN_CREDIT_SUB_WAIT

        target_user = database._get_user_from_db(user_id)
        if not target_user:
            await update.message.reply_text(f"⚠️ المستخدم صاحب الـ ID `{user_id}` غير موجود.")
            return config.ADMIN_CREDIT_SUB_WAIT

        # تطبيق المميزات
        target_user["tokens"] += package["tokens"]
        target_user["subscription_limit"] += package["file_limit"]
        database._update_user_in_db(user_id, target_user)

        # إشعار الأدمن بالنجاح
        await update.message.reply_text(
            f"✅ تم تفعيل **{package['name']}** للمستخدم {target_user['name']} (`{user_id}`) بنجاح."
        )

        # إشعار المستخدم بالتفعيل
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🎉 تهانينا! تم تفعيل **{package['name']}** لحسابك بنجاح.\n\n"
                 f"تمت إضافة {package['tokens']:,} توكنز لرصيدك.\n\n"
                 "شكراً لثقتك ودعمك! يمكنك الآن الاستمتاع بمميزات البوت الكاملة."
        )

    except (ValueError, IndexError):
        await update.message.reply_text("⚠️ صيغة خاطئة. يرجى الإرسال بالتنسيق التالي: `USER_ID package_key`")
        return config.ADMIN_CREDIT_SUB_WAIT
    except Exception as e:
        logger.error(f"Error in admin_credit_sub_apply: {e}")
        await update.message.reply_text("حدث خطأ فني أثناء محاولة تفعيل الاشتراك.")

    # الرجوع للوحة التحكم الرئيسية
    await admin_entry(update, context)
    return config.ADMIN_PANEL

# في ملف admin_handler.py

async def admin_activate_sub_from_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Activates a subscription directly from an admin notification button."""
    query = update.callback_query
    await query.answer("⏳ جاري تفعيل الاشتراك...")
    
    try:
        _, _, user_id_str, package_key = query.data.split("_")
        user_id = int(user_id_str)

        package = config.SUBSCRIPTION_PACKAGES.get(package_key)
        if not package:
            await query.edit_message_text(f"❌ خطأ: الباقة '{package_key}' لم تعد موجودة.")
            return config.ADMIN_PANEL

        target_user = database._get_user_from_db(user_id)
        if not target_user:
            await query.edit_message_text(f"❌ خطأ: المستخدم `{user_id}` غير موجود.")
            return config.ADMIN_PANEL

        # تطبيق المميزات
        target_user["tokens"] += package["tokens"]
        target_user["subscription_limit"] += package["file_limit"]
        database._update_user_in_db(user_id, target_user)

        # تحديث رسالة الإشعار لتأكيد التفعيل
        await query.edit_message_text(
            f"✅ **تم التفعيل بنجاح** ✅\n\n"
            f"**المستخدم:** {target_user['name']}\n"
            f"**الباقة:** {package['name']}"
        )

        # إشعار المستخدم
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🎉 تهانينا! تم تفعيل **{package['name']}** لحسابك بنجاح.\n\n"
                 f"تمت إضافة **{package['tokens']:,}** توكنز لرصيدك.\n"
                 "شكراً لدعمك!"
        )
    except Exception as e:
        logger.error(f"Error activating sub from button: {e}")
        await query.edit_message_text("❌ حدث خطأ فني أثناء التفعيل.")
        
    return config.ADMIN_PANEL
async def admin_send_welcome_gif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = database.get_all_user_ids()
    for uid in users:
        try:
            with open("welcome.gif", "rb") as gif:
                await context.bot.send_animation(uid, gif, caption="👋 مرحبًا بك في أقوى بوت تعليمي!")
        except Exception:
            continue
    await update.effective_message.reply_text("✅ تم إرسال رسالة ترحيب متحركة.")
    database.log_admin_action("ترحيب متحرك")

# مراجعة أكثر المستخدمين تفاعلاً
async def admin_top_active_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = database.get_all_users_detailed()
    top_users = sorted(users, key=lambda u: u.get('files_processed', 0), reverse=True)[:10]
    msg = beautify_text("🔥 أكثر 10 مستخدمين تفاعلاً:\n" + "\n".join([f"{i+1}. {u['name']} - {u.get('files_processed', 0)} ملف" for i, u in enumerate(top_users)]))
    await update.effective_message.reply_text(msg)
    database.log_admin_action("مراجعة الأكثر تفاعلاً")

# إرسال اقتباس يومي تلقائي
async def admin_daily_quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quotes = [
        "💡 العلم نور، والجهل ظلام.",
        "🚀 لا يوجد مستحيل مع الإرادة.",
        "📚 المذاكرة طريق النجاح.",
        "🌟 كل يوم فرصة جديدة للتعلم.",
        "🧠 الذكاء في الاستمرار، لا في البداية فقط."
    ]
    quote = random.choice(quotes)
    users = database.get_all_user_ids()
    for uid in users:
        try:
            await context.bot.send_message(uid, quote)
        except Exception:
            continue
    await update.effective_message.reply_text("✅ تم إرسال اقتباس يومي.")
    database.log_admin_action("اقتباس يومي")
async def handle_admin_pick_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Accept a user ID after pressing admin_pick_user_by_id and show user controls."""
    raw = (update.message.text or '').strip()
    if not raw.isdigit():
        await update.message.reply_text("⚠️ أدخل ID رقمي صحيح.")
        return config.ADMIN_PICK_USER
    uid = int(raw)
    user = database._get_user_from_db(uid)
    if not user:
        await update.message.reply_text("❌ لم يتم العثور على المستخدم.")
        return config.ADMIN_PICK_USER
    msg = beautify_text(f"👤 {safe_md(user.get('name','N/A'))}\nID: `{uid}`\nالنقاط: {user.get('tokens',0)}\nالملفات: {user.get('files_processed',0)}")
    await update.message.reply_text(msg, reply_markup=keyboards.admin_user_view_kb(uid), parse_mode=ParseMode.MARKDOWN)
    return config.ADMIN_PANEL

# --- ✨✨ تم تعديل هذه الدالة بالكامل لتحل مشكلة زر الرجوع بشكل نهائي ✨✨ ---
async def admin_exit_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
     تنهي محادثة الأدمن بشكل صحيح وتعرض القائمة الرئيسية.
    """
    query = update.callback_query
    await query.answer()
    
    # استدعاء دالة start_cmd الأصلية لعرض القائمة الرئيسية
    # هذا سيضمن أن الرسالة يتم تعديلها بشكل صحيح وأن الحالة تنتقل للمحادثة الرئيسية
    await start_cmd(update, context)
    
    # إنهاء محادثة الأدمن الحالية
    return ConversationHandler.END