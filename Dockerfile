# Используем официальный Python-образ
FROM python:3.10-slim

# Устанавливаем системные библиотеки, необходимые для SpeechRecognition и pydub
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libasound-dev \
    portaudio19-dev \
    libportaudio2 \
    libportaudiocpp0 \
    python3-pyaudio \
    curl \
    && apt-get clean

# Создаём рабочую директорию
WORKDIR /app

# Копируем зависимости и код
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Запускаем бота
CMD ["python", "draft_bot.py"]