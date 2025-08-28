# keyboards.py
import config
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from typing import Dict, Any

def main_menu_kb(user: Dict[str, Any]) -> InlineKeyboardMarkup:
    """
    Generates the main menu keyboard.
    It's dynamic: shows an admin button only to admins and includes support/contact/report.
    """
    keyboard = [
        [InlineKeyboardButton("📝 ملخص جديد", callback_data="summarize"), InlineKeyboardButton("💡 شرح فكرة", callback_data="explain")],
        [InlineKeyboardButton("🧠 خريطة ذهنية", callback_data="mindmap"), InlineKeyboardButton("🎲 اختبار ذكي", callback_data="quiz")],
        [InlineKeyboardButton("📚 مكتبتي", callback_data="library"), InlineKeyboardButton("⭐ ترقية الاشتراك", callback_data="subscribe")],
        
        # ✨ --- تم إرجاع هذه الأزرار المهمة --- ✨
        [InlineKeyboardButton("🐞 إبلاغ عن مشكلة", callback_data="report_issue"), InlineKeyboardButton("📨 تواصل مع الإدارة", callback_data="contact_admin")],
        [InlineKeyboardButton("📊 إحصائياتي", callback_data="stats")]
    ]

    # Add the Admin Panel button only if the user is an admin
    if user.get("is_admin", False):
        keyboard.append([InlineKeyboardButton("👑 لوحة التحكم", callback_data="act_admin")])

    return InlineKeyboardMarkup(keyboard)

def back_to_menu_kb() -> InlineKeyboardMarkup:
    """A simple keyboard to go back to the main menu."""
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع للقائمة الرئيسية", callback_data="act_back_to_menu")]])

def quiz_cancel_kb() -> InlineKeyboardMarkup:
    """A simple keyboard to cancel a running quiz."""
    return InlineKeyboardMarkup([[InlineKeyboardButton("⏹️ إلغاء الكويز وإنهاء المحاولة", callback_data="qz_cancel")]])

def productivity_features_kb() -> InlineKeyboardMarkup:
    """Combined keyboard for all extra/production features."""
    keyboard = [
        [InlineKeyboardButton("📝 نص → PDF", callback_data="feature_text_to_pdf"), InlineKeyboardButton("🖼️ نص → صورة", callback_data="feature_text_to_image")],
        [InlineKeyboardButton("🔎 OCR (قراءة نص من صورة)", callback_data="feature_ocr"), InlineKeyboardButton("📄 تلخيص PDF", callback_data="feature_summarize_pdf")],
        [InlineKeyboardButton("📽️ توليد شرائح PPTX", callback_data="feature_make_pptx"), InlineKeyboardButton("⬇️ تنزيل فيديو/صوت", callback_data="feature_download_media")],
        [InlineKeyboardButton("🏆 إنجازاتي", callback_data="feature_achievements"), InlineKeyboardButton("🏅 الأكثر تفاعلاً", callback_data="feature_leaderboard")],
        [InlineKeyboardButton("💡 اقتباس تحفيزي", callback_data="feature_quote"), InlineKeyboardButton("🎯 هدف الأسبوع", callback_data="feature_weekly_goal")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="act_back_to_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def language_style_kb() -> InlineKeyboardMarkup:
    """Keyboard for selecting the language style for summaries and explanations."""
    keyboard = [
        [InlineKeyboardButton("🇬🇧 English Only", callback_data="style_en")],
        [InlineKeyboardButton("🇬🇧/🇦🇪 Bilingual (انجليزي مع شرح عربي)", callback_data="style_bilingual")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="act_back_to_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def ask_for_phone_kb() -> ReplyKeyboardMarkup:
    """Keyboard to request user's contact information."""
    keyboard = [[KeyboardButton("📱 مشاركة رقم هاتفي 📱", request_contact=True)]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def subscribe_kb() -> InlineKeyboardMarkup:
    """Keyboard for subscription options."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Month 🟢", callback_data="sub_monthly"),
            InlineKeyboardButton("Term 🟡", callback_data="sub_term"),
            InlineKeyboardButton("Year 🔵", callback_data="sub_year"),
        ],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="act_back_to_menu")],
    ])

def rewrite_tones_kb() -> InlineKeyboardMarkup:
    """Keyboard for selecting a rewrite tone."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Simpler", callback_data="tone_simple"),
            InlineKeyboardButton("More Formal", callback_data="tone_formal"),
            InlineKeyboardButton("For a 10‑year‑old", callback_data="tone_kid10"),
        ],
        [
            InlineKeyboardButton("Persuasive", callback_data="tone_persuasive"),
            InlineKeyboardButton("Academic", callback_data="tone_academic"),
        ],
        [InlineKeyboardButton("Custom…", callback_data="tone_custom")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="act_back_to_menu")],
    ])


# ==================================
# ======= Library Keyboards ========
# ==================================

def library_main_kb(user: dict) -> InlineKeyboardMarkup:
    """Main keyboard for the smart library, showing folders."""
    folders = user.get("library", {}).get("folders", {})
    rows = [[InlineKeyboardButton(f"{folder_data['name']} ({len(folder_data.get('items', []))})", callback_data=f"lib_open_{folder_id}")] for folder_id, folder_data in folders.items()]
    rows.extend([
        [InlineKeyboardButton("➕ إنشاء مجلد جديد", callback_data="lib_new_folder")],
        [InlineKeyboardButton("🔍 بحث في المكتبة", callback_data="lib_search")],
        [InlineKeyboardButton("⬅️ رجوع للقائمة الرئيسية", callback_data="act_back_to_menu")]
    ])
    return InlineKeyboardMarkup(rows)

def library_folder_kb(user: dict, folder_id: str) -> InlineKeyboardMarkup:
    """Keyboard for viewing items within a specific folder."""
    library = user.get("library", {})
    folder = library.get("folders", {}).get(folder_id, {})
    item_ids = folder.get("items", [])
    rows = []
    for item_id in item_ids:
        item = library.get("items", {}).get(item_id)
        if item:
            icon = {"summary": "📝", "explanation": "📚", "mindmap_live": "🧠", "quiz": "❓", "presentation": "📽️"}.get(item["type"], "📄")
            rows.append([InlineKeyboardButton(f"{icon} {item['title'][:40]}", callback_data=f"lib_view_{item_id}")])
    rows.append([InlineKeyboardButton("⬅️ رجوع إلى المجلدات", callback_data="lib_main")])
    return InlineKeyboardMarkup(rows)
    
def library_item_kb(item_id: str) -> InlineKeyboardMarkup:
    """Keyboard for actions on a specific library item."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 نقل لمجلد آخر", callback_data=f"lib_move_{item_id}"),
            InlineKeyboardButton("🗑️ حذف", callback_data=f"lib_del_{item_id}")
        ],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="lib_back_folder")]
    ])

def library_move_kb(user: dict, item_id: str) -> InlineKeyboardMarkup:
    """Keyboard to select a destination folder for moving an item."""
    folders = user.get("library", {}).get("folders", {})
    rows = [[InlineKeyboardButton(f"📥 إلى: {folder_data['name']}", callback_data=f"lib_moveto_{item_id}_{folder_id}")] for folder_id, folder_data in folders.items()]
    rows.append([InlineKeyboardButton("❌ إلغاء النقل", callback_data=f"lib_view_{item_id}")])
    return InlineKeyboardMarkup(rows)


# ==================================
# ========= Quiz Keyboards =========
# ==================================

def quiz_menu_kb() -> InlineKeyboardMarkup:
    """Main menu for the quiz feature."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 ابدأ الكويز (10 أسئلة)", callback_data="qz_start_10")],
        [InlineKeyboardButton("🚀 ابدأ الكويز (20 سؤال)", callback_data="qz_start_20")],
        [InlineKeyboardButton("⚙️ إعدادات الكويز", callback_data="qz_settings")],
        [InlineKeyboardButton("⬅️ رجوع للقائمة الرئيسية", callback_data="act_back_to_menu")]
    ])

def quiz_settings_kb(prefs: dict) -> InlineKeyboardMarkup:
    """Keyboard for configuring quiz settings."""
    timer_map = {0: "بدون مؤقت", 15: "15 ثانية", 30: "30 ثانية", 60: "60 ثانية"}
    timer_text = timer_map.get(prefs.get("timer", 30), f"{prefs.get('timer', 30)} ثانية")
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⏱️ المؤقت: {timer_text}", callback_data="qz_set_timer")],
        [
            InlineKeyboardButton(f"🔀 خلط الأسئلة: {'✅' if prefs.get('shuffle_questions') else '❌'}", callback_data="qz_toggle_shuffle_q"),
            InlineKeyboardButton(f"🔀 خلط الخيارات: {'✅' if prefs.get('shuffle_choices') else '❌'}", callback_data="qz_toggle_shuffle_c")
        ],
        [InlineKeyboardButton(f"🧠 إظهار الشرح: {'✅' if prefs.get('show_explanations') else '❌'}", callback_data="qz_toggle_expl")],
        [InlineKeyboardButton(f"🔁 إعادة المحاولة: {'✅' if prefs.get('retry_incorrect') else '❌'}", callback_data="qz_toggle_retry")],
        [InlineKeyboardButton("⬅️ رجوع إلى قائمة الكويز", callback_data="quiz")]
    ])
# في ملف keyboards.py

def quiz_results_kb(quiz_state: dict) -> InlineKeyboardMarkup:
    """Keyboard displayed on the quiz results screen."""
    rows = []
    # زر مراجعة الإجابات (يظهر دائماً)
    rows.append([InlineKeyboardButton("🧐 مراجعة كل الإجابات", callback_data="qz_review")])

    # زر إعادة حل الأسئلة الخاطئة (يظهر فقط لو فيه أسئلة غلط)
    incorrect_unskipped = [i for i in quiz_state.get('incorrect_indices', []) if i not in quiz_state.get('skipped_indices', [])]
    if quiz_state.get("retry_incorrect") and incorrect_unskipped:
        rows.append([InlineKeyboardButton("🔁 حل الأسئلة الخاطئة فقط", callback_data="qz_retry_wrong")])
    
    rows.extend([
        [InlineKeyboardButton("🔝 ابدأ كويز جديد", callback_data="quiz")],
        [InlineKeyboardButton("⬅️ رجوع للقائمة الرئيسية", callback_data="act_back_to_menu")]
    ])
    return InlineKeyboardMarkup(rows)
# ==================================
# ======== Admin Keyboards =========
# ==================================

def admin_panel_kb() -> InlineKeyboardMarkup:
    """Main keyboard for the admin panel."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 إحصائيات", callback_data="admin_stats"), InlineKeyboardButton("🚨 البلاغات", callback_data="admin_reports")],
        [InlineKeyboardButton("📢 بث رسالة", callback_data="admin_broadcast")],
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_users")],
        [InlineKeyboardButton("💬 إرسال رسالة خاصة", callback_data="admin_dm_start")],
        [InlineKeyboardButton("⚙️ إعدادات البوت", callback_data="admin_settings")],
        [InlineKeyboardButton("⬅️ رجوع للقائمة الرئيسية", callback_data="act_back_to_menu")]
    ])

def admin_settings_kb(current_channel: str) -> InlineKeyboardMarkup:
    """Keyboard for bot settings in the admin panel."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✍️ تعديل قناة الاشتراك", callback_data="admin_set_channel")],
        [InlineKeyboardButton("⬅️ رجوع للوحة التحكم", callback_data="act_admin")]
    ])

def admin_user_list_kb(page: int, total_users: int, items_per_page: int) -> InlineKeyboardMarkup:
    """Pagination keyboard for the user list in the admin panel."""
    keyboard_rows = []
    pagination_buttons = []
    if page > 0:
        pagination_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"admin_users_page_{page-1}"))
    if (page + 1) * items_per_page < total_users:
        pagination_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=f"admin_users_page_{page+1}"))
    
    if pagination_buttons:
        keyboard_rows.append(pagination_buttons)
    
    keyboard_rows.append([InlineKeyboardButton("✍️ تعديل بيانات مستخدم (أدخل ID)", callback_data="admin_pick_user_by_id")])
    keyboard_rows.append([InlineKeyboardButton("⬅️ رجوع للوحة التحكم", callback_data="act_admin")])
    return InlineKeyboardMarkup(keyboard_rows)

def admin_user_view_kb(target_id: int) -> InlineKeyboardMarkup:
    """Keyboard for managing a specific user in the admin panel."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ +100 Tokens", callback_data=f"admin_tokens_inc_{target_id}"),
         InlineKeyboardButton("➖ -100 Tokens", callback_data=f"admin_tokens_dec_{target_id}")],
        [InlineKeyboardButton("✍️ Set Tokens", callback_data=f"admin_tokens_set_{target_id}")],
        [InlineKeyboardButton("📦 Set Free Limit", callback_data=f"admin_subs_set_{target_id}")],
        [InlineKeyboardButton("🚫 حظر/رفع حظر", callback_data=f"admin_ban_toggle_{target_id}")],
        [InlineKeyboardButton("💬 أرسل رسالة له", callback_data=f"admin_dm_user_{target_id}")],
        [InlineKeyboardButton("⬅️ رجوع لقائمة المستخدمين", callback_data="admin_users")]
    ])
def subscriptions_menu_kb() -> InlineKeyboardMarkup:
    """Generates the keyboard for subscription packages."""
    keyboard = []
    # إنشاء زر لكل باقة من ملف الكونفيج
    for key, package in config.SUBSCRIPTION_PACKAGES.items():
        text = f"{package['name']} - {package['price']} جنيه"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"sub_package_{key}")])
    
    keyboard.append([InlineKeyboardButton("⬅️ رجوع للقائمة الرئيسية", callback_data="act_back_to_menu")])
    return InlineKeyboardMarkup(keyboard)

def payment_instructions_kb(package_key: str) -> InlineKeyboardMarkup:
    """Shows the payment instructions and confirmation button."""
    keyboard = [
        [InlineKeyboardButton("✅ لقد قمت بالتحويل", callback_data=f"payment_sent_{package_key}")],
        [InlineKeyboardButton("⬅️ اختيار باقة أخرى", callback_data="subscribe")]
    ]
    return InlineKeyboardMarkup(keyboard)
def admin_subscription_activation_kb(user_id: int, package_key: str) -> InlineKeyboardMarkup:
    """Creates a button for the admin to directly activate a user's subscription."""
    keyboard = [[
        InlineKeyboardButton(
            "✅ تفعيل الاشتراك الآن",
            callback_data=f"admin_activate_sub_{user_id}_{package_key}"
        )
    ]]
    return InlineKeyboardMarkup(keyboard)