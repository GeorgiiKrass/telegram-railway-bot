import os
import json
import uuid
import logging
import dateparser
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

BOT_TOKEN = os.getenv("TOKEN")
NOTES_FILE = "notes.txt"
REMINDERS_FILE = "reminders.json"

logging.basicConfig(level=logging.INFO)
scheduler = AsyncIOScheduler()
print("📢 AsyncIOScheduler создан")

def load_notes():
    try:
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            return f.readlines()
    except FileNotFoundError:
        return []

def save_note(text):
    with open(NOTES_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")

def load_reminders():
    if not os.path.exists(REMINDERS_FILE):
        return []
    with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_reminders(reminders):
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, indent=2, ensure_ascii=False)

async def send_reminder(bot, chat_id, text, reminder_id):
    try:
        print(f"🔔 Async-напоминание: {text} | ID: {reminder_id}")
        await bot.send_message(chat_id=chat_id, text=f"⏰ Напоминание: {text}")
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")

def schedule_reminder(bot, chat_id, text, when_str, reminder_id):
    try:
        parsed_time = dateparser.parse(
            when_str,
            languages=["ru"],
            settings={"TIMEZONE": "Europe/Kyiv", "RETURN_AS_TIMEZONE_AWARE": True}
        )
        if not parsed_time:
            print("⚠️ Время не распознано:", when_str)
            return False

        print(f"✅ Планируем async-задачу на {parsed_time} | Текст: {text} | ID: {reminder_id}")

        scheduler.add_job(
            send_reminder,
            trigger='date',
            run_date=parsed_time,
            args=[bot, chat_id, text, reminder_id],
            id=reminder_id,
            replace_existing=True,
            coalesce=True
        )
        return parsed_time.strftime("%Y-%m-%d %H:%M")
    except Exception as e:
        logging.error(f"Ошибка при установке напоминания: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Напиши заметку или: напомни через 1 минуту - async тест")

async def handle_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower().startswith("напомни "):
        parts = text.split("-")
        if len(parts) == 2:
            when_str = parts[0].replace("напомни", "").strip()
            reminder_text = parts[1].strip()
            chat_id = update.message.chat_id
            reminder_id = str(uuid.uuid4())

            reminder_time = schedule_reminder(context.bot, chat_id, reminder_text, when_str, reminder_id)
            if reminder_time:
                reminder = {
                    "id": reminder_id,
                    "chat_id": chat_id,
                    "text": reminder_text,
                    "when": when_str,
                    "datetime": reminder_time
                }
                reminders = load_reminders()
                reminders.append(reminder)
                save_reminders(reminders)

                await update.message.reply_text(f"✅ Напоминание установлено на: {when_str}")
            else:
                await update.message.reply_text("⚠️ Не удалось распознать время.")
        else:
            await update.message.reply_text("⚠️ Формат: напомни через 1 минуту - текст")
    else:
        save_note(text)
        await update.message.reply_text("💾 Записал!")

async def show_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reminders = load_reminders()
    user_reminders = [r for r in reminders if r["chat_id"] == update.message.chat_id]
    if not user_reminders:
        await update.message.reply_text("🔕 У вас нет активных напоминаний.")
        return

    for r in user_reminders:
        text = f"⏳ {r['datetime']} — {r['text']}"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Выполнено", callback_data=f"done:{r['id']}"),
             InlineKeyboardButton("❌ Удалить", callback_data=f"delete:{r['id']}")]
        ])
        await update.message.reply_text(text, reply_markup=keyboard)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    action, reminder_id = data.split(":")
    reminders = load_reminders()
    updated_reminders = [r for r in reminders if r["id"] != reminder_id]
    save_reminders(updated_reminders)

    if action == "delete":
        await query.edit_message_text("❌ Напоминание удалено.")
    elif action == "done":
        await query.edit_message_text("✅ Отмечено как выполненное.")

async def on_startup(app):
    print("🚀 Запускаем планировщик внутри on_startup")
    scheduler.start()

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_startup).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reminders", show_reminders))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_note))
    print("🚀 Бот запущен")
    app.run_polling()
