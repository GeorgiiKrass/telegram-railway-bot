import json
import os
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import ContextTypes

NOTES_FILE = "structured_notes.json"
TIMEZONE = pytz.timezone("Europe/Kyiv")

def load_notes():
    if not os.path.exists(NOTES_FILE):
        return []
    with open(NOTES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_note(note):
    notes = load_notes()
    notes.append(note)
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(notes, f, indent=2, ensure_ascii=False)

def parse_note(text: str):
    words = text.split()
    tags = [w[1:] for w in words if w.startswith("#")]
    priority = next((w[1:] for w in words if w.startswith("!")), "средний")
    clean_text = " ".join(w for w in words if not w.startswith("#") and not w.startswith("!"))
    return {
        "text": clean_text.strip(),
        "tags": tags,
        "priority": priority,
        "timestamp": datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M")
    }

async def handle_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower().startswith("найти"):
        keyword = text[5:].strip().lower()
        notes = load_notes()
        found = [
            f"- {n['text']} (#{', '.join(n['tags']) if n['tags'] else 'без тега'}, приоритет: {n['priority']}, время: {n['timestamp']})"
            for n in notes if keyword in n['text'].lower()
        ]
        response = "\n".join(found) if found else "❌ Ничего не найдено."
        await update.message.reply_text(response)
    elif text.startswith("#") or text.startswith("!"):
        keyword = text.strip()
        notes = load_notes()
        if keyword.startswith("#"):
            tag = keyword[1:]
            found = [
                f"- {n['text']} (#{', '.join(n['tags'])}, приоритет: {n['priority']}, время: {n['timestamp']})"
                for n in notes if tag in n['tags']
            ]
        elif keyword.startswith("!"):
            priority = keyword[1:]
            found = [
                f"- {n['text']} (#{', '.join(n['tags']) if n['tags'] else 'без тега'}, приоритет: {n['priority']}, время: {n['timestamp']})"
                for n in notes if priority == n['priority']
            ]
        else:
            found = []

        response = "\n".join(found) if found else "❌ Ничего не найдено."
        await update.message.reply_text(response)
    else:
        note = parse_note(text)
        save_note(note)
        await update.message.reply_text(
            f"📝 Заметка сохранена:\n«{note['text']}»\nТеги: {', '.join(note['tags']) or '—'} | Приоритет: {note['priority']} | Время: {note['timestamp']}"
        )
