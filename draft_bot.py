from datetime import datetime
import logging
import os
import json
import dateparser
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler

BOT_TOKEN = os.getenv("TOKEN")
NOTES_FILE = "notes.txt"
REMINDERS_FILE = "reminders.json"

logging.basicConfig(level=logging.INFO)
scheduler = BackgroundScheduler()
scheduler.start()

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

def schedule_reminder(application, chat_id, text, when_str):
    try:
        parsed_time = dateparser.parse(
            when_str,
            languages=["ru"],
            settings={"TIMEZONE": "Europe/Kyiv", "RETURN_AS_TIMEZONE_AWARE": True}
        )
        if not parsed_time:
            return False

        reminder = {
            "chat_id": chat_id,
            "text": text,
            "when": when_str,
            "datetime": parsed_time.strftime("%Y-%m-%d %H:%M")
        }

        reminders = load_reminders()
        reminders.append(reminder)
        save_reminders(reminders)

        scheduler.add_job(
            lambda: application.bot.send_message(chat_id=chat_id, text=f"⏰ Напоминание: {text}"),
            trigger='date',
            run_date=parsed_time
        )
        return True
    except Exception as e:
        logging.error(f"Ошибка при установке напоминания: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Напиши заметку или: напомни завтра в 10:00 - отправить бриф")

async def handle_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower().startswith("напомни "):
        parts = text.split("-")
        if len(parts) == 2:
            when_str = parts[0].replace("напомни", "").strip()
            reminder_text = parts[1].strip()
            chat_id = update.message.chat_id
            if schedule_reminder(context.application, chat_id, reminder_text, when_str):
                await update.message.reply_text(f"✅ Напоминание установлено на: {when_str}")
            else:
                await update.message.reply_text("⚠️ Не удалось распознать время.")
        else:
            await update.message.reply_text("⚠️ Формат: напомни завтра в 10:00 - текст")
    else:
        save_note(text)
        await update.message.reply_text("💾 Записал!")

async def show_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reminders = load_reminders()
    user_reminders = [r for r in reminders if r["chat_id"] == update.message.chat_id]
    if not user_reminders:
        await update.message.reply_text("🔕 У вас нет активных напоминаний.")
        return

    response = "🗓 Ваши напоминания:\n"
    for r in user_reminders:
        response += f"⏳ {r['datetime']} — {r['text']}\n"
    await update.message.reply_text(response)

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("напоминания", show_reminders))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_note))
    app.run_polling()
