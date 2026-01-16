FROM python:3.13-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование файлов проекта
COPY . .

# Создание директории для логов и данных
RUN mkdir -p /app/data

# Запуск бота
CMD ["python", "scripts/get_users.py"]
