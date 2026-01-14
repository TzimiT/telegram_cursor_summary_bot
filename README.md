Clean News Bot — ежедневный дайджест из Telegram

О проекте
- Репозиторий содержит два кооперативных скрипта на Python:
  - get_users.py — Telegram‑бот для подписки/отписки пользователей и служебных команд.
  - news_bot_part.py — ежедневный агрегатор: читает каналы из папки Telegram, суммаризирует посты за вчера при помощи OpenAI и рассылает дайджест подписчикам.

Стек
- Python (asyncio)
- Библиотеки:
  - telethon — клиент для чтения каналов/папок Telegram
  - python-telegram-bot — Bot API для общения с пользователями
  - openai — суммаризация через Chat Completions API
- Управление пакетами: pip (рекомендуется virtualenv)

Точки входа и вспомогательные файлы
- get_users.py — запускает бота с командами: /start, /stop, /channels, /status, /recommend_channel. Должен работать постоянно (cron/pm2/systemd/Screen).
- news_bot_part.py — подключается к Telegram (Telethon), собирает посты за вчера из каналов в channels.json, вызывает OpenAI для суммаризации и отправляет результат всем активным подписчикам. Запускать по расписанию (cron).
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
- config.py — локальные секреты и настройки (не публикуйте реальные ключи в публичный репозиторий).
- get_channels.py — утилита для выгрузки информации о каналах из папки Telegram в channels.json.
- get_users.py — точка входа бота подписчиков (python-telegram-bot).
- news_bot_part.py — дневной агрегатор/рассылщик (Telethon + OpenAI).
- channels.json — список каналов для агрегации (формируется/обновляется get_channels.py).
- subscribers.json — список подписчиков в формате { "subscribers": [ { ... } ] }.
- mycron.txt — примеры cron.
- Логи: users.log, bot.log (+ архивные варианты).
- Файлы сессий Telethon: anon.session, anon_news.session.
- Прочее: commands.txt, recommended_channels.txt, tz*.txt.

Конфигурация
1) Создайте config.py на основе шаблона:
   - Скопируйте config_example.py → config.py и заполните:
     - api_id, api_hash — из https://my.telegram.org
     - openai_api_key — ключ OpenAI
     - telegram_bot_token — токен бота от @BotFather
     - FOLDER_NAME — название папки Telegram с целевыми каналами (например, "GPT")
     - TARGET_CHAT_ID — зарезервировано под расширения (в основном не используется)
     - SUBSCRIBERS_FILE — путь к JSON со списком подписчиков (по умолчанию subscribers.json)

2) Telegram:
   - В приложении Telegram создайте/используйте папку с именем FOLDER_NAME и добавьте туда каналы для агрегации.

3) OpenAI:
   - Ключ получите на https://platform.openai.com/ и укажите в config.py.

Установка
- Создайте и активируйте виртуальное окружение, установите зависимости:
  - python -m venv venv
  - source venv/bin/activate  # macOS/Linux
    # или venv\\Scripts\\activate  # Windows
  - pip install --upgrade pip
  - pip install telethon python-telegram-bot openai

Запуск
Вариант A: вручную
- Запустить бота подписчиков (должен работать постоянно):
  - python get_users.py

- Прогнать агрегатор один раз (для проверки):
  - python news_bot_part.py

Вариант B: по расписанию (cron)
- См. mycron.txt. Пример (подставьте свои пути):
  - Каждую минуту поддерживать запуск бота:
    * * * * * cd /path/to/clean_news_bot && /path/to/clean_news_bot/venv/bin/python get_users.py >> users.log 2>&1
  - Каждый день в 09:00 собирать и рассылать дайджест:
    0 9 * * * cd /path/to/clean_news_bot && /path/to/clean_news_bot/venv/bin/python news_bot_part.py >> bot.log 2>&1

Данные и логи
- subscribers.json
  - Автоматически поддерживается get_users.py при /start и любом сообщении.
  - Формат: { "subscribers": [ { "user_id": ..., "username": ..., ... } ] }
  - После рассылки news_bot_part.py оставляет только активных получателей.
- channels.json
  - Генерируется get_channels.py на основе папки FOLDER_NAME.
  - Ключевые поля: username, id.
- sent_messages.log
  - Лог каждой отправленной части сообщения: время (UTC), user_id, message_id, длина и ПОЛНЫЙ текст.
  - Важно: файл хранит содержимое рассылок. Учитывайте приватность и ротацию логов.

Как это работает (коротко)
1) get_users.py
   - Поднимает приложение python-telegram-bot и регистрирует хендлеры:
     /start — добавляет пользователя в subscribers.json
     /stop — удаляет из подписки
     /channels — показывает список каналов из channels.json
     /status — показывает статус подписки
     /recommend_channel — короткий диалог для рекомендаций
2) news_bot_part.py
   - Через Telethon подключается к Telegram, при первом запуске создаёт .session.
   - Вызывает get_channels_fullinfo_from_folder(...) и обновляет channels.json по папке FOLDER_NAME.
   - Собирает сообщения за «вчера» (UTC) из перечисленных каналов, добавляя ссылку-источник вида https://t.me/<username>/<id>.
   - Отправляет текст в OpenAI Chat Completions (модель по умолчанию: gpt-4.1-mini) для суммаризации по заданному формату разделов.
   - Дробит итог на части ≤4096 символов и рассылает подписчикам через Bot API.

Настройка модели и подсказки
- Модель суммаризации в коде: gpt-4.1-mini (OpenAI). При необходимости можно заменить на другую совместимую модель и скорректировать промпт в функции summarize_news().
- Формат результата: разделы «Главное», «AI/ML» (опционально), «Остальное кратко». Источники (t.me) указываются в скобках у каждого пункта.

Переменные окружения
- Сейчас используется config.py; поддержка .env не реализована.
- TODO: добавить опциональную загрузку конфигурации из переменных окружения/файла .env.

Тестирование
- Автотестов пока нет.
- TODO:
  - Тестирование split_message (дробление длинных сообщений)
  - Загрузка/сохранение подписчиков и «очистка» неактивных
  - Загрузка каналов и сериализация
  - Режим «сухого запуска» агрегатора (без реальной отправки)

Безопасность и эксплуатация
- Не коммитьте реальные секреты (api_id, api_hash, telegram_bot_token, openai_api_key) в публичные репозитории.
- Храните config.py отдельно или используйте шаблон config_example.py.
- Файлы сессий (*.session) и логи могут содержать чувствительные данные.
- Telegram и OpenAI имеют лимиты — при необходимости увеличьте задержки между отправками.

Лицензия
- Файл LICENSE отсутствует.
- TODO: добавить LICENSE (например, MIT/Apache-2.0) и обновить раздел.

Диагностика
- Telethon при первом запуске может запросить логин/код для создания сессии.
- Если каналы не подтягиваются — проверьте соответствие FOLDER_NAME реальной папке с нужными каналами.
- Пустая рассылка — значит за вчера (UTC) не было сообщений; отправка будет пропущена.
- Ошибки OpenAI — проверьте ключ и квоты; убедитесь в доступе к сети.

Примечания
- README отражает текущее состояние кода. TODO‑пункты обозначают планируемые улучшения.
