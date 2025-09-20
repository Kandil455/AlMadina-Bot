# database.py
import sqlite3
import json
import logging
import config
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

def setup_database():
    """ينشئ جداول قاعدة البيانات إذا لم تكن موجودة."""
    conn = sqlite3.connect(config.DATABASE_FILE)
    cursor = conn.cursor()
    
    # جدول المستخدمين
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        name TEXT,
        phone_number TEXT,
        tokens INTEGER DEFAULT 0,
        subscription_limit INTEGER DEFAULT 5,
        files_processed INTEGER DEFAULT 0,
        session TEXT, -- لتخزين بيانات الجلسة كـ JSON
        library TEXT  -- لتخزين المكتبة كـ JSON
    )''')
    
    # جدول الإعدادات العامة
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')

    # جدول سجلات الأدمن (مهم للأحداث)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP,
        action TEXT,
        details TEXT
    )''')

    conn.commit()
    conn.close()
    logger.info("Database setup complete.")

def _get_user_from_db(user_id: int) -> Optional[dict]:
    """يسترجع بيانات مستخدم واحد من قاعدة البيانات."""
    conn = sqlite3.connect(config.DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user_row = cursor.fetchone()
    conn.close()
    if user_row:
        user_dict = dict(user_row)
        user_dict['session'] = json.loads(user_dict.get('session', '{}'))
        user_dict['library'] = json.loads(user_dict.get('library', '{}'))
        return user_dict
    return None

def _update_user_in_db(user_id: int, user_data: dict):
    """يحدّث بيانات مستخدم في قاعدة البيانات."""
    # تحويل القواميس إلى JSON قبل الحفظ
    session_json = json.dumps(user_data.get('session', {}))
    library_json = json.dumps(user_data.get('library', {}))
    
    conn = sqlite3.connect(config.DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE users SET
        name = ?, phone_number = ?, tokens = ?, subscription_limit = ?, 
        files_processed = ?, session = ?, library = ?
    WHERE id = ?
    ''', (
        user_data.get('name'), user_data.get('phone_number'), user_data.get('tokens'),
        user_data.get('subscription_limit'), user_data.get('files_processed'),
        session_json, library_json, user_id
    ))
    conn.commit()
    conn.close()

def ensure_user(user_id: int, name: str) -> Dict[str, Any]:
    """
    يسترجع المستخدم من قاعدة البيانات أو ينشئه إذا لم يكن موجودًا.
    هذه هي الدالة الرئيسية للتعامل مع المستخدمين.
    """
    user = _get_user_from_db(user_id)
    if user:
        # التأكد من وجود الحقول الافتراضية للجلسات القديمة
        user.setdefault('name', name)
        user.setdefault('is_admin', user_id in config.ADMIN_USER_IDS)
        user['session'].setdefault('last_text', '')
        user['session'].setdefault('previews_on', False)
        user['session'].setdefault('quiz', None)
        user.setdefault('library', {"folders": {"default": {"name": "📂 عام", "items": []}}, "items": {}})
        return user

    # مستخدم جديد
    new_user = {
        "id": user_id,
        "name": name,
        "phone_number": None,
        "tokens": config.DEFAULT_USER_TOKENS,
        "subscription_limit": config.FREE_TIER_FILE_LIMIT,
        "files_processed": 0,
        "session": {"last_text": "", "last_source_type": None, "chat_history": [], "quiz": None, "previews_on": False},
        "library": {"folders": {"default": {"name": "📂 عام", "items": []}}, "items": {}},
        "is_admin": user_id in config.ADMIN_USER_IDS,
    }

    session_json = json.dumps(new_user['session'])
    library_json = json.dumps(new_user['library'])

    conn = sqlite3.connect(config.DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO users (id, name, phone_number, tokens, subscription_limit, files_processed, session, library)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id, name, None, new_user['tokens'], new_user['subscription_limit'], 0,
        session_json, library_json
    ))
    conn.commit()
    conn.close()
    
    return new_user

def get_all_user_ids() -> List[int]:
    """يسترجع ID كل المستخدمين للبث."""
    conn = sqlite3.connect(config.DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users")
    ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return ids

def get_settings() -> dict:
    """يقرأ إعدادات البوت من قاعدة البيانات."""
    conn = sqlite3.connect(config.DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    settings = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    settings.setdefault("force_sub_channel", None)
    return settings

def save_settings(settings: dict):
    """يحفظ إعدادات البوت في قاعدة البيانات."""
    conn = sqlite3.connect(config.DATABASE_FILE)
    cursor = conn.cursor()
    for key, value in settings.items():
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_all_users_detailed() -> List[dict]:
    """Return list of users with basic info for admin listing."""
    conn = sqlite3.connect(config.DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, phone_number, tokens, files_processed FROM users ORDER BY id DESC")
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return users


def get_all_users() -> List[dict]:
    """Return minimal user dicts for admin operations."""
    return get_all_users_detailed()

def get_all_users_with_session() -> List[dict]:
    """Return list of users with id and parsed session for broadcasting filters."""
    conn = sqlite3.connect(config.DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, session FROM users")
    rows = cursor.fetchall()
    conn.close()
    users = []
    for row in rows:
        try:
            session = json.loads(row["session"] or "{}")
        except Exception:
            session = {}
        users.append({"id": row["id"], "session": session})
    return users

def find_user(query: str) -> Optional[dict]:
    """Find a user by ID or name (case-insensitive)."""
    conn = sqlite3.connect(config.DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        uid = int(query)
        cursor.execute("SELECT * FROM users WHERE id = ?", (uid,))
    except ValueError:
        cursor.execute("SELECT * FROM users WHERE LOWER(name) LIKE ?", (f"%{query.lower()}%",))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    user = dict(row)
    user['session'] = json.loads(user.get('session', '{}'))
    user['library'] = json.loads(user.get('library', '{}'))
    return user


def get_bot_stats() -> dict:
    """Compute simple bot stats: number of users and total files processed."""
    conn = sqlite3.connect(config.DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(files_processed) FROM users")
    files = cursor.fetchone()[0] or 0
    conn.close()
    return {"users": users, "summaries": files, "top_feature": "ملخصات"}


def log_admin_action(action: str, details: str = "") -> None:
    conn = sqlite3.connect(config.DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO admin_logs (action, details) VALUES (?, ?)", (action, details))
    conn.commit()
    conn.close()


def get_last_logs(limit: int = 10) -> List[str]:
    conn = sqlite3.connect(config.DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT ts, action, details FROM admin_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [f"[{r[0]}] {r[1]} - {r[2]}" for r in rows]
