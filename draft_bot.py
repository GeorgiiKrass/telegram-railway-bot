from datetime import datetime, timedelta
import logging
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler

BOT_TOKEN = os.getenv("TOKEN")
NOTES_FILE = "notes.txt"

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

def schedule_reminder(application, chat_id, text, when_str):
    try:
        if "завтра" in when_str:
            time_part = when_str.split("в")[-1].strip()
            remind_time = datetime.now() + timedelta(days=1)
            hour, minute = map(int, time_part.split(":"))
            remind_time = remind_time.replace(hour=hour, minute=minute, second=0)
        else:
            return False

        scheduler.add_job(
            lambda: application.bot.send_message(chat_id=chat_id, text=f"⏰ Напоминание: {text}"),
            trigger='date',
            run_date=remind_time
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
                await update.message.reply_text(f"✅ Напоминание установлено на {when_str}")
            else:
                await update.message.reply_text("⚠️ Не удалось распознать время.")
        else:
            await update.message.reply_text("⚠️ Формат: напомни завтра в 10:00 - текст")
    else:
        save_note(text)
        await update.message.reply_text("💾 Записал!")

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_note))
    app.run_polling()
