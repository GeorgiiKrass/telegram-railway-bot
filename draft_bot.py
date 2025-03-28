
import os
import json
import uuid
import logging
import dateparser
import speech_recognition as sr
from datetime import datetime
from telegram import Update, Voice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydub import AudioSegment

BOT_TOKEN = os.getenv("TOKEN")
NOTES_FILE = "notes.txt"
REMINDERS_FILE = "reminders.json"
AUDIO_DIR = "audio_notes"

os.makedirs(AUDIO_DIR, exist_ok=True)
logging.basicConfig(level=logging.INFO)
scheduler = AsyncIOScheduler()

TEXT_NUMBERS = {
    "одну": "1", "один": "1", "одна": "1",
    "две": "2", "два": "2",
    "три": "3",
    "четыре": "4",
    "пять": "5",
    "шесть": "6",
    "семь": "7",
    "восемь": "8",
    "девять": "9",
    "десять": "10",
}

def normalize_time_expression(text: str) -> str:
    words = text.split()
    return " ".join([TEXT_NUMBERS.get(w.lower(), w) for w in words])

def extract_time_and_text(full_text: str):
    base = full_text.lower().replace("напомни", "").strip()
    base = normalize_time_expression(base)

    words = base.split()
    for i in range(2, len(words)):
        time_candidate = " ".join(words[:i])
        parsed = dateparser.parse(
            time_candidate,
            languages=["ru"],
            settings={"TIMEZONE": "Europe/Kyiv", "RETURN_AS_TIMEZONE_AWARE": True}
        )
        if parsed:
            text_part = " ".join(words[i:])
            logging.info(f"✅ Распознано как напоминание: время='{time_candidate}', текст='{text_part}'")
            return time_candidate, text_part

    logging.warning(f"❌ Не удалось распознать время в тексте: '{base}'")
    return None, None

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
        await bot.send_message(chat_id=chat_id, text=f"⏰ Напоминание: {text}")
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")

def schedule_reminder(bot, chat_id, text, when_str, reminder_id):
    try:
        when_str = normalize_time_expression(when_str)
        parsed_time = dateparser.parse(
            when_str,
            languages=["ru"],
            settings={"TIMEZONE": "Europe/Kyiv", "RETURN_AS_TIMEZONE_AWARE": True}
        )
        if not parsed_time:
            logging.warning(f"⚠️ dateparser не распознал: '{when_str}'")
            return False

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

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice: Voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)

    ogg_path = f"{AUDIO_DIR}/{voice.file_id}.ogg"
    wav_path = f"{AUDIO_DIR}/{voice.file_id}.wav"

    await file.download_to_drive(ogg_path)

    try:
        sound = AudioSegment.from_file(ogg_path)
        sound.export(wav_path, format="wav")

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio = recognizer.record(source)
            text = recognizer.recognize_google(audio, language="ru-RU")

        if "напомни" in text.lower():
            when_str, reminder_text = extract_time_and_text(text)
            if when_str and reminder_text:
                reminder_id = str(uuid.uuid4())
                chat_id = update.message.chat_id
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
                    await update.message.reply_text(f"✅ Напоминание установлено на: {reminder_time}")
                    return
            await update.message.reply_text("⚠️ Не удалось распознать время.")
        else:
            save_note(text)
            await update.message.reply_text(f"📝 Распознал и записал: {text}")
    except Exception as e:
        logging.error(f"❌ Ошибка при распознавании: {e}")
        await update.message.reply_text("⚠️ Не удалось распознать голосовое сообщение.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎙 Отправь голос или текст: напомни через 2 минуты выпить воды")

async def handle_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower().startswith("напомни "):
        when_str, reminder_text = extract_time_and_text(text)
        if when_str and reminder_text:
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
                await update.message.reply_text(f"✅ Напоминание установлено на: {reminder_time}")
                return

        await update.message.reply_text("⚠️ Не удалось распознать время.")
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
    scheduler.start()

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_startup).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reminders", show_reminders))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_note))
    app.run_polling()
