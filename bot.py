# bot.py - оптимизированная версия для Railway
import os
import sys
import sqlite3
import logging
from datetime import datetime
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Проверка токена
TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TOKEN:
    logger.error("TELEGRAM_TOKEN not set!")
    sys.exit(1)

try:
    from telegram import Update, ReplyKeyboardMarkup
    from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
except ImportError as e:
    logger.error(f"Failed to import telegram: {e}")
    logger.info("Installing python-telegram-bot...")
    os.system("pip install python-telegram-bot==13.7")
    from telegram import Update, ReplyKeyboardMarkup
    from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext


class SimpleDatabase:
    def __init__(self):
        self.db_path = 'monitoring.db'
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS websites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                name TEXT,
                created_at TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                website_id INTEGER NOT NULL,
                created_at TEXT,
                UNIQUE(user_id, website_id)
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("Database initialized")

    def get_user(self, telegram_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {'id': row[0], 'telegram_id': row[1]}
        return None

    def add_user(self, telegram_id, username=None, first_name=None, last_name=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO users (telegram_id, username, first_name, last_name, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (telegram_id, username, first_name, last_name, datetime.now().isoformat()))
            conn.commit()
            return self.get_user(telegram_id)
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            return None
        finally:
            conn.close()

    def add_website(self, url, name=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM websites WHERE url = ?', (url,))
            existing = cursor.fetchone()
            if existing:
                return {'id': existing[0], 'url': existing[1], 'name': existing[2]}

            cursor.execute('''
                INSERT INTO websites (url, name, created_at)
                VALUES (?, ?, ?)
            ''', (url, name or url, datetime.now().isoformat()))
            conn.commit()
            cursor.execute('SELECT * FROM websites WHERE url = ?', (url,))
            row = cursor.fetchone()
            return {'id': row[0], 'url': row[1], 'name': row[2]}
        except Exception as e:
            logger.error(f"Error adding website: {e}")
            return None
        finally:
            conn.close()

    def get_website_by_url(self, url):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM websites WHERE url = ?', (url,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {'id': row[0], 'url': row[1], 'name': row[2]}
        return None

    def subscribe(self, user_id, website_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO subscriptions (user_id, website_id, created_at)
                VALUES (?, ?, ?)
            ''', (user_id, website_id, datetime.now().isoformat()))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error subscribing: {e}")
            return False
        finally:
            conn.close()

    def unsubscribe(self, user_id, website_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM subscriptions WHERE user_id = ? AND website_id = ?',
                           (user_id, website_id))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error unsubscribing: {e}")
            return False
        finally:
            conn.close()

    def get_user_subscriptions(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.*, w.url, w.name 
            FROM subscriptions s
            JOIN websites w ON s.website_id = w.id
            WHERE s.user_id = ?
        ''', (user_id,))
        rows = cursor.fetchall()
        conn.close()

        subscriptions = []
        for row in rows:
            subscriptions.append({
                'id': row[0],
                'user_id': row[1],
                'website_id': row[2],
                'created_at': row[3],
                'website': {'url': row[4], 'name': row[5]}
            })
        return subscriptions


# Клавиатура
def get_main_keyboard():
    keyboard = [["📊 Статус", "📋 Подписки"], ["ℹ️ Помощь"]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


class MonitorBot:
    def __init__(self):
        self.db = SimpleDatabase()
        self.token = TOKEN
        self.updater = Updater(self.token, use_context=True)
        self._setup_handlers()

    def _setup_handlers(self):
        dp = self.updater.dispatcher

        dp.add_handler(CommandHandler("start", self.start))
        dp.add_handler(CommandHandler("help", self.help))
        dp.add_handler(CommandHandler("status", self.status))
        dp.add_handler(CommandHandler("monitor", self.monitor_command))
        dp.add_handler(CommandHandler("subscribe", self.subscribe))
        dp.add_handler(CommandHandler("unsubscribe", self.unsubscribe))
        dp.add_handler(CommandHandler("list", self.list_subscriptions))
        dp.add_handler(MessageHandler(Filters.text & ~Filters.command, self.handle_message))

    def start(self, update: Update, context: CallbackContext):
        user = update.effective_user
        self.db.add_user(user.id, user.username, user.first_name, user.last_name)

        welcome = f"""
👋 *Добро пожаловать, {user.first_name}!*

🤖 *Smart Monitor Bot* - система мониторинга сайтов.

📝 *Команды:*
• /monitor [url] - добавить сайт
• /subscribe [url] - подписаться
• /unsubscribe [url] - отписаться
• /list - мои подписки
• /status - статус
• /help - помощь

💡 *Пример:*
/monitor https://github.com/status
/subscribe https://github.com/status
        """
        update.message.reply_text(welcome, parse_mode='Markdown', reply_markup=get_main_keyboard())

    def help(self, update: Update, context: CallbackContext):
        help_text = """
📖 *Помощь*

🔹 /start - запуск
🔹 /monitor [url] - добавить сайт
🔹 /subscribe [url] - подписаться
🔹 /unsubscribe [url] - отписаться
🔹 /list - мои подписки
🔹 /status - статус
🔹 /help - помощь

💡 *Примеры:*
/monitor https://github.com/status
/subscribe https://github.com/status
        """
        update.message.reply_text(help_text, parse_mode='Markdown')

    def status(self, update: Update, context: CallbackContext):
        user = self.db.get_user(update.effective_user.id)
        if not user:
            update.message.reply_text("❌ Используйте /start для регистрации")
            return

        subscriptions = self.db.get_user_subscriptions(user['id'])

        text = f"""
📊 *Статус*

👥 *Подписок:* {len(subscriptions)}

📡 *Сайты:*
{chr(10).join([f"• {s['website']['name']}" for s in subscriptions]) if subscriptions else "📭 Нет подписок"}

💡 *Совет:* /monitor [url] - добавить сайт
        """
        update.message.reply_text(text, parse_mode='Markdown')

    def monitor_command(self, update: Update, context: CallbackContext):
        if not context.args:
            update.message.reply_text("❌ Укажите URL: /monitor https://site.com")
            return

        url = context.args[0]
        if not url.startswith('http'):
            url = 'https://' + url

        website = self.db.add_website(url)
        if website:
            update.message.reply_text(f"✅ Сайт {url} добавлен!\n\n/subscribe {url} - подписаться")
        else:
            update.message.reply_text(f"❌ Ошибка добавления {url}")

    def subscribe(self, update: Update, context: CallbackContext):
        if not context.args:
            update.message.reply_text("❌ Укажите URL: /subscribe https://site.com")
            return

        url = context.args[0]
        user = self.db.get_user(update.effective_user.id)

        if not user:
            user = self.db.add_user(update.effective_user.id)

        website = self.db.get_website_by_url(url)
        if not website:
            update.message.reply_text(f"❌ Сайт {url} не найден.\n/monitor {url} - добавить")
            return

        if self.db.subscribe(user['id'], website['id']):
            update.message.reply_text(f"✅ Подписка на {url} оформлена!")
        else:
            update.message.reply_text("❌ Ошибка подписки")

    def unsubscribe(self, update: Update, context: CallbackContext):
        if not context.args:
            user = self.db.get_user(update.effective_user.id)
            if user:
                subs = self.db.get_user_subscriptions(user['id'])
                if subs:
                    text = "📋 *Подписки:*\n\n" + "\n".join([f"• {s['website']['url']}" for s in subs])
                    text += "\n\n/unsubscribe [url] - отписаться"
                    update.message.reply_text(text, parse_mode='Markdown')
                else:
                    update.message.reply_text("📭 Нет подписок")
            return

        url = context.args[0]
        user = self.db.get_user(update.effective_user.id)
        website = self.db.get_website_by_url(url)

        if user and website:
            if self.db.unsubscribe(user['id'], website['id']):
                update.message.reply_text(f"✅ Отписка от {url} выполнена")
            else:
                update.message.reply_text("❌ Вы не подписаны")

    def list_subscriptions(self, update: Update, context: CallbackContext):
        user = self.db.get_user(update.effective_user.id)
        if not user:
            update.message.reply_text("❌ Используйте /start")
            return

        subscriptions = self.db.get_user_subscriptions(user['id'])

        if not subscriptions:
            update.message.reply_text("📭 Нет подписок\n\n/monitor [url] - добавить сайт")
            return

        text = "📋 *Ваши подписки:*\n\n"
        for s in subscriptions:
            text += f"• {s['website']['name']}\n  `{s['website']['url']}`\n\n"
        update.message.reply_text(text, parse_mode='Markdown')

    def handle_message(self, update: Update, context: CallbackContext):
        text = update.message.text
        if text == "📊 Статус":
            self.status(update, context)
        elif text == "📋 Подписки":
            self.list_subscriptions(update, context)
        elif text == "ℹ️ Помощь":
            self.help(update, context)
        else:
            update.message.reply_text("Используйте /help")

    def run(self):
        logger.info("Bot starting...")
        logger.info(f"Bot token: {self.token[:10]}...")
        self.updater.start_polling()
        self.updater.idle()


if __name__ == "__main__":
    logger.info("Initializing bot...")
    try:
        bot = MonitorBot()
        bot.run()
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)