# handlers/library_handler.py
import uuid
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.error import BadRequest

import database
import keyboards
import config
from utils import shorten

# --- Entry Point ---
async def library_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = database.ensure_user(update.effective_user.id, update.effective_user.full_name)
    context.user_data['library_history'] = ['main']
    
    text = "📚 **المكتبة الذكية**\n\nهنا يمكنك تنظيم كل المواد الدراسية الخاصة بك."
    keyboard = keyboards.library_main_kb(user)
    
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=keyboard)
        except BadRequest as e:
            if "There is no text in the message to edit" in str(e):
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=keyboard)
            else: raise e
    else:
        await update.message.reply_text(text, reply_markup=keyboard)
    return config.LIB_MAIN

# --- Router for all library actions ---
async def library_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = database.ensure_user(query.from_user.id, query.from_user.full_name)
    data = query.data
    
    if data == "lib_main":
        await query.edit_message_text("📚 **المكتبة الذكية**", reply_markup=keyboards.library_main_kb(user))
        return config.LIB_MAIN

    if data.startswith("lib_open_"):
        folder_id = data.split("_", 2)[2]
        context.user_data['current_folder'] = folder_id
        folder_name = user["library"]["folders"].get(folder_id, {}).get("name", "مجلد")
        await query.edit_message_text(f"محتويات: **{folder_name}**", reply_markup=keyboards.library_folder_kb(user, folder_id))
        return config.LIB_FOLDER_VIEW

    if data == "lib_new_folder":
        await query.edit_message_text("✍️ أرسل اسم المجلد الجديد الذي تريد إنشاءه.")
        return config.LIB_CREATE_FOLDER

    if data.startswith("lib_view_"):
        item_id = data.split("_", 2)[2]
        item = user["library"]["items"].get(item_id)
        if not item:
            await query.answer("⚠️ العنصر غير موجود!", show_alert=True)
            return config.LIB_FOLDER_VIEW
        context.user_data['current_item'] = item_id
        content = item['content']
        text = f"**{item['type'].capitalize()}:** {item['title']}\n\n"
        if isinstance(content, str): text += shorten(content, 200)
        elif isinstance(content, list): text += f"يحتوي على {len(content)} سؤال."
        else: text += "محتوى غير نصي."
        await query.edit_message_text(text, reply_markup=keyboards.library_item_kb(item_id))
        return config.LIB_ITEM_VIEW

    if data.startswith("lib_del_"):
        item_id = data.split("_", 2)[2]
        user["library"]["items"].pop(item_id, None)
        for folder in user["library"]["folders"].values():
            if item_id in folder["items"]: folder["items"].remove(item_id)
        database._update_user_in_db(user['id'], user)
        await query.answer("🗑️ تم حذف العنصر!")
        folder_id = context.user_data.get('current_folder', 'default')
        folder_name = user["library"]["folders"].get(folder_id, {}).get("name", "مجلد")
        await query.edit_message_text(f"محتويات: **{folder_name}**", reply_markup=keyboards.library_folder_kb(user, folder_id))
        return config.LIB_FOLDER_VIEW

    if data.startswith("lib_move_"):
        item_id = data.split("_", 2)[2]
        await query.edit_message_text("اختر المجلد لنقل العنصر إليه:", reply_markup=keyboards.library_move_kb(user, item_id))
        return config.LIB_MOVE_ITEM

    if data.startswith("lib_moveto_"):
        _, _, item_id, target_folder_id = data.split("_")
        library = user["library"]
        for folder in library["folders"].values():
            if item_id in folder["items"]: folder["items"].remove(item_id)
        library["folders"][target_folder_id]["items"].append(item_id)
        database._update_user_in_db(user['id'], user)
        await query.answer("🔄 تم نقل العنصر!", show_alert=True)
        item = user["library"]["items"].get(item_id)
        text = f"**{item['type'].capitalize()}:** {item['title']}\n\n(تم نقله)"
        await query.edit_message_text(text, reply_markup=keyboards.library_item_kb(item_id))
        return config.LIB_ITEM_VIEW

    if data == "lib_back_folder":
        folder_id = context.user_data.get('current_folder', 'default')
        folder_name = user["library"]["folders"].get(folder_id, {}).get("name", "مجلد")
        await query.edit_message_text(f"محتويات: **{folder_name}**", reply_markup=keyboards.library_folder_kb(user, folder_id))
        return config.LIB_FOLDER_VIEW

    if data == "lib_search":
        await query.edit_message_text("🔍 أرسل كلمة البحث...")
        return config.LIB_SEARCH

    return config.LIB_MAIN

# --- Text Handlers for specific states ---
async def library_create_folder_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = database.ensure_user(update.effective_user.id, update.effective_user.full_name)
    folder_name = update.message.text.strip()
    
    if not 1 <= len(folder_name) <= 30:
        await update.message.reply_text("⚠️ اسم المجلد يجب أن يكون بين 1 و 30 حرفًا.")
        return config.LIB_CREATE_FOLDER

    folder_id = f"folder_{uuid.uuid4().hex[:8]}"
    user["library"]["folders"][folder_id] = {"name": f"📂 {folder_name}", "items": []}
    database._update_user_in_db(user['id'], user)
    
    await update.message.reply_text(f"✅ تم إنشاء مجلد '{folder_name}'!", reply_markup=keyboards.library_main_kb(user))
    return config.LIB_MAIN

async def library_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = database.ensure_user(update.effective_user.id, update.effective_user.full_name)
    query = update.message.text.strip().lower()
    
    if not query:
        await update.message.reply_text("⚠️ يرجى إرسال كلمة بحث.")
        return config.LIB_SEARCH

    results = [item for item in user["library"]["items"].values() if query in item["title"].lower() or (isinstance(item["content"], str) and query in item["content"].lower())]
            
    if not results:
        await update.message.reply_text(f"لم يتم العثور على نتائج لـ '{query}'.", reply_markup=keyboards.library_main_kb(user))
        return config.LIB_MAIN
        
    text_results = [f"نتائج البحث عن '{query}': ({len(results)})"]
    for item in results[:10]: # Limit to 10 results
        icon = {"summary": "📝", "explanation": "📚"}.get(item["type"], "📄")
        text_results.append(f"\n{icon} *{item['title']}*\n_{shorten(str(item.get('content', '')), 80)}_")
    
    await update.message.reply_text("\n".join(text_results), parse_mode=ParseMode.MARKDOWN)
    await update.message.reply_text("📚 **المكتبة الذكية**", reply_markup=keyboards.library_main_kb(user))
    return config.LIB_MAIN