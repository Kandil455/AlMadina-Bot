from flask import Flask, render_template
app = Flask(__name__)

@app.route("/")
def dashboard():
    # اعرض إحصائيات المستخدمين والعمليات
    return render_template("dashboard.html")