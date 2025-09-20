# admin_panel.py
"""
لوحة تحكم ويب للأدمن (اختيارية)
لتشغيلها: python admin_panel.py
ثم افتح المتصفح على http://localhost:8080
"""
from flask import Flask, render_template_string, send_file, jsonify
import csv
import io
import logging
from datetime import datetime

# --- محاولة استيراد ملف قاعدة البيانات ---
try:
    import database
    DATABASE_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  WARNING: Could not import 'database.py'. Some features will be disabled. Error: {e}")
    DATABASE_AVAILABLE = False
    # تعريف دوال وهمية علشان الكود ما يطلعش أخطاء
    class DummyDatabase:
        @staticmethod
        def get_bot_stats():
            return {"users": 0, "files_processed": 0, "total_tokens_used": 0, "top_feature": "N/A"}
        @staticmethod
        def get_all_users_detailed():
            return []
    database = DummyDatabase()

# --- إعداد التسجيل (Logging) ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- دالة مساعدة للتعامل مع القيم الغير موجودة ---
def safe_get(d, key, default=""):
    """يحصل على قيمة من قاموس بأمان، ويرجع قيمة افتراضية لو مش موجودة."""
    return d.get(key, default) if isinstance(d, dict) else default

# --- قالب HTML للوحة التحكم ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>لوحة تحكم الأدمن - Al Madina Bot</title>
    <style>
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            margin: 0; 
            padding: 20px; 
            background-color: #f0f2f5; 
            color: #333; 
        }
        .container { 
            max-width: 1200px; 
            margin: auto; 
            background: white; 
            padding: 25px; 
            border-radius: 10px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
        }
        h1, h2, h3 { 
            color: #2c3e50; 
            margin-top: 0; 
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #eee;
            padding-bottom: 15px;
            margin-bottom: 25px;
        }
        .stats-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
            gap: 20px; 
            margin-bottom: 30px; 
        }
        .stat-card { 
            background: #e3f2fd; 
            padding: 20px; 
            border-radius: 8px; 
            text-align: center; 
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .stat-card h3 { 
            margin: 0 0 10px 0; 
            color: #1976d2; 
            font-size: 1.1em;
        }
        .stat-card p { 
            font-size: 2em; 
            font-weight: bold; 
            margin: 0; 
            color: #0d47a1; 
        }
        table { 
            width: 100%; 
            border-collapse: collapse; 
            margin-top: 20px; 
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border-radius: 8px;
            overflow: hidden;
        }
        th, td { 
            border: 1px solid #ddd; 
            padding: 12px; 
            text-align: right; 
        }
        th { 
            background-color: #1976d2; 
            color: white; 
        }
        tr:nth-child(even) { 
            background-color: #f9f9f9; 
        }
        tr:hover {
            background-color: #f1f8ff;
        }
        a { 
            display: inline-block; 
            margin: 10px 0; 
            padding: 12px 24px; 
            background-color: #1976d2; 
            color: white; 
            text-decoration: none; 
            border-radius: 5px; 
            font-weight: bold;
            transition: background-color 0.3s;
        }
        a:hover { 
            background-color: #0d47a1; 
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }
        .export-section {
            background-color: #e8f5e9;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
        }
        .footer { 
            margin-top: 30px; 
            text-align: center; 
            color: #7f8c8d; 
            font-size: 0.9em; 
            padding-top: 20px;
            border-top: 1px solid #eee;
        }
        .warning {
            background-color: #fff8e1;
            padding: 15px;
            border-radius: 5px;
            border-left: 5px solid #ffc107;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>👑 لوحة تحكم الأدمن - Al Madina Bot</h1>
            <div>📅 {{ now }}</div>
        </div>
        
        {% if not database_available %}
        <div class="warning">
            ⚠️ <strong>تحذير:</strong> ملف <code>database.py</code> مش متاح. الإحصائيات المعروضة بيانات تجريبية.
        </div>
        {% endif %}

        <h2>📊 الإحصائيات العامة</h2>
        <div class="stats-grid">
            <div class="stat-card">
                <h3>عدد المستخدمين</h3>
                <p>{{ "{:,}".format(stats.users) }}</p>
            </div>
            <div class="stat-card">
                <h3>عدد الملفات المُعالجة</h3>
                <p>{{ "{:,}".format(stats.files_processed) }}</p>
            </div>
            <div class="stat-card">
                <h3>إجمالي التوكنز المستخدمة</h3>
                <p>{{ "{:,}".format(stats.total_tokens_used) }}</p>
            </div>
            <div class="stat-card">
                <h3>أكثر ميزة استخدامًا</h3>
                <p>{{ stats.top_feature or "غير محدد" }}</p>
            </div>
        </div>

        <div class="export-section">
            <h2>📥 تصدير البيانات</h2>
            <a href="/export_users">⬇️ تحميل ملف المستخدمين (CSV)</a>
        </div>

        <h2>🏅 أكثر 10 مستخدمين تفاعلاً</h2>
        {% if top_users %}
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>الاسم</th>
                    <th>ID</th>
                    <th>رقم الهاتف</th>
                    <th>التوكنز</th>
                    <th>الملفات المُعالجة</th>
                </tr>
            </thead>
            <tbody>
                {% for user in top_users %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td>{{ safe_get(user, 'name') }}</td>
                    <td>{{ safe_get(user, 'id') }}</td>
                    <td>{{ safe_get(user, 'phone_number') or "غير متوفر" }}</td>
                    <td>{{ "{:,}".format(safe_get(user, 'tokens', 0)) }}</td>
                    <td>{{ "{:,}".format(safe_get(user, 'files_processed', 0)) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p>لا توجد بيانات مستخدمين لعرضها.</p>
        {% endif %}

        <div class="footer">
            <p>تم إنشاؤه بواسطة Al Madina Bot | 📅 {{ now }}</p>
        </div>
    </div>
</body>
</html>
"""

@app.route("/")
def dashboard():
    """الصفحة الرئيسية للوحة التحكم."""
    try:
        # 1. جلب الإحصائيات
        # افتراض أن database.get_bot_stats() بترجع قاموس
        stats = database.get_bot_stats() 
        # لو الفانكشن مش موجودة أو بترجع حاجة تانية، نستخدم قيمة افتراضية
        if not isinstance(stats, dict):
            stats = {
                "users": 0,
                "files_processed": 0,
                "total_tokens_used": 0,
                "top_feature": "غير محدد"
            }

        # 2. جلب بيانات المستخدمين
        users = database.get_all_users_detailed() # افتراض إنها بترجع list of dicts
        if not isinstance(users, list):
            users = []
        
        # 3. ترتيب المستخدمين حسب عدد الملفات المُعالجة (من الأعلى للأدنى)
        top_users = sorted(users, key=lambda u: safe_get(u, 'files_processed', 0), reverse=True)[:10]

        # 4. عرض الصفحة باستخدام القالب
        return render_template_string(
            HTML_TEMPLATE,
            stats=stats,
            top_users=top_users,
            now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            safe_get=safe_get, # نمرر الدالة للقالب
            database_available=DATABASE_AVAILABLE
        )
    except Exception as e:
        logger.error(f"Error in dashboard route: {e}")
        return f"<h1>⚠️ حدث خطأ</h1><p>{str(e)}</p>", 500

@app.route("/export_users")
def export_users():
    """تصدير بيانات المستخدمين لملف CSV."""
    try:
        if not DATABASE_AVAILABLE:
            return "<h1>⚠️ الخدمة غير متوفرة</h1><p>ملف قاعدة البيانات غير متاح.</p>", 500
            
        users = database.get_all_users_detailed()
        if not isinstance(users, list):
            users = []

        # إنشاء ملف CSV في الذاكرة
        output = io.StringIO()
        writer = csv.DictWriter(
            output, 
            fieldnames=["id", "name", "phone_number", "tokens", "files_processed", "subscription_limit"],
            extrasaction='ignore' # يتجاهل الحقول الزايده
        )
        writer.writeheader()
        for u in users:
            if isinstance(u, dict):
                # نتأكد إن البيانات صح قبل ما نكتبها
                row = {
                    "id": safe_get(u, 'id'),
                    "name": safe_get(u, 'name'),
                    "phone_number": safe_get(u, 'phone_number') or "",
                    "tokens": safe_get(u, 'tokens', 0),
                    "files_processed": safe_get(u, 'files_processed', 0),
                    "subscription_limit": safe_get(u, 'subscription_limit', 0),
                }
                writer.writerow(row)

        # تحويل البيانات لبايت علشان Flask يقدر يتعامل معاها
        mem = io.BytesIO()
        mem.write(output.getvalue().encode('utf-8-sig')) # UTF-8 with BOM for Excel
        mem.seek(0)
        output.close()

        return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
    except Exception as e:
        logger.error(f"Error exporting users: {e}")
        return f"<h1>⚠️ حدث خطأ في التصدير</h1><p>{str(e)}</p>", 500

# --- نقطة تشغيل السكريبت ---
if __name__ == "__main__":
    logger.info("جارٍ تشغيل لوحة تحكم الأدمن على http://localhost:8080")
    
    # محاولة استدعاء دالة إعداد قاعدة البيانات لو موجودة
    if DATABASE_AVAILABLE:
        try:
            if hasattr(database, 'setup_database'):
                database.setup_database()
                logger.info("قاعدة البيانات جاهزة.")
            else:
                logger.info("ملف قاعدة البيانات تم استيراده، لكن دالة setup_database() مش موجودة.")
        except Exception as e:
            logger.warning(f"مشكلة في إعداد قاعدة البيانات: {e}")
    else:
        logger.warning("ملف قاعدة البيانات مش متاح. سيتم عرض بيانات تجريبية.")
        
    app.run(host='127.0.0.1', port=8080, debug=True)
