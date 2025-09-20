# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# --- إعدادات البوت الأساسية ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "").strip()
TELEGRAPH_ACCESS_TOKEN = os.getenv("TELEGRAPH_ACCESS_TOKEN", "").strip() or None


# --- إعدادات الأدمن والمستخدمين ---
_admin_env = os.getenv("ADMIN_USER_IDS", "").strip()
if _admin_env:
    ADMIN_USER_IDS = [int(x) for x in _admin_env.split(",") if x.strip().isdigit()]
else:
    ADMIN_USER_IDS = [123456789] # <--- ضع الـ ID الخاص بك هنا كقيمة افتراضية

BOT_LINK = "t.me/AI_study1_bot"
DATABASE_FILE = os.getenv("DATABASE_FILE", "bot_data.sqlite3")


# --- إعدادات منطق البوت وحدود الاستخدام ---
DEFAULT_USER_TOKENS = int(os.getenv("DEFAULT_USER_TOKENS", 66666))
FREE_TIER_FILE_LIMIT = int(os.getenv("FREE_TIER_FILE_LIMIT", 5))
MAX_QUIZ_QUESTIONS = 50
MAX_TEXT_CHARS = 120_000


# --- حالات المحادثة (Conversation States) ---
# Main Conversation States
(
    WAITING_INPUT, MAIN_MENU, DOCUMENT_QA_MODE,
    WAITING_ADMIN_CONTACT, WAITING_BUG_REPORT # حالة انتظار رسالة المستخدم للإدارة
) = range(5)

# Admin Conversation States
(
    ADMIN_PANEL, ADMIN_BROADCAST_WAIT, ADMIN_PICK_USER,
    ADMIN_DM_WAIT, ADMIN_SET_CHANNEL_WAIT, CONTACT_ADMIN, 
    ADMIN_CREDIT_SUB_WAIT,
    
    # ✨ --- [التعديل هنا] إضافة الحالات الجديدة --- ✨
    ADMIN_SET_TOKENS_WAIT, ADMIN_SET_SUBS_WAIT 

) = range(100, 109)

# Quiz Conversation States
QZ_MENU, QZ_SETTINGS, QZ_RUNNING = range(200, 203)

# Library Conversation States
LIB_MAIN, LIB_FOLDER_VIEW, LIB_ITEM_VIEW, LIB_CREATE_FOLDER, LIB_MOVE_ITEM, LIB_SEARCH = range(300, 306)


# --- شخصيات الذكاء الاصطناعي ---
AI_PERSONAS = {
    "professor": "an academic university professor who explains things with precision and depth",
    "friend": "a friendly and helpful study partner who simplifies concepts and uses encouraging language",
    "coach": "a motivational coach who focuses on key takeaways, action items, and achieving goals"
}


# --- قسم الاشتراكات والدفع ---
# ⚠️⚠️⚠️ هام: قم بتغيير هذه القيم إلى بياناتك الصحيحة ⚠️⚠️⚠️
VODAFONE_CASH_NUMBER = "01009275685"  # <--- ✏️ غيّر هذا الرقم إلى رقم فودافون كاش الخاص بك
ADMIN_SUPPORT_USERNAME = "@D_O_L_K" # <--- ✏️ غيّر هذا إلى يوزر حسابك الذي سيتواصل معه المستخدمون

# تعريف باقات الاشتراك
SUBSCRIPTION_PACKAGES = {
    "bronze": {
        "name": "🥉 الباقة البرونزية",
        "price": 50,
        "tokens": 50000,
        "file_limit": 100,
    },
    "silver": {
        "name": "🥈 الباقة الفضية",
        "price": 100,
        "tokens": 120000,
        "file_limit": 250,
    },
    "gold": {
        "name": "🥇 الباقة الذهبية",
        "price": 150,
        "tokens": 200000,
        "file_limit": 500,
    },
    "platinum": {
        "name": "💎 الباقة البلاتينية",
        "price": 200,
        "tokens": 300000,
        "file_limit": 1000,
    },
}