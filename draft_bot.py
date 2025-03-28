
import os
import logging
import uuid
import json
import dateparser
from datetime import datetime
from telegram import Update, Voice
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydub import AudioSegment
import speech_recognition as sr

BOT_TOKEN = os.getenv("TOKEN")
AUDIO_DIR = "audio_notes"
REMINDERS_FILE = "reminders.json"

os.makedirs(AUDIO_DIR, exist_ok=True)
scheduler = AsyncIOScheduler()
logging.basicConfig(level=logging.INFO)

def save_reminder(r):
    if not os.path.exists(REMINDERS_FILE):
        data = []
    else:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    data.append(r)
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def extract_time_and_text(text):
    if "через" in text:
        parts = text.lower().replace("напомни", "").strip().split()
        if len(parts) >= 4:
            time_candidate = " ".join(parts[:3])
            text_candidate = " ".join(parts[3:])
            print(f"🛠 fallback: время = '{time_candidate}', текст = '{text_candidate}'")
            return time_candidate, text_candidate
    return None, None

def schedule(application, chat_id, text, when_str):
    print(f"🧠 Пытаемся распарсить: {when_str}")
    dt = dateparser.parse(
        when_str,
        languages=["ru"],
        settings={
            "PREFER_DATES_FROM": "future",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "RELATIVE_BASE": datetime.now()
        }
    )
    if dt:
        print(f"📅 Напоминание будет в: {dt}")
        scheduler.add_job(
            lambda: application.bot.send_message(chat_id=chat_id, text=f"⏰ Напоминание: {text}"),
            trigger='date',
            run_date=dt
        )
        r = {"chat_id": chat_id, "text": text, "datetime": dt.strftime("%Y-%m-%d %H:%M")}
        save_reminder(r)
        return True
    else:
        print("❌ Не удалось распарсить дату.")
        return False

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice: Voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    ogg = f"{AUDIO_DIR}/{voice.file_id}.ogg"
    wav = f"{AUDIO_DIR}/{voice.file_id}.wav"
    await file.download_to_drive(ogg)

    try:
        sound = AudioSegment.from_file(ogg)
        sound.export(wav, format="wav")
        recog = sr.Recognizer()
        with sr.AudioFile(wav) as source:
            audio = recog.record(source)
            text = recog.recognize_google(audio, language="ru-RU")
        print(f"🎙 Текст: {text}")
        if "напомни" in text.lower():
            when, body = extract_time_and_text(text)
            if when and body:
                if schedule(context.application, update.message.chat_id, body, when):
                    await update.message.reply_text("✅ Напоминание установлено")
                    return
            await update.message.reply_text("⚠️ Не удалось распознать время.")
        else:
            await update.message.reply_text(f"📝 Распознал как заметку: {text}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        await update.message.reply_text("⚠️ Ошибка распознавания")

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    scheduler.start()
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.run_polling()
