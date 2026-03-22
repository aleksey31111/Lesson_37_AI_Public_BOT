# telegram_bot.py - исправленная версия
import os
import sqlite3
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters, CallbackContext

logger = logging.getLogger(__name__)


class SimpleDatabase:
    def __init__(self, db_path='monitoring.db'):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TEXT,
                preferences TEXT DEFAULT '{}'
            )
        ''')

        # Таблица сайтов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS websites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                name TEXT,
                is_active INTEGER DEFAULT 1,
                check_interval INTEGER DEFAULT 300,
                created_at TEXT
            )
        ''')

        # Таблица подписок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                website_id INTEGER NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT,
                UNIQUE(user_id, website_id)
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("База данных инициализирована")

    def get_user(self, telegram_id):
        """Получает пользователя по telegram_id"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'telegram_id': row[1],
                    'username': row[2],
                    'first_name': row[3],
                    'last_name': row[4],
                    'created_at': row[5],
                    'preferences': row[6]
                }
            return None
        except Exception as e:
            logger.error(f"Ошибка получения пользователя: {e}")
            return None
        finally:
            conn.close()

    def add_user(self, telegram_id, username=None, first_name=None, last_name=None):
        """Добавляет пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Проверяем существует ли пользователь
            cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
            existing = cursor.fetchone()

            if existing:
                return {
                    'id': existing[0],
                    'telegram_id': existing[1],
                    'username': existing[2],
                    'first_name': existing[3],
                    'last_name': existing[4]
                }

            cursor.execute('''
                INSERT INTO users (telegram_id, username, first_name, last_name, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (telegram_id, username, first_name, last_name, datetime.now().isoformat()))

            conn.commit()
            cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
            row = cursor.fetchone()

            return {
                'id': row[0],
                'telegram_id': row[1],
                'username': row[2],
                'first_name': row[3],
                'last_name': row[4]
            }
        except Exception as e:
            logger.error(f"Ошибка добавления пользователя: {e}")
            return None
        finally:
            conn.close()

    def add_website(self, url, name=None):
        """Добавляет сайт"""
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
            logger.error(f"Ошибка добавления сайта: {e}")
            return None
        finally:
            conn.close()

    def get_website_by_url(self, url):
        """Получает сайт по URL"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT * FROM websites WHERE url = ?', (url,))
            row = cursor.fetchone()
            if row:
                return {'id': row[0], 'url': row[1], 'name': row[2]}
            return None
        finally:
            conn.close()

    def get_website_by_id(self, website_id):
        """Получает сайт по ID"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT * FROM websites WHERE id = ?', (website_id,))
            row = cursor.fetchone()
            if row:
                return {'id': row[0], 'url': row[1], 'name': row[2]}
            return None
        finally:
            conn.close()

    def subscribe(self, user_id, website_id):
        """Подписывает пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO subscriptions (user_id, website_id, created_at)
                VALUES (?, ?, ?)
            ''', (user_id, website_id, datetime.now().isoformat()))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка подписки: {e}")
            return False
        finally:
            conn.close()

    def unsubscribe(self, user_id, website_id):
        """Отписывает пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                DELETE FROM subscriptions WHERE user_id = ? AND website_id = ?
            ''', (user_id, website_id))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка отписки: {e}")
            return False
        finally:
            conn.close()

    def get_user_subscriptions(self, user_id):
        """Получает все подписки пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT s.*, w.url, w.name 
                FROM subscriptions s
                JOIN websites w ON s.website_id = w.id
                WHERE s.user_id = ?
            ''', (user_id,))

            rows = cursor.fetchall()
            subscriptions = []
            for row in rows:
                subscriptions.append({
                    'id': row[0],
                    'user_id': row[1],
                    'website_id': row[2],
                    'is_active': row[3],
                    'created_at': row[4],
                    'website': {
                        'url': row[5],
                        'name': row[6]
                    }
                })
            return subscriptions
        finally:
            conn.close()

    def get_all_websites(self):
        """Получает все сайты"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT * FROM websites WHERE is_active = 1')
            rows = cursor.fetchall()
            websites = []
            for row in rows:
                websites.append({
                    'id': row[0],
                    'url': row[1],
                    'name': row[2],
                    'is_active': row[3],
                    'check_interval': row[4],
                    'created_at': row[5]
                })
            return websites
        finally:
            conn.close()


# Клавиатуры
def get_main_keyboard():
    keyboard = [
        ["📊 Статус", "📋 Мои подписки"],
        ["⚙️ Настройки", "💡 Рекомендации"],
        ["📖 Помощь"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


class SmartMonitorBot:
    def __init__(self):
        self.db = SimpleDatabase()
        self.token = os.getenv('TELEGRAM_TOKEN')

        if not self.token:
            raise ValueError("TELEGRAM_TOKEN not found")

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
        dp.add_handler(CallbackQueryHandler(self.handle_callback))

    def start(self, update: Update, context: CallbackContext):
        user = update.effective_user

        # Добавляем пользователя в БД
        db_user = self.db.get_user(user.id)
        if not db_user:
            db_user = self.db.add_user(user.id, user.username, user.first_name, user.last_name)

        welcome_text = f"""
👋 *Добро пожаловать, {user.first_name}!*

🤖 *Smart Monitor Bot* - умная система мониторинга веб-сайтов.

✨ *Что я умею:*
• 📡 Отслеживать изменения на сайтах
• 🎯 Персонализированные уведомления
• 🎓 Учиться на ваших реакциях

📝 *Быстрый старт:*
1. /monitor https://github.com/status - добавить сайт
2. /subscribe https://github.com/status - подписаться
3. /status - проверить статус

💡 *Совет:* Оценивайте уведомления 👍/👎 для улучшения фильтрации!
        """

        update.message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=get_main_keyboard())

    def help(self, update: Update, context: CallbackContext):
        help_text = """
📖 *Помощь по командам*

🔹 *Основные:*
• /start - запустить бота
• /help - эта справка
• /status - статус мониторинга

🔹 *Мониторинг:*
• /monitor [url] - добавить сайт
• /subscribe [url] - подписаться
• /unsubscribe [url] - отписаться
• /list - мои подписки

💡 *Примеры:*
/monitor https://github.com/status
/subscribe https://github.com/status

📌 *Популярные сайты:*
• https://www.githubstatus.com
• https://status.cloud.google.com
• https://status.aws.amazon.com
        """
        update.message.reply_text(help_text, parse_mode='Markdown')

    def status(self, update: Update, context: CallbackContext):
        user = self.db.get_user(update.effective_user.id)
        if not user:
            update.message.reply_text("❌ Пользователь не найден. Используйте /start для регистрации")
            return

        subscriptions = self.db.get_user_subscriptions(user['id'])

        # Получаем общую статистику
        all_websites = self.db.get_all_websites()

        status_text = f"""
📊 *Статус мониторинга*

👥 *Ваш ID:* {user['id']}
📋 *Ваших подписок:* {len(subscriptions)}
🌐 *Всего сайтов в системе:* {len(all_websites)}

📡 *Ваши активные сайты:*
{chr(10).join([f"• {s['website']['name']}" for s in subscriptions]) if subscriptions else "📭 Нет активных подписок"}

💡 *Совет:* Добавьте больше сайтов через /monitor
        """

        update.message.reply_text(status_text, parse_mode='Markdown')

    def monitor_command(self, update: Update, context: CallbackContext):
        if not context.args:
            update.message.reply_text(
                "❌ Укажите URL сайта\n\n"
                "Пример: /monitor https://github.com/status\n\n"
                "📌 *Популярные сайты:*\n"
                "• https://www.githubstatus.com\n"
                "• https://status.cloud.google.com\n"
                "• https://status.aws.amazon.com",
                parse_mode='Markdown'
            )
            return

        url = context.args[0]
        if not url.startswith('http'):
            url = 'https://' + url

        # Проверяем, существует ли уже сайт
        existing = self.db.get_website_by_url(url)
        if existing:
            update.message.reply_text(
                f"ℹ️ Сайт {url} уже есть в системе!\n\n"
                f"Используйте /subscribe {url} для подписки"
            )
            return

        website = self.db.add_website(url)

        if website:
            update.message.reply_text(
                f"✅ Сайт {url} добавлен!\n\n"
                f"📊 *Информация:*\n"
                f"• ID: {website['id']}\n"
                f"• Название: {website['name']}\n\n"
                f"Используйте /subscribe {url} для подписки на уведомления",
                parse_mode='Markdown'
            )
        else:
            update.message.reply_text(f"❌ Не удалось добавить {url}")

    def subscribe(self, update: Update, context: CallbackContext):
        if not context.args:
            update.message.reply_text("❌ Укажите URL: /subscribe https://site.com")
            return

        url = context.args[0]
        user = self.db.get_user(update.effective_user.id)

        if not user:
            user = self.db.add_user(update.effective_user.id,
                                    update.effective_user.username,
                                    update.effective_user.first_name,
                                    update.effective_user.last_name)

        website = self.db.get_website_by_url(url)
        if not website:
            update.message.reply_text(
                f"❌ Сайт {url} не найден.\n\n"
                f"Сначала добавьте его: /monitor {url}"
            )
            return

        # Проверяем, не подписан ли уже
        subscriptions = self.db.get_user_subscriptions(user['id'])
        for sub in subscriptions:
            if sub['website']['url'] == url:
                update.message.reply_text(f"ℹ️ Вы уже подписаны на {url}")
                return

        success = self.db.subscribe(user['id'], website['id'])

        if success:
            update.message.reply_text(
                f"✅ Подписка на {url} оформлена!\n\n"
                f"📊 *Статистика:*\n"
                f"• Всего подписок: {len(subscriptions) + 1}\n\n"
                f"💡 *Совет:* Используйте /list для просмотра всех подписок",
                parse_mode='Markdown'
            )
        else:
            update.message.reply_text("❌ Ошибка подписки")

    def unsubscribe(self, update: Update, context: CallbackContext):
        if not context.args:
            # Показываем список подписок
            user = self.db.get_user(update.effective_user.id)
            if user:
                subscriptions = self.db.get_user_subscriptions(user['id'])
                if subscriptions:
                    text = "📋 *Ваши подписки:*\n\n"
                    for sub in subscriptions:
                        text += f"• {sub['website']['name']} - `{sub['website']['url']}`\n"
                    text += "\nДля отписки используйте: /unsubscribe [url]"
                    update.message.reply_text(text, parse_mode='Markdown')
                else:
                    update.message.reply_text("📭 У вас нет активных подписок")
            else:
                update.message.reply_text("❌ Пользователь не найден")
            return

        url = context.args[0]
        user = self.db.get_user(update.effective_user.id)

        if not user:
            update.message.reply_text("❌ Пользователь не найден. Используйте /start")
            return

        website = self.db.get_website_by_url(url)
        if not website:
            update.message.reply_text(f"❌ Сайт {url} не найден")
            return

        success = self.db.unsubscribe(user['id'], website['id'])

        if success:
            update.message.reply_text(f"✅ Отписка от {url} выполнена")
        else:
            update.message.reply_text("❌ Вы не подписаны на этот сайт")

    def list_subscriptions(self, update: Update, context: CallbackContext):
        user = self.db.get_user(update.effective_user.id)

        if not user:
            update.message.reply_text(
                "❌ Пользователь не найден.\n\n"
                "Используйте /start для регистрации"
            )
            return

        subscriptions = self.db.get_user_subscriptions(user['id'])

        if not subscriptions:
            update.message.reply_text(
                "📭 У вас нет активных подписок\n\n"
                "Добавьте сайт: /monitor [url]\n"
                "Подпишитесь: /subscribe [url]\n\n"
                "📌 *Пример:*\n"
                "/monitor https://github.com/status\n"
                "/subscribe https://github.com/status"
            )
            return

        text = "📋 *Ваши подписки:*\n\n"
        for i, sub in enumerate(subscriptions, 1):
            text += f"{i}. *{sub['website']['name']}*\n"
            text += f"   📍 `{sub['website']['url']}`\n"
            text += f"   🕐 Подписано: {sub['created_at'][:10]}\n\n"

        text += f"📊 *Всего подписок:* {len(subscriptions)}"

        update.message.reply_text(text, parse_mode='Markdown')

    def handle_message(self, update: Update, context: CallbackContext):
        text = update.message.text

        if text == "📊 Статус":
            self.status(update, context)
        elif text == "📋 Мои подписки":
            self.list_subscriptions(update, context)
        elif text == "⚙️ Настройки":
            update.message.reply_text(
                "⚙️ *Настройки*\n\n"
                "Настройки будут доступны в следующей версии.\n\n"
                "Пока вы можете:\n"
                "• /subscribe - подписаться на сайты\n"
                "• /unsubscribe - отписаться\n"
                "• /list - посмотреть подписки",
                parse_mode='Markdown'
            )
        elif text == "💡 Рекомендации":
            update.message.reply_text(
                "💡 *Рекомендации ИИ:*\n\n"
                "1️⃣ *Добавьте статус-страницы:*\n"
                "   • GitHub Status\n"
                "   • Google Cloud Status\n"
                "   • AWS Status\n\n"
                "2️⃣ *Настройте подписки:*\n"
                "   • Используйте /subscribe для подписки\n"
                "   • Используйте /unsubscribe для отписки\n\n"
                "3️⃣ *Популярные сайты для мониторинга:*\n"
                "   • https://www.githubstatus.com\n"
                "   • https://status.cloud.google.com\n"
                "   • https://status.aws.amazon.com\n"
                "   • https://status.slack.com\n\n"
                "💡 *Совет:* Чем больше сайтов вы добавите, тем полезнее будут уведомления!",
                parse_mode='Markdown'
            )
        elif text == "📖 Помощь":
            self.help(update, context)
        else:
            update.message.reply_text(
                "🤖 Неизвестная команда\n\n"
                "Используйте /help для списка доступных команд\n\n"
                "💡 *Быстрые команды:*\n"
                "• /status - статус мониторинга\n"
                "• /list - мои подписки\n"
                "• /monitor [url] - добавить сайт",
                parse_mode='Markdown'
            )

    def handle_callback(self, update: Update, context: CallbackContext):
        query = update.callback_query
        query.answer()

        data = query.data

        if data == "like":
            query.edit_message_reply_markup(reply_markup=None)
            query.edit_message_text(
                query.message.text + "\n\n✅ Спасибо за оценку!",
                parse_mode='Markdown'
            )
        elif data == "dislike":
            query.edit_message_reply_markup(reply_markup=None)
            query.edit_message_text(
                query.message.text + "\n\n👍 Спасибо за отзыв! Мы работаем над улучшением.",
                parse_mode='Markdown'
            )
        else:
            query.edit_message_text("✅ Готово!")

    def run(self):
        print("\n🚀 Бот запускается...")
        print("💡 Откройте Telegram и отправьте /start")
        print("🛑 Нажмите Ctrl+C для остановки\n")
        self.updater.start_polling()
        self.updater.idle()


# Импортируем os для получения токена
if __name__ == "__main__":
    bot = SmartMonitorBot()
    bot.run()