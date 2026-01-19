# Инструкция по развертыванию бота в облаке

Этот документ описывает несколько способов развертывания Telegram бота в облаке для постоянной работы.

## Варианты деплоя

### 1. Railway (Рекомендуется) ⭐

**Плюсы:** Простой, бесплатный тариф, автоматический деплой из GitHub

**Шаги:**

1. Зарегистрируйтесь на [Railway.app](https://railway.app) (можно через GitHub)

2. Создайте новый проект и подключите ваш GitHub репозиторий

3. Добавьте переменные окружения в настройках проекта:
   - `API_ID` - ваш Telegram API ID
   - `API_HASH` - ваш Telegram API Hash
   - `TELEGRAM_BOT_TOKEN` - токен бота от @BotFather
   - `OPENAI_API_KEY` - ключ OpenAI API
   - `FOLDER_NAME` - название папки Telegram (например, "GPT")
   - `SUBSCRIBERS_FILE` - subscribers.json
   - `DATA_DIR` - путь к volume (например, `/data`)
   - `DEBUG_MODE` - False (для продакшена)
   - `DEBUG_USER_IDS` - можно оставить пустым

4. Railway автоматически определит `Procfile` и запустит `python scripts/get_users.py`

5. Для ежедневной рассылки настройте Scheduled Task:
   - В настройках проекта → New → Scheduled Task
   - Cron: `0 9 * * *` (каждый день в 09:00 UTC)
   - Command: `python scripts/run_daily.py --send`

6. Загрузите файл сессии Telethon:
   - Создайте его локально: `python scripts/create_user_session.py`
   - Скопируйте `anon_news.session` на Railway как файл или через переменную окружения (base64)
   - Переменная окружения: `TELEGRAM_SESSION_B64` (также поддерживается `TELEGRAM_SESSION`)

7. Подключите volume для постоянных данных:
   - Railway → Settings → Volumes → Add Volume
   - Mount path: `/data`
   - Установите переменную окружения `DATA_DIR=/data`

**Важно:** Railway предоставляет бесплатный тариф с ограничениями. Для продакшена может потребоваться платный план.

---

### 2. Render

**Плюсы:** Бесплатный тариф, простой интерфейс

**Шаги:**

1. Зарегистрируйтесь на [Render.com](https://render.com)

2. Создайте новый Background Worker (не Web Service):
   - Подключите GitHub репозиторий
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python scripts/get_users.py`

3. Добавьте переменные окружения (Environment Variables):
   - Те же, что и для Railway

4. Для ежедневной рассылки используйте Cron Job (если доступно):
   - New → Cron Job
   - Schedule: `0 9 * * *`
   - Command: `python scripts/run_daily.py --send`
   - Если Cron Jobs недоступны на тарифе — используйте внешний планировщик

5. Загрузите `anon_news.session` через SSH или как файл
   - Переменная окружения: `TELEGRAM_SESSION_B64` (также поддерживается `TELEGRAM_SESSION`)

**Ограничения:** Бесплатный тариф может "засыпать" после 15 минут неактивности. Для постоянной работы нужен платный план.

---

### 3. DigitalOcean App Platform

**Плюсы:** Надежный, хорошая производительность

**Шаги:**

1. Зарегистрируйтесь на [DigitalOcean](https://www.digitalocean.com)

2. Создайте App:
   - Подключите GitHub репозиторий
   - Выберите Python
   - Build Command: `pip install -r requirements.txt`
   - Run Command: `python scripts/get_users.py` (Worker)

3. Добавьте переменные окружения в настройках App

4. Для cron задач используйте Jobs:
   - Create Job
   - Schedule: `0 9 * * *` (каждый день в 09:00)
   - Command: `python scripts/run_daily.py --send`

**Стоимость:** От $5/месяц

---

### 4. VPS (DigitalOcean, Linode, Hetzner)

**Плюсы:** Полный контроль, дешево, надежно

**Шаги:**

1. Создайте VPS (рекомендуется Ubuntu 22.04):
   ```bash
   # Минимальные требования: 1GB RAM, 1 CPU
   ```

2. Подключитесь по SSH и установите зависимости:
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip python3-venv git -y
   ```

3. Клонируйте репозиторий:
   ```bash
   git clone <ваш_репозиторий> /opt/news_bot
   cd /opt/news_bot
   ```

4. Создайте виртуальное окружение:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

5. Создайте `config.py` с вашими данными или задайте переменные окружения

6. Настройте systemd для автозапуска бота:
   ```bash
   sudo nano /etc/systemd/system/news-bot.service
   ```
   
   Содержимое файла:
   ```ini
   [Unit]
   Description=News Bot Service
   After=network.target

   [Service]
   Type=simple
   User=your_username
   WorkingDirectory=/opt/news_bot
   Environment="PATH=/opt/news_bot/venv/bin"
  ExecStart=/opt/news_bot/venv/bin/python scripts/get_users.py
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

7. Включите и запустите сервис:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable news-bot
   sudo systemctl start news-bot
   ```

8. Настройте cron для ежедневной рассылки:
   ```bash
   crontab -e
   ```
   
   Добавьте строку:
   ```
  0 9 * * * cd /opt/news_bot && /opt/news_bot/venv/bin/python scripts/run_daily.py --send >> /opt/news_bot/bot.log 2>&1
   ```

9. Проверьте статус:
   ```bash
   sudo systemctl status news-bot
   ```

**Стоимость:** От $4-6/месяц

---

## Важные моменты

### Файл сессии Telethon

Telethon создает файл `anon_news.session` при первом запуске. Этот файл нужно:
1. Создать локально (`python scripts/create_user_session.py`)
2. Загрузить на сервер/в облако
3. Сохранить в рабочей директории проекта

### Переменные окружения vs config.py

Для безопасности лучше использовать переменные окружения вместо `config.py` с секретами. В проекте уже есть поддержка `.env` и переменных окружения (см. `config.py`):

```python
import os

api_id = int(os.getenv('API_ID', 'YOUR_API_ID'))
api_hash = os.getenv('API_HASH', 'YOUR_API_HASH')
# и т.д.
```

### Хранение подписчиков и логов

В облаке файловая система может быть эфемерной. Если `subscribers.json` и логи должны сохраняться между перезапусками:
- используйте persistent disk (Render) или volume (Railway)
- задайте `DATA_DIR` на путь внутри volume (например, `/data`)
- при необходимости задайте `SUBSCRIBERS_FILE` как абсолютный путь

### Логирование

В облаке логи обычно доступны через:
- Railway: вкладка Logs
- Render: вкладка Logs
- VPS: `journalctl -u news-bot -f` или файлы `.log`

### Мониторинг

Рекомендуется настроить:
- Алерты при падении бота (через uptime monitoring)
- Регулярные проверки работоспособности
- Ротацию логов

---

## Рекомендации

1. **Для начала:** Railway или Render (проще всего)
2. **Для продакшена:** VPS или DigitalOcean App Platform (надежнее)
3. **Бюджет:** VPS самый дешевый вариант с полным контролем

---

## Поддержка

При возникновении проблем проверьте:
- Логи бота
- Переменные окружения
- Наличие файла сессии Telethon
- Доступность интернета на сервере
