import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
)
import json
import os
from datetime import datetime

SUBSCRIBERS_FILE = "subscribers.json"
RECOMMEND_WAIT_INPUT = 1

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

def _load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.warning(f"[WARN] Ошибка чтения {path}: {e}")
        return default

def _save_json(path: str, data):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"[ERROR] Ошибка записи {path}: {e}")

def load_subscribers():
    if not os.path.exists(SUBSCRIBERS_FILE):
        logger.warning("[WARN] Файл с подписчиками не найден, список пуст")
        return []
    try:
        with open(SUBSCRIBERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('subscribers', [])
    except Exception as e:
        logger.error(f"[ERROR] Ошибка чтения {SUBSCRIBERS_FILE}: {e}")
        return []

def save_subscriber(user: Update.effective_user):
    subscribers = load_subscribers()
    user_ids = {sub['user_id'] for sub in subscribers if 'user_id' in sub}
    if user.id not in user_ids:
        subscriber = {
            "user_id": user.id,
            "username": user.username or "-",
            "first_name": user.first_name or "-",
            "last_name": user.last_name or "-",
            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        subscribers.append(subscriber)
        with open(SUBSCRIBERS_FILE, 'w', encoding='utf-8') as f:
            json.dump({"subscribers": subscribers}, f, ensure_ascii=False, indent=2)
        logger.info(f"Добавлен новый подписчик: {subscriber}")
        return True
    return False

def remove_subscriber(user_id):
    subscribers = load_subscribers()
    new_subs = [sub for sub in subscribers if 'user_id' in sub and sub['user_id'] != user_id]
    with open(SUBSCRIBERS_FILE, 'w', encoding='utf-8') as f:
        json.dump({"subscribers": new_subs}, f, ensure_ascii=False, indent=2)
    logger.info(f"Пользователь {user_id} удалён из подписчиков.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    was_added = save_subscriber(user)
    await update.message.reply_text(
        "Привет! Ты добавлен в рассылку новостей." if was_added else "Ты уже в списке рассылки."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Напиши любое сообщение, чтобы подписаться на рассылку.\n"
        "Доступные команды:\n"
        "/start — подписаться\n"
        "/stop — отписаться\n"
        "/recommend_channel — предложить канал для рассылки\n"
        "/channels — список каналов для агрегации\n"
        "/status — узнать статус подписки"
    )

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    was_added = save_subscriber(user)
    if was_added:
        await update.message.reply_text("Спасибо за сообщение! Ты подписан на рассылку.")
    else:
        await update.message.reply_text("Ты уже подписан.")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    remove_subscriber(user.id)
    await update.message.reply_text("Ты отписан от рассылки. Возвращайся, если что!")

# --- Recommend Channel Conversation ---

async def recommend_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Пожалуйста, отправьте ссылку на канал или username (@example), который вы хотите предложить для рассылки. "
        "Можно добавить комментарий."
    )
    return RECOMMEND_WAIT_INPUT

async def recommend_channel_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    rec_info = (
        f"date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
        f"user_id: {user.id} | username: @{user.username or '-'} | "
        f"name: {user.first_name or '-'} {user.last_name or '-'} | "
        f"recommend: {text}\n"
    )
    with open("channel_recommendations.txt", "a", encoding="utf-8") as f:
        f.write(rec_info)
    await update.message.reply_text("Спасибо! Ваша рекомендация отправлена администратору.")
    return ConversationHandler.END

async def recommend_channel_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Рекомендация отменена.")
    return ConversationHandler.END

# --- /channels: показать список каналов (читает channels.json) ---
async def channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open("channels.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            channels = data.get("channels", [])
        if not channels:
            await update.message.reply_text("Список каналов пуст.")
            return
        msg = "Список каналов для агрегации:\n" + "\n".join(
            f"@{c['username']}" if c.get('username') else c.get('title', '-') for c in channels
        )
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"Не удалось получить список каналов: {e}")

# --- /status: статус подписки ---
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    subscribers = load_subscribers()
    is_subscribed = any('user_id' in sub and sub['user_id'] == user.id for sub in subscribers)
    if is_subscribed:
        await update.message.reply_text("Ты подписан на рассылку ✅")
    else:
        await update.message.reply_text("Ты не подписан на рассылку.")

def main():
    import config  # импортирует telegram_bot_token из твоего конфига

    app = ApplicationBuilder().token(config.telegram_bot_token).build()

    # Основные команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("channels", channels_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), echo))

    # Recommend channel
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("recommend_channel", recommend_channel_start)],
        states={
            RECOMMEND_WAIT_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recommend_channel_receive)
            ],
        },
        fallbacks=[CommandHandler("cancel", recommend_channel_cancel)],
    )
    app.add_handler(conv_handler)

    logger.info("Бот запущен, ожидает сообщений...")
    app.run_polling()

if __name__ == '__main__':
    main()
