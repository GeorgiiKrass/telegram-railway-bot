
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
    original = text.lower().replace("напомни", "").strip()
    normalized = original.replace("—", " ").replace("–", " ").replace("-", " ")
    print(f"🎙 Распознанный текст: {text}")
    print(f"🛠 Нормализованный текст: {normalized}")
    
    words = normalized.split()
    for i in range(2, len(words)):
        time_candidate = " ".join(words[:i])
        text_candidate = " ".join(words[i:])
        print(f"🔍 Пробуем время: {time_candidate} | текст: {text_candidate}")
        parsed = dateparser.parse(
            time_candidate,
            languages=["ru"],
            settings={
                "PREFER_DATES_FROM": "future",
                "RETURN_AS_TIMEZONE_AWARE": True,
                "RELATIVE_BASE": datetime.now()
            }
        )
        if parsed:
            print(f"✅ Успех: {parsed}")
            return time_candidate, text_candidate, parsed
    
    print("❌ Не удалось распарсить ни одну комбинацию")
    return None, None, None

def schedule(application, chat_id, text, when_str, parsed_time):
    try:
        job_id = str(uuid.uuid4())
        scheduler.add_job(
            lambda: send_reminder(application, chat_id, text, job_id),
            trigger='date',
            run_date=parsed_time,
            id=job_id
        )
        print(f"✅ Планируем задачу на {parsed_time} | Текст: {text} | ID: {job_id}")
        r = {"chat_id": chat_id, "text": text, "datetime": parsed_time.strftime("%Y-%m-%d %H:%M"), "id": job_id}
        save_reminder(r)
        return True
    except Exception as e:
        print(f"❌ Ошибка при планировании задачи: {e}")
        return False

def send_reminder(application, chat_id, text, job_id):
    try:
        application.bot.send_message(chat_id=chat_id, text=f"⏰ Напоминание: {text}")
        print(f"📤 Отправлено напоминание [{job_id}]: {text}")
    except Exception as e:
        print(f"❌ Ошибка при отправке напоминания [{job_id}]: {e}")

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
            when, body, parsed = extract_time_and_text(text)
            if when and body and parsed:
                if schedule(context.application, update.message.chat_id, body, when, parsed):
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
