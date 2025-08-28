# handlers/quiz_handler.py
import logging
import random
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.error import BadRequest

import database
import keyboards
import config
from ai_services import ai_generate_quiz

logger = logging.getLogger(__name__)

# --- Quiz Default Preferences ---
QZ_DEFAULT_PREFS = {
    "timer": 30,
    "shuffle_questions": True,
    "shuffle_choices": True,
    "show_explanations": True,
    "retry_incorrect": True,
}

# --- Helper Functions ---
def _get_quiz_prefs(user: dict) -> dict:
    """Initializes and returns the user's quiz preferences."""
    sess = user.setdefault("session", {})
    prefs = sess.setdefault("quiz_prefs", QZ_DEFAULT_PREFS.copy())
    for k, v in QZ_DEFAULT_PREFS.items():
        prefs.setdefault(k, v)
    return prefs

# --- Core Quiz Logic (Using Polls) ---
async def _display_question(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Fetches user state, displays the current question, or shows final results."""
    user = database._get_user_from_db(user_id)
    if not user or "quiz" not in user.get("session", {}):
        logger.warning(f"Quiz state not found for user {user_id} in _display_question.")
        return

    quiz = user["session"]["quiz"]
    q_idx = quiz["current_q_idx"]
    questions = quiz["questions"]
    total_qs = len(questions)

    # --- Final Results Display ---
    if q_idx >= total_qs:
        score = quiz.get("score", 0)
        percentage = (score / total_qs) * 100 if total_qs > 0 else 0
        grade = "ممتاز! 🥳" if percentage >= 80 else ("جيد جدًا 👍" if percentage >= 60 else "تحتاج للمزيد من المذاكرة 📚")
        text = (
            f"**🏁 نتيجة الكويز**\n\n"
            f"النتيجة: **{score} من {total_qs}** ({percentage:.1f}%)\n"
            f"التقييم: {grade}"
        )
        keyboard = keyboards.quiz_results_kb(quiz)

        # ✨ التحسين: إرسال النتيجة كرسالة جديدة لتظهر في نهاية المحادثة
        await context.bot.send_message(
            chat_id=quiz["chat_id"], text=text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
        )
        
        # ✨ التحسين: حذف الرسالة القديمة "جاري التجهيز..." لتنظيف الشاشة
        message_id = quiz.get("start_message_id")
        if message_id:
            try:
                await context.bot.delete_message(chat_id=quiz["chat_id"], message_id=message_id)
            except Exception:
                pass  # It's okay if deletion fails

        quiz["is_finished"] = True
        database._update_user_in_db(user_id, user)
        return

    # --- Send Question as a Poll ---
    question = questions[q_idx]
    choices = list(question.get("choices", []))
    correct_idx = int(question.get("answer_index", 0))
    
    # حفظ الإجابة الصحيحة الأصلية قبل الخلط (مهم جداً للمراجعة)
    quiz.setdefault("original_correct_indices", {})[q_idx] = correct_idx
    
    if quiz.get("shuffle_choices", True):
        correct_val = choices[correct_idx]
        random.shuffle(choices)
        correct_idx = choices.index(correct_val)

    timer_duration = quiz.get("timer", 0)
    open_period = timer_duration if 5 <= timer_duration <= 600 else None

    try:
        sent_poll_message = await context.bot.send_poll(
            chat_id=quiz["chat_id"],
            question=f"({q_idx + 1}/{total_qs}) {question['q']}",
            options=choices, type='quiz', correct_option_id=correct_idx,
            open_period=open_period,
            explanation=question.get("explanation") if quiz.get("show_explanations") else None,
            explanation_parse_mode=ParseMode.MARKDOWN, is_anonymous=False
        )
        
        quiz["active_poll_id"] = sent_poll_message.poll.id
        quiz["active_correct_option_id"] = sent_poll_message.poll.correct_option_id
        quiz.setdefault("shuffled_choices_map", {})[q_idx] = choices # حفظ الخيارات المخلوطة
        database._update_user_in_db(user_id, user)

    except Exception as e:
        logger.error(f"Failed to send poll for user {user_id}: {e}")
        await context.bot.send_message(quiz["chat_id"], "⚠️ حدث خطأ أثناء إرسال السؤال التالي. تم إيقاف الكويز.")
        user["session"].pop("quiz", None)
        database._update_user_in_db(user_id, user)


async def _start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE, n_questions: int, is_retry: bool = False):
    query = update.callback_query
    user = database.ensure_user(query.from_user.id, query.from_user.full_name)
    prefs = _get_quiz_prefs(user)
    
    await query.answer()
    status_message = await query.edit_message_text("⏳ جاري تجهيز الكويز...", reply_markup=keyboards.quiz_cancel_kb())

    questions = []
    if is_retry:
        old_quiz = user["session"].get("quiz", {})
        all_qs = old_quiz.get("questions", [])
        incorrect_indices = [i for i in old_quiz.get("incorrect_indices", []) if i not in old_quiz.get("skipped_indices", [])]
        if not all_qs or not incorrect_indices:
            await status_message.edit_text("✅ لا توجد أسئلة خاطئة لإعادتها!", reply_markup=keyboards.quiz_menu_kb())
            return config.QZ_MENU
        questions = [all_qs[i] for i in incorrect_indices]
    else:
        src_text = user["session"].get("last_text", "").strip()
        if not src_text:
            await status_message.edit_text("⚠️ لم أجد نصًا لتوليد كويز منه.", reply_markup=keyboards.back_to_menu_kb())
            return config.QZ_MENU
        questions = await ai_generate_quiz(src_text, n_questions=min(n_questions, config.MAX_QUIZ_QUESTIONS))

    if not questions:
        await status_message.edit_text("⚠️ لم أتمكن من إنشاء أسئلة من النص المقدم.", reply_markup=keyboards.quiz_menu_kb())
        return config.QZ_MENU

    if prefs.get("shuffle_questions"): random.shuffle(questions)
    questions = questions[:n_questions]

    # بناء حالة الكويز الجديدة بشكل كامل
    user["session"]["quiz"] = {
        "questions": questions, "current_q_idx": 0, "score": 0,
        "incorrect_indices": [], "skipped_indices": [],
        "user_answers": {}, "is_finished": False,
        "shuffled_choices_map": {}, "original_correct_indices": {},
        "chat_id": query.message.chat_id, "start_message_id": status_message.message_id,
        "active_poll_id": None, "active_correct_option_id": None,
        **prefs
    }
    
    database._update_user_in_db(user['id'], user)
    await _display_question(context, user['id'])
    return config.QZ_RUNNING

# --- Command and Button Handlers ---
async def quiz_command_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = database.ensure_user(update.effective_user.id, update.effective_user.full_name)
    _get_quiz_prefs(user)
    text = "🧠 **تحدي المعرفة**\n\nاختر عدد الأسئلة للبدء، أو قم بضبط الإعدادات."
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=keyboards.quiz_menu_kb())
    else:
        await update.message.reply_text(text, reply_markup=keyboards.quiz_menu_kb())
    return config.QZ_MENU

async def quiz_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = database.ensure_user(query.from_user.id, query.from_user.full_name)
    data = query.data
    
    if data == "qz_settings":
        prefs = _get_quiz_prefs(user)
        await query.edit_message_text("⚙️ **إعدادات الكويز**", reply_markup=keyboards.quiz_settings_kb(prefs))
        return config.QZ_SETTINGS

    if data.startswith("qz_toggle_"):
        await query.answer()
        prefs = _get_quiz_prefs(user)
        key_map = {"q": "shuffle_questions", "c": "shuffle_choices", "expl": "show_explanations", "retry": "retry_incorrect"}
        key = key_map.get(data.split("_")[-1])
        if key:
            prefs[key] = not prefs.get(key, True)
            database._update_user_in_db(user['id'], user)
            await query.edit_message_text("⚙️ **إعدادات الكويز**", reply_markup=keyboards.quiz_settings_kb(prefs))
        return config.QZ_SETTINGS
        
    if data == "qz_set_timer":
        await query.answer()
        prefs = _get_quiz_prefs(user)
        options = [0, 15, 30, 60]
        current_timer = prefs.get("timer", 30)
        try: next_timer = options[(options.index(current_timer) + 1) % len(options)]
        except ValueError: next_timer = 30
        prefs["timer"] = next_timer
        database._update_user_in_db(user['id'], user)
        await query.edit_message_text("⚙️ **إعدادات الكويز**", reply_markup=keyboards.quiz_settings_kb(prefs))
        return config.QZ_SETTINGS

    if data.startswith("qz_start_"):
        n = int(data.split("_")[-1])
        return await _start_quiz(update, context, n_questions=n)

    if data == "qz_retry_wrong":
        return await _start_quiz(update, context, n_questions=100, is_retry=True)
    
    # Fallback to quiz menu
    await query.answer()
    await query.edit_message_text("🧠 **تحدي المعرفة**", reply_markup=keyboards.quiz_menu_kb())
    return config.QZ_MENU

async def handle_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        answer = update.poll_answer
        user_id = answer.user.id
        user = database._get_user_from_db(user_id)
        if not user or "quiz" not in user.get("session", {}): return

        quiz = user["session"]["quiz"]
        if answer.poll_id != quiz.get("active_poll_id"): return

        q_idx = quiz["current_q_idx"]
        selected_option_idx = answer.option_ids[0] if answer.option_ids else -1
        quiz.setdefault("user_answers", {})[q_idx] = selected_option_idx

        if selected_option_idx != -1:
            if selected_option_idx == quiz.get("active_correct_option_id"):
                quiz["score"] = quiz.get("score", 0) + 1
            else:
                quiz.setdefault("incorrect_indices", []).append(q_idx)
        else:
            quiz.setdefault("skipped_indices", []).append(q_idx)
            quiz.setdefault("incorrect_indices", []).append(q_idx)

        quiz["current_q_idx"] += 1
        database._update_user_in_db(user_id, user)
        
        context.job_queue.run_once(
            lambda ctx: _display_question(ctx, user_id),
            when=2, name=f"next_q_{user_id}_{random.randint(1, 10000)}"
        )
    except Exception as e:
        logger.error(f"FATAL ERROR in handle_quiz_answer for user {update.poll_answer.user.id}: {e}", exc_info=True)

# --- New Handlers for Cancel and Review ---
async def quiz_cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's request to cancel a running quiz."""
    query = update.callback_query
    await query.answer("تم إلغاء الكويز.")
    user = database.ensure_user(query.from_user.id, query.from_user.full_name)
    user["session"].pop("quiz", None)
    database._update_user_in_db(user['id'], user)
    await query.edit_message_text("⏹️ تم إلغاء الكويز بنجاح.", reply_markup=keyboards.quiz_menu_kb())
    return config.QZ_MENU

async def quiz_review_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Generates and sends a detailed review of all quiz questions and answers."""
    query = update.callback_query
    await query.answer()
    user = database.ensure_user(query.from_user.id, query.from_user.full_name)
    quiz = user.get("session", {}).get("quiz")

    if not quiz or not quiz.get("is_finished"):
        await query.message.reply_text("لا يوجد كويز منتهي لمراجعته.", reply_markup=keyboards.quiz_menu_kb())
        return config.QZ_MENU

    await query.message.reply_text("⏳ جاري إعداد المراجعة التفصيلية...")
    review_lines = ["🧐 **مراجعة الإجابات**\n" + ("-"*25)]
    
    for idx, question in enumerate(quiz["questions"]):
        review_lines.append(f"\n*{idx + 1}. {question['q']}*")
        
        original_correct_idx = quiz.get("original_correct_indices", {}).get(idx, 0)
        correct_answer_text = question["choices"][original_correct_idx]
        
        user_selected_idx = quiz.get("user_answers", {}).get(idx, -1)
        shuffled_choices = quiz.get("shuffled_choices_map", {}).get(idx, question["choices"])
        user_answer_text = shuffled_choices[user_selected_idx] if user_selected_idx != -1 else "لم تتم الإجابة"

        if user_answer_text == correct_answer_text:
            review_lines.append(f"✅ إجابتك: *{user_answer_text}* (صحيحة)")
        else:
            review_lines.append(f"❌ إجابتك: *{user_answer_text}*")
            review_lines.append(f"💡 الإجابة الصحيحة: *{correct_answer_text}*")
        
        if quiz.get("show_explanations") and question.get("explanation"):
            review_lines.append(f"💬 الشرح: _{question['explanation']}_")

    review_text = "\n".join(review_lines)
    for i in range(0, len(review_text), 4000): # Send in chunks if too long
        await context.bot.send_message(
            chat_id=query.message.chat_id, text=review_text[i:i+4000], parse_mode=ParseMode.MARKDOWN
        )

    await context.bot.send_message(
        chat_id=query.message.chat_id, text="تم عرض المراجعة.", reply_markup=keyboards.quiz_menu_kb()
    )
    return config.QZ_MENU
