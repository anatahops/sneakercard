FROM python:3.11-slim

# 1. Ставим git и чистим кэш
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# 2. Фикс DNS (работает даже в бесплатном CPU)
RUN echo "nameserver 8.8.8.8" > /etc/resolv.conf

# 3. Клонируем ваш репо
RUN git clone https://github.com/anatahops/sneakercard.git /app
WORKDIR /app

# 4. Ставим зависимости
RUN pip install -r requirements.txt

# 5. Запускаем бота
CMD ["python","-u","bot.py"]
