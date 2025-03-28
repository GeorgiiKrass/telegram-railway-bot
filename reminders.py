import json
import os
import re
from datetime import datetime
import pytz
import dateparser
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update
from telegram.ext import ContextTypes

REMINDERS_FILE = "reminders.json"
TIMEZONE = pytz.timezone("Europe/Kyiv")
scheduler = BackgroundScheduler(timezone=TIMEZONE)
scheduler.start()

def load_reminders():
    if not os.path.exists(REMINDERS_FILE):
        return []
    with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_reminders(reminders):
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, indent=2, ensure_ascii=False)

def schedule_reminder(chat_id, text, remind_time, context):
    scheduler.add_job(
        lambda: context.bot.send_message(chat_id=chat_id, text=f"⏰ Напоминание: {text}"),
        trigger="date",
        run_date=remind_time,
        id=f"{chat_id}-{remind_time.timestamp()}",
        replace_existing=True
    )

def parse_reminder(text: str):
    match = re.match(r"напомни (.+?) — (.+)", text, re.IGNORECASE)
    if not match:
        return None, None
    time_part = match.group(1).strip()
    message_part = match.group(2).strip()
    parsed_time = dateparser.parse(time_part, languages=["ru"], settings={"TIMEZONE": "Europe/Kyiv", "RETURN_AS_TIMEZONE_AWARE": True})
    return parsed_time, message_part

async def handle_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    remind_time, message = parse_reminder(text)

    if not remind_time or not message:
        await update.message.reply_text("❌ Не удалось распознать время или текст. Используй формат:

напомни сегодня в 18:00 — сделать звонок")
        return

    reminder = {
        "chat_id": update.message.chat_id,
        "text": message,
        "remind_time": remind_time.isoformat()
    }

    reminders = load_reminders()
    reminders.append(reminder)
    save_reminders(reminders)

    schedule_reminder(update.message.chat_id, message, remind_time, context)

    await update.message.reply_text(f"✅ Напоминание установлено на {remind_time.strftime('%Y-%m-%d %H:%M')}:
«{message}»")
