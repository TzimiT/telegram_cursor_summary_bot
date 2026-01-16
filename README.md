Clean News Bot — ежедневный дайджест из Telegram

О проекте
- Репозиторий содержит два кооперативных скрипта на Python:
  - scripts/get_users.py — Telegram‑бот для подписки/отписки пользователей и служебных команд.
  - scripts/run_daily.py — единая точка входа для ежедневной рассылки: обновляет каналы, собирает новости, суммаризирует через OpenAI и рассылает дайджест подписчикам.
  - src/news_bot_part.py — модуль с функциями агрегации и рассылки (используется scripts/run_daily.py).

Стек
- Python 3.10+ (asyncio)
- Библиотеки:
  - telethon — клиент для чтения каналов/папок Telegram
  - python-telegram-bot — Bot API для общения с пользователями
  - openai — суммаризация через Chat Completions API
  - httpx — HTTP клиент (зависимость)
- Управление пакетами: pip (рекомендуется virtualenv)
- Docker — поддержка контейнеризации (опционально)

Точки входа и вспомогательные файлы
- scripts/get_users.py — запускает бота с командами: /start, /stop, /channels, /status, /recommend_channel. Должен работать постоянно (cron/pm2/systemd/Screen/Docker).
- scripts/run_daily.py — единый скрипт для ежедневной рассылки с аргументами командной строки. Запускать по расписанию (cron/Scheduled Task).
- scripts/create_user_session.py — создаёт user‑сессию Telethon (anon_news.session) для чтения каналов.
- src/news_bot_part.py — модуль с функциями get_news(), summarize_news(), send_news() (используется scripts/run_daily.py).
- src/get_channels.py — утилита для работы с каналами из папки Telegram.
- mycron.txt — примеры записей crontab для обоих скриптов.
- commands.txt — личные заметки по эксплуатации (не обязателен для работы).

Требования
- Python 3.10+
- Учётные данные Telegram (api_id, api_hash)
- Токен Telegram‑бота (@BotFather)
- Ключ OpenAI API
- Доступ к интернету (Telegram и OpenAI)

Структура проекта
- config_example.py — шаблон конфигурации. Скопируйте в config.py и заполните поля.
- config.py — конфигурация с поддержкой переменных окружения (приоритет: переменные окружения → значения по умолчанию). Не публикуйте реальные ключи в публичный репозиторий.
- src/get_channels.py — утилита для выгрузки информации о каналах из папки Telegram в channels.json.
- scripts/get_users.py — точка входа бота подписчиков (python-telegram-bot).
- scripts/run_daily.py — единый скрипт для ежедневной рассылки с аргументами командной строки.
- src/news_bot_part.py — модуль с функциями агрегации и рассылки (Telethon + OpenAI).
- channels.json — список каналов для агрегации (формируется/обновляется src/get_channels.py или scripts/run_daily.py --channels).
- subscribers.json — список подписчиков в формате { "subscribers": [ { ... } ] }.
- sent_messages.log — лог каждой отправленной части сообщения (время, user_id, message_id, длина, полный текст).
- sent_summaries.log — лог полных саммари перед рассылкой (с датой и временем).
- Логи: users.log, bot.log (+ архивные варианты).
- Файлы сессий Telethon: anon.session, anon_news.session.
- Dockerfile — конфигурация для Docker-контейнера.
- Procfile — конфигурация для деплоя на Railway/Render.
- DEPLOY.md, QUICK_DEPLOY.md — инструкции по развертыванию в облаке.
- Прочее: commands.txt, channel_recommendations.txt, tz*.txt.
- Утилиты: scripts/backfill_users_once.py, scripts/update_subscribers_data.py, scripts/upload_session.py.

Конфигурация
1) Создайте config.py на основе шаблона:
   - Скопируйте config_example.py → config.py и заполните значения по умолчанию (или используйте переменные окружения).
   - Параметры:
     - api_id, api_hash — из https://my.telegram.org
     - openai_api_key — ключ OpenAI
     - telegram_bot_token — токен бота от @BotFather
     - FOLDER_NAME — название папки Telegram с целевыми каналами (например, "GPT")
     - TARGET_CHAT_ID — зарезервировано под расширения (в основном не используется)
     - SUBSCRIBERS_FILE — путь к JSON со списком подписчиков (по умолчанию subscribers.json)
     - DEBUG_MODE — режим отладки (True/False). Если True, рассылка только тестовым пользователям.
     - DEBUG_USER_IDS — список user_id для тестовой рассылки (используется при DEBUG_MODE=True)

2) Telegram:
   - В приложении Telegram создайте/используйте папку с именем FOLDER_NAME и добавьте туда каналы для агрегации.

3) OpenAI:
   - Ключ получите на https://platform.openai.com/ и укажите в config.py или переменной окружения OPENAI_API_KEY.

4) Переменные окружения (приоритет над значениями в config.py):
   - API_ID, API_HASH — учетные данные Telegram
   - TELEGRAM_BOT_TOKEN — токен бота
   - OPENAI_API_KEY — ключ OpenAI
   - FOLDER_NAME — название папки Telegram
   - DEBUG_MODE — режим отладки ('True'/'False')
   - DEBUG_USER_IDS — список user_id через запятую (например, "123456,789012")

Установка
- Создайте и активируйте виртуальное окружение, установите зависимости:
  ```bash
  python -m venv venv
  source venv/bin/activate  # macOS/Linux
  # или venv\Scripts\activate  # Windows
  pip install --upgrade pip
  pip install -r requirements.txt
  ```
  
  Или установите зависимости вручную:
  ```bash
  pip install telethon>=1.40.0 python-telegram-bot>=22.1 openai>=1.0.0 httpx>=0.28.0
  ```

Запуск
Вариант A: вручную
- Запустить бота подписчиков (должен работать постоянно):
  ```bash
  python scripts/get_users.py
  ```

- Подготовить user‑сессию Telethon (нужна для чтения каналов):
  ```bash
  python scripts/create_user_session.py
  ```

- Прогнать агрегатор один раз (для проверки):
  ```bash
  python scripts/run_daily.py --send
  ```
  
  Или использовать отдельные этапы:
  ```bash
  python scripts/run_daily.py --channels    # Обновить channels.json
  python scripts/run_daily.py --news        # Только собрать новости (без отправки)
  python scripts/run_daily.py --send        # Полный цикл: каналы → новости → рассылка
  python scripts/run_daily.py --weekly      # Сводка за неделю (вместо дня)
  python scripts/run_daily.py --dry-run     # Превью без отправки
  python scripts/run_daily.py --summary-only  # Сохранить сводку в файл (summary.txt)
  python scripts/run_daily.py --summary-only out.txt  # Сохранить сводку в указанный файл
  python scripts/run_daily.py --verify      # Проверить доступность подписчиков
  ```

Вариант B: по расписанию (cron)
- См. mycron.txt. Пример (подставьте свои пути):
  ```bash
  # Каждую минуту поддерживать запуск бота (или используйте systemd/pm2):
  * * * * * cd /path/to/actual_news_bot && /path/to/actual_news_bot/venv/bin/python scripts/get_users.py >> users.log 2>&1
  
  # Каждый день в 09:00 собирать и рассылать дайджест:
  0 9 * * * cd /path/to/actual_news_bot && /path/to/actual_news_bot/venv/bin/python scripts/run_daily.py --send >> bot.log 2>&1
  ```

Вариант C: Docker
- Соберите образ:
  ```bash
  docker build -t news-bot .
  ```
- Запустите контейнер:
  ```bash
  docker run -d --name news-bot \
    -v $(pwd)/anon_news.session:/app/anon_news.session \
    -v $(pwd)/subscribers.json:/app/subscribers.json \
    -e API_ID=your_api_id \
    -e API_HASH=your_api_hash \
    -e TELEGRAM_BOT_TOKEN=your_token \
    -e OPENAI_API_KEY=your_key \
    news-bot
  ```

Вариант D: Облачный деплой (Railway, Render)
- См. QUICK_DEPLOY.md для быстрого старта или DEPLOY.md для подробных инструкций.
- Railway/Render автоматически используют Procfile для запуска бота.
- Для ежедневной рассылки настройте Scheduled Task (Railway) или Cron Job (Render).

Данные и логи
- subscribers.json
  - Автоматически поддерживается scripts/get_users.py при /start и любом сообщении.
  - Формат: { "subscribers": [ { "user_id": ..., "username": ..., "first_name": ..., "last_name": ..., "added_at": ... } ] }
  - После рассылки scripts/run_daily.py и src/news_bot_part.py автоматически удаляют заблокировавших бота пользователей.
  - Перед рассылкой создается бэкап с timestamp: subscribers.json.YYYYMMDD-HHMMSS.bak
- channels.json
  - Генерируется src/get_channels.py или scripts/run_daily.py --channels на основе папки FOLDER_NAME.
  - Ключевые поля: username, id, title (и другие метаданные канала).
- sent_messages.log
  - Лог каждой отправленной части сообщения: время (UTC), user_id, message_id, длина и ПОЛНЫЙ текст.
  - Важно: файл хранит содержимое рассылок. Учитывайте приватность и ротацию логов.
- sent_summaries.log
  - Лог полных саммари перед рассылкой (с датой и временем отправки).
  - Сохраняется автоматически перед рассылкой в scripts/run_daily.py и src/news_bot_part.py.
- users.log, bot.log
  - Стандартные логи работы скриптов (если перенаправлен stdout/stderr).

Как это работает (коротко)
1) scripts/get_users.py
   - Поднимает приложение python-telegram-bot и регистрирует хендлеры:
     - /start — добавляет пользователя в subscribers.json
     - /stop — удаляет из подписки
     - /channels — показывает список каналов из channels.json
     - /status — показывает статус подписки
     - /recommend_channel — короткий диалог для рекомендаций (сохраняет в channel_recommendations.txt)
     - /help — справка по командам
     - Любое текстовое сообщение — также добавляет в подписчики (если еще не подписан)

2) scripts/run_daily.py (рекомендуемый способ запуска рассылки)
   - Единая точка входа с аргументами командной строки:
     - --channels — обновить channels.json из телеграм-папки
     - --verify — проверить доступность подписчиков перед рассылкой
     - --news — только собрать новости (без отправки)
     - --send — полный цикл: каналы → новости → суммаризация → рассылка
     - --weekly — сводка за неделю (по умолчанию за день)
     - --dry-run — превью без реальной отправки
     - --summary-only — сохранить сводку в файл (по умолчанию summary.txt)
   - По умолчанию (без аргументов) выполняет --channels + --send
   - Создает бэкапы файлов перед изменением
   - Сохраняет саммари в sent_summaries.log перед рассылкой

3) src/news_bot_part.py (модуль с функциями)
   - get_news() — через Telethon собирает сообщения за «вчера» (UTC) из каналов, добавляя ссылку-источник вида https://t.me/<username>/<id>
   - summarize_news() — отправляет текст в OpenAI Chat Completions (модель: gpt-4.1-mini) для суммаризации по заданному формату разделов
   - send_news() — дробит итог на части ≤4096 символов и рассылает подписчикам через Bot API
   - Автоматически фильтрует недоступных пользователей (заблокировавших бота) и обновляет subscribers.json
   - Поддерживает режим отладки (DEBUG_MODE) для тестовой рассылки

Настройка модели и подсказки
- Модель суммаризации в коде: gpt-4.1-mini (OpenAI). При необходимости можно заменить на другую совместимую модель и скорректировать промпт в функции summarize_news().
- Формат результата: разделы «Главное», «AI/ML» (опционально), «Остальное кратко». Источники (t.me) указываются в скобках у каждого пункта.

Переменные окружения
- config.py поддерживает переменные окружения (приоритет над значениями по умолчанию):
  - API_ID, API_HASH — учетные данные Telegram
  - TELEGRAM_BOT_TOKEN — токен бота
  - OPENAI_API_KEY — ключ OpenAI
  - FOLDER_NAME — название папки Telegram
  - SUBSCRIBERS_FILE — путь к файлу подписчиков
  - DEBUG_MODE — режим отладки ('True'/'False')
  - DEBUG_USER_IDS — список user_id через запятую
- Это позволяет безопасно деплоить в облако без коммита секретов в репозиторий.
- Поддержка .env файла не реализована (можно добавить через python-dotenv при необходимости).

Тестирование
- Автотестов пока нет.
- Режим отладки:
  - Установите DEBUG_MODE=True в config.py или переменной окружения
  - Укажите DEBUG_USER_IDS (список user_id для тестовой рассылки)
  - Рассылка будет выполняться только указанным пользователям
- Режим «сухого запуска»:
  - `python scripts/run_daily.py --dry-run` — покажет превью саммари без отправки
  - `python scripts/run_daily.py --summary-only` — сохранит сводку в файл
  - `python scripts/run_daily.py --news` — только соберет новости без отправки
- Проверка доступности подписчиков:
  - `python scripts/run_daily.py --verify` — проверит доступность всех подписчиков перед рассылкой
- TODO:
  - Автотесты для split_message (дробление длинных сообщений)
  - Автотесты для загрузки/сохранения подписчиков
  - Автотесты для загрузки каналов и сериализации

Безопасность и эксплуатация
- Не коммитьте реальные секреты (api_id, api_hash, telegram_bot_token, openai_api_key) в публичные репозитории.
- Используйте переменные окружения для секретов при деплое в облако (см. DEPLOY.md).
- Храните config.py отдельно или используйте шаблон config_example.py.
- Файлы сессий (*.session) и логи могут содержать чувствительные данные:
  - sent_messages.log — содержит полные тексты рассылок
  - sent_summaries.log — содержит полные саммари
  - Настройте ротацию логов и ограничьте доступ к ним
- Telegram и OpenAI имеют лимиты — при необходимости увеличьте задержки между отправками (asyncio.sleep в коде).
- Режим отладки (DEBUG_MODE) позволяет тестировать рассылку без отправки всем подписчикам.

Лицензия
- Файл LICENSE отсутствует.
- TODO: добавить LICENSE (например, MIT/Apache-2.0) и обновить раздел.

Диагностика
- Telethon при первом запуске может запросить логин/код для создания сессии (anon_news.session).
  - Создать сессию локально: `python scripts/create_user_session.py`
  - Можно задать номер телефона через переменную окружения `TELEGRAM_PHONE`
  - Файл сессии нужно загрузить на сервер при деплое в облако (см. DEPLOY.md).
- Если каналы не подтягиваются:
  - Проверьте соответствие FOLDER_NAME реальной папке с нужными каналами
  - Запустите `python scripts/run_daily.py --channels` для обновления channels.json
  - Проверьте, что папка содержит каналы и они доступны вашему аккаунту
- Пустая рассылка:
  - Значит за вчера (UTC) не было сообщений; отправка будет пропущена
  - Проверьте логи для подтверждения: "Нет новостей за вчера — рассылка пропущена"
- Ошибки OpenAI:
  - Проверьте ключ и квоты на https://platform.openai.com/
  - Убедитесь в доступе к сети
  - Проверьте модель (по умолчанию: gpt-4.1-mini)
- Ошибки рассылки:
  - Проверьте sent_messages.log для деталей
  - Пользователи, заблокировавшие бота, автоматически удаляются из subscribers.json
  - Используйте `python scripts/run_daily.py --verify` для проверки доступности подписчиков
- Логи и бэкапы:
  - Бэкапы файлов создаются автоматически перед изменением (формат: filename.YYYYMMDD-HHMMSS.bak)
  - Проверяйте логи на наличие [WARN] и [ERROR] сообщений

Дополнительные утилиты
- scripts/backfill_users_once.py — утилита для одноразового заполнения данных подписчиков
- scripts/update_subscribers_data.py — утилита для обновления данных подписчиков
- scripts/upload_session.py — утилита для загрузки файла сессии Telethon

Деплой в облако
- Подробные инструкции: см. DEPLOY.md (Railway, Render, DigitalOcean, VPS)
- Быстрый старт: см. QUICK_DEPLOY.md (Railway, Render)
- Docker: используйте Dockerfile для контейнеризации
- Railway/Render: используйте Procfile для автоматического запуска

Примечания
- README отражает текущее состояние кода. TODO‑пункты обозначают планируемые улучшения.
- Для продакшена рекомендуется использовать переменные окружения вместо значений по умолчанию в config.py.
- Режим отладки (DEBUG_MODE) полезен для тестирования перед массовой рассылкой.