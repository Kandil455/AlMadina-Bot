# utils.py
import re
import math
import uuid
import datetime as dt
from typing import Dict, Any, Optional
import database # استيراد للوصول لبيانات المستخدم

LANGS = {
    "ar": {
        "welcome": "👋 مرحبًا بك في البوت الذكي!",
        "help": "أرسل لي أي ملف أو نص وسأساعدك بأحدث تقنيات الذكاء الاصطناعي.",
        "reminder": "⏰ تذكير: يمكنك الآن تجربة ميزة جديدة في البوت!",
        "error": "⚠️ حدث خطأ غير متوقع. إذا تكرر الخطأ تواصل مع الدعم."
    },
    "en": {
        "welcome": "👋 Welcome to the Smart Bot!",
        "help": "Send me any file or text and I'll help you with the latest AI technologies.",
        "reminder": "⏰ Reminder: You can now try a new feature in the bot!",
        "error": "⚠️ An unexpected error occurred. If it happens again, contact support."
    }
}

def safe_md(text: str) -> str:
    if not text: return ""
    return re.sub(r'([_*`])', r'\\\1', text)

def shorten(s: str, n: int = 400) -> str:
    s = s.strip()
    return (s[:n] + "…") if len(s) > n else s

def now_iso() -> str:
    return dt.datetime.utcnow().isoformat()

def format_tokens(user: Dict[str, Any]) -> str:
    if user.get("is_admin"): return "∞"
    return f"{user['tokens']:,}"

def user_freetier_allowed(user: Dict[str, Any]) -> bool:
    if user.get("is_admin"): return True
    return user["files_processed"] < user.get("subscription_limit", 5)

def inc_files_processed(user: Dict[str, Any]):
    if not user.get("is_admin"):
        user["files_processed"] += 1
    database._update_user_in_db(user['id'], user) # تحديث فوري

def add_library_item(user: Dict[str, Any], type_: str, title: str, content: Any, folder_id: str = "default", extra: Optional[Dict[str, Any]] = None) -> str:
    item_id = str(uuid.uuid4())
    library = user["library"]
    
    library["items"][item_id] = {
        "id": item_id, "type": type_, "title": title, "content": content,
        "ts": now_iso(), "extra": extra or {},
    }
    
    if folder_id in library["folders"]:
        library["folders"][folder_id]["items"].append(item_id)
    else:
        library["folders"]["default"]["items"].append(item_id)
        
    database._update_user_in_db(user['id'], user) # تحديث فوري
    return item_id

def token_estimate(ch_count: int) -> int:
    return max(1, math.ceil(ch_count / 4))

def cost_for_operation(op: str, ch_count: int) -> int:
    base = token_estimate(ch_count)
    weights = {
        "summarize": 1.0, "explain": 1.1, "key_concepts": 1.0,
        "quiz_generate": 1.6, "tutor_chat": 1.0, "presentation": 1.5,
        "mindmap": 1.3, "rewrite": 1.0, "exam_questions": 1.6,
        "study_plan": 1.2, "vision_extract": 0.9,
    }
    w = weights.get(op, 1.0)
    return max(1, int(base * w))

async def deduct_tokens(user: Dict[str, Any], op: str, ch_count: int) -> bool:
    if user.get("is_admin"): return True
    cost = cost_for_operation(op, ch_count)
    if user["tokens"] >= cost:
        user["tokens"] -= cost
        database._update_user_in_db(user['id'], user) # تحديث فوري
        return True
    return False

def get_user_lang(user: dict) -> str:
    return user.get("lang", "ar")

def t(key: str, user: dict) -> str:
    lang = get_user_lang(user)
    return LANGS.get(lang, LANGS["ar"]).get(key, key)

def beautify_text(text: str) -> str:
    """تجميل النص بإضافة رموز وتنسيق Markdown تلقائي."""
    text = text.replace("ملخص", "📝 ملخص").replace("شرح", "💡 شرح")
    text = text.replace("خريطة ذهنية", "🧠 خريطة ذهنية").replace("اختبار", "🎲 اختبار")
    return f"✨ {text.strip()} ✨"

async def send_rich_message(bot, chat_id, text, user=None, **kwargs):
    """إرسال رسالة غنية تلقائياً حسب لغة المستخدم وتجميل النص."""
    if user:
        text = t(text, user)
    text = beautify_text(text)
    await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", **kwargs)