FROM python:3.11-slim

# 1. Ставим git и чистим кэш
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# 2. Клонируем ваш репо
RUN git clone https://github.com/anatahops/sneakercard.git /app
WORKDIR /app

# 3. Ставим зависимости
RUN pip install -r requirements.txt

# 4. Запускаем бота
CMD ["python","-u","bot.py"]
