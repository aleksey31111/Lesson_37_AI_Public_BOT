#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Smart Monitor Bot - Production Ready for Railway
"""

import os
import sys
import sqlite3
import logging
import json
import requests
import hashlib
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv
from bs4 import BeautifulSoup

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
    logger.error("❌ TELEGRAM_TOKEN not set!")
    logger.info("Please set TELEGRAM_TOKEN in environment variables")
    sys.exit(1)

# Импорт Telegram
try:
    from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters, CallbackContext
except ImportError as e:
    logger.error(f"Failed to import telegram: {e}")
    sys.exit(1)


# ==================== DATABASE ====================

class Database:
    """Database handler with SQLite"""

    def __init__(self):
        self.db_path = 'monitoring.db'
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Users table
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

        # Websites table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS websites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                name TEXT,
                last_hash TEXT,
                last_content TEXT,
                last_check TEXT,
                check_count INTEGER DEFAULT 0,
                change_count INTEGER DEFAULT 0,
                created_at TEXT
            )
        ''')

        # Subscriptions table
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

        # Changes history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                website_id INTEGER NOT NULL,
                change_type TEXT,
                change_summary TEXT,
                change_details TEXT,
                importance_score REAL,
                detected_at TEXT
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("✅ Database initialized")

    # User methods
    def get_user(self, telegram_id: int) -> Optional[Dict]:
        """Get user by telegram_id"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'id': row[0],
                'telegram_id': row[1],
                'username': row[2],
                'first_name': row[3],
                'last_name': row[4],
                'created_at': row[5],
                'preferences': json.loads(row[6]) if row[6] else {}
            }
        return None

    def add_user(self, telegram_id: int, username: str = None,
                 first_name: str = None, last_name: str = None) -> Optional[Dict]:
        """Add new user"""
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

    # Website methods
    def add_website(self, url: str, name: str = None) -> Optional[Dict]:
        """Add new website"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT * FROM websites WHERE url = ?', (url,))
            existing = cursor.fetchone()

            if existing:
                return {
                    'id': existing[0],
                    'url': existing[1],
                    'name': existing[2]
                }

            cursor.execute('''
                INSERT INTO websites (url, name, created_at)
                VALUES (?, ?, ?)
            ''', (url, name or url, datetime.now().isoformat()))
            conn.commit()

            cursor.execute('SELECT * FROM websites WHERE url = ?', (url,))
            row = cursor.fetchone()
            return {
                'id': row[0],
                'url': row[1],
                'name': row[2]
            }
        except Exception as e:
            logger.error(f"Error adding website: {e}")
            return None
        finally:
            conn.close()

    def get_website_by_url(self, url: str) -> Optional[Dict]:
        """Get website by URL"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM websites WHERE url = ?', (url,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'id': row[0],
                'url': row[1],
                'name': row[2],
                'last_hash': row[3],
                'last_content': row[4],
                'last_check': row[5],
                'check_count': row[6],
                'change_count': row[7],
                'created_at': row[8]
            }
        return None

    def get_website_by_id(self, website_id: int) -> Optional[Dict]:
        """Get website by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM websites WHERE id = ?', (website_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'id': row[0],
                'url': row[1],
                'name': row[2],
                'last_hash': row[3],
                'last_content': row[4],
                'last_check': row[5],
                'check_count': row[6],
                'change_count': row[7],
                'created_at': row[8]
            }
        return None

    def update_website_check(self, website_id: int, content_hash: str = None,
                             content: str = None, success: bool = True):
        """Update website check info"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            if content_hash and content:
                cursor.execute('''
                    UPDATE websites 
                    SET last_hash = ?, last_content = ?, last_check = ?, check_count = check_count + 1
                    WHERE id = ?
                ''', (content_hash, content, datetime.now().isoformat(), website_id))
            else:
                cursor.execute('''
                    UPDATE websites 
                    SET last_check = ?, check_count = check_count + 1
                    WHERE id = ?
                ''', (datetime.now().isoformat(), website_id))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating website: {e}")
            return False
        finally:
            conn.close()

    def increment_changes(self, website_id: int):
        """Increment change counter"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE websites SET change_count = change_count + 1 WHERE id = ?
            ''', (website_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error incrementing changes: {e}")
            return False
        finally:
            conn.close()

    def get_all_websites(self) -> List[Dict]:
        """Get all websites"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT * FROM websites')
            rows = cursor.fetchall()
            websites = []
            for row in rows:
                websites.append({
                    'id': row[0],
                    'url': row[1],
                    'name': row[2],
                    'last_hash': row[3],
                    'last_content': row[4],
                    'last_check': row[5],
                    'check_count': row[6],
                    'change_count': row[7],
                    'created_at': row[8]
                })
            return websites
        finally:
            conn.close()

    # Subscription methods
    def subscribe(self, user_id: int, website_id: int) -> bool:
        """Subscribe user to website"""
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
            logger.error(f"Error subscribing: {e}")
            return False
        finally:
            conn.close()

    def unsubscribe(self, user_id: int, website_id: int) -> bool:
        """Unsubscribe user from website"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                DELETE FROM subscriptions WHERE user_id = ? AND website_id = ?
            ''', (user_id, website_id))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error unsubscribing: {e}")
            return False
        finally:
            conn.close()

    def get_user_subscriptions(self, user_id: int) -> List[Dict]:
        """Get all subscriptions for user"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT s.*, w.url, w.name, w.change_count, w.last_check
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
                        'name': row[6],
                        'change_count': row[7],
                        'last_check': row[8]
                    }
                })
            return subscriptions
        finally:
            conn.close()

    def get_subscribers_for_website(self, website_id: int) -> List[Dict]:
        """Get all subscribers for website"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT u.* FROM users u
                JOIN subscriptions s ON u.id = s.user_id
                WHERE s.website_id = ?
            ''', (website_id,))

            rows = cursor.fetchall()
            users = []
            for row in rows:
                users.append({
                    'id': row[0],
                    'telegram_id': row[1],
                    'username': row[2],
                    'first_name': row[3]
                })
            return users
        finally:
            conn.close()

    # Change methods
    def save_change(self, website_id: int, change_type: str, summary: str,
                    details: str, importance_score: float) -> Optional[int]:
        """Save change to history"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO changes (website_id, change_type, change_summary, 
                                    change_details, importance_score, detected_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (website_id, change_type, summary, details,
                  importance_score, datetime.now().isoformat()))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error saving change: {e}")
            return None
        finally:
            conn.close()

    # Statistics
    def get_stats(self, user_id: int = None) -> Dict:
        """Get monitoring statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            stats = {}

            cursor.execute('SELECT COUNT(*) FROM websites')
            stats['total_websites'] = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM users')
            stats['total_users'] = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM subscriptions')
            stats['total_subscriptions'] = cursor.fetchone()[0]

            today = datetime.now().date().isoformat()
            cursor.execute('''
                SELECT COUNT(*) FROM changes WHERE date(detected_at) = ?
            ''', (today,))
            stats['changes_today'] = cursor.fetchone()[0]

            if user_id:
                user = self.get_user(user_id)
                if user:
                    subs = self.get_user_subscriptions(user['id'])
                    stats['user_subscriptions'] = len(subs)

            return stats
        finally:
            conn.close()


# ==================== MONITOR ====================

class WebsiteMonitor:
    """Website monitoring system"""

    def __init__(self, db: Database):
        self.db = db
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'SmartMonitorBot/1.0 (+https://github.com/smart-monitor)'
        })

    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch webpage content"""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            return response.text
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def compute_hash(self, content: str) -> str:
        """Compute SHA256 hash of content"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def extract_significant_content(self, html: str) -> str:
        """Extract meaningful content from HTML"""
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Remove scripts and styles
            for tag in soup.find_all(['script', 'style', 'meta', 'link']):
                tag.decompose()

            # Get text from important tags
            text_parts = []
            for tag in soup.find_all(['h1', 'h2', 'h3', 'title', 'p', 'div.status']):
                text = tag.get_text(strip=True)
                if text and len(text) > 10:
                    text_parts.append(text[:200])

            return ' '.join(text_parts)[:1000]
        except Exception as e:
            logger.error(f"Error extracting content: {e}")
            return html[:500]

    def analyze_change(self, old_content: str, new_content: str) -> Dict:
        """Analyze changes and determine importance"""
        old_text = self.extract_significant_content(old_content)
        new_text = self.extract_significant_content(new_content)

        if not old_text:
            return {
                'has_changes': True,
                'change_type': 'info',
                'importance_score': 0.5,
                'summary': 'Initial content detected',
                'details': new_text[:200]
            }

        if old_text == new_text:
            return {'has_changes': False}

        # Detect change type based on keywords
        new_lower = new_text.lower()
        critical_keywords = ['outage', 'down', 'offline', 'critical', 'emergency', 'failure', 'crash']
        warning_keywords = ['degraded', 'slow', 'delay', 'warning', 'partial', 'issue', 'problem']

        change_type = 'info'
        importance_score = 0.3

        for kw in critical_keywords:
            if kw in new_lower:
                change_type = 'critical'
                importance_score = 0.9
                break

        if change_type == 'info':
            for kw in warning_keywords:
                if kw in new_lower:
                    change_type = 'warning'
                    importance_score = 0.7
                    break

        return {
            'has_changes': True,
            'change_type': change_type,
            'importance_score': importance_score,
            'summary': f"Detected {change_type} change",
            'details': new_text[:200]
        }

    def check_website(self, website: Dict) -> Dict:
        """Check single website for changes"""
        logger.info(f"Checking: {website['url']}")

        # Fetch current content
        content = self.fetch_page(website['url'])
        if not content:
            return {'error': True}

        current_hash = self.compute_hash(content)

        # First check
        if not website.get('last_hash'):
            self.db.update_website_check(website['id'], current_hash, content)
            return {'first_check': True}

        # No changes
        if website['last_hash'] == current_hash:
            self.db.update_website_check(website['id'])
            return {'has_changes': False}

        # Changes detected
        logger.info(f"Changes detected on {website['url']}")

        # Analyze changes
        old_content = website.get('last_content', '')
        analysis = self.analyze_change(old_content, content)

        if analysis.get('has_changes'):
            # Save change
            change_id = self.db.save_change(
                website['id'],
                analysis['change_type'],
                analysis['summary'],
                analysis['details'],
                analysis['importance_score']
            )

            # Update website
            self.db.update_website_check(website['id'], current_hash, content)
            self.db.increment_changes(website['id'])

            return {
                'has_changes': True,
                'change_id': change_id,
                'change_type': analysis['change_type'],
                'importance_score': analysis['importance_score'],
                'summary': analysis['summary'],
                'details': analysis['details'],
                'website': website
            }

        return {'has_changes': False}


# ==================== BOT ====================

class SmartMonitorBot:
    """Main Telegram Bot"""

    def __init__(self):
        self.db = Database()
        self.monitor = WebsiteMonitor(self.db)
        self.updater = Updater(TOKEN, use_context=True)
        self._setup_handlers()

        # Start background monitoring
        self._start_background_monitoring()

        logger.info("✅ Bot initialized")

    def _setup_handlers(self):
        """Setup command handlers"""
        dp = self.updater.dispatcher

        # Commands
        dp.add_handler(CommandHandler("start", self.cmd_start))
        dp.add_handler(CommandHandler("help", self.cmd_help))
        dp.add_handler(CommandHandler("status", self.cmd_status))
        dp.add_handler(CommandHandler("monitor", self.cmd_monitor))
        dp.add_handler(CommandHandler("subscribe", self.cmd_subscribe))
        dp.add_handler(CommandHandler("unsubscribe", self.cmd_unsubscribe))
        dp.add_handler(CommandHandler("list", self.cmd_list))
        dp.add_handler(CommandHandler("check", self.cmd_check))

        # Message handler
        dp.add_handler(MessageHandler(Filters.text & ~Filters.command, self.handle_message))
        dp.add_handler(CallbackQueryHandler(self.handle_callback))

    def _start_background_monitoring(self):
        """Start background monitoring thread"""

        def monitor_loop():
            while True:
                try:
                    logger.info("🔄 Running background monitoring...")
                    websites = self.db.get_all_websites()

                    for website in websites:
                        result = self.monitor.check_website(website)

                        if result.get('has_changes') and result.get('change_id'):
                            # Get subscribers
                            subscribers = self.db.get_subscribers_for_website(website['id'])

                            for user in subscribers:
                                self.send_notification(user['telegram_id'], result, website)

                    logger.info(f"✅ Monitoring complete. Next in 5 minutes...")
                    time.sleep(300)  # 5 minutes

                except Exception as e:
                    logger.error(f"Background monitoring error: {e}")
                    time.sleep(60)

        thread = threading.Thread(target=monitor_loop, daemon=True)
        thread.start()
        logger.info("✅ Background monitoring started")

    def get_keyboard(self):
        """Main keyboard"""
        keyboard = [
            ["📊 Статус", "📋 Мои подписки"],
            ["🔍 Проверить", "ℹ️ Помощь"]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def cmd_start(self, update: Update, context: CallbackContext):
        """Handle /start command"""
        user = update.effective_user
        self.db.add_user(user.id, user.username, user.first_name, user.last_name)

        welcome = f"""
👋 *Добро пожаловать, {user.first_name}!*

🤖 *Smart Monitor Bot* - система мониторинга веб-сайтов.

✨ *Возможности:*
• 📡 Отслеживание изменений на сайтах
• 🔔 Умные уведомления в Telegram
• 📋 Система подписок
• 🎯 Автоматический анализ важности изменений

📝 *Команды:*
• /monitor [url] - добавить сайт
• /subscribe [url] - подписаться
• /unsubscribe [url] - отписаться
• /list - мои подписки
• /status - статус мониторинга
• /check - проверить сейчас
• /help - помощь

💡 *Пример:*
/monitor https://github.com/status
/subscribe https://github.com/status
        """

        update.message.reply_text(welcome, parse_mode='Markdown', reply_markup=self.get_keyboard())

    def cmd_help(self, update: Update, context: CallbackContext):
        """Handle /help command"""
        help_text = """
📖 *Помощь по командам*

🔹 *Основные:*
• /start - запуск бота
• /help - эта справка
• /status - статус мониторинга

🔹 *Мониторинг:*
• /monitor [url] - добавить сайт
• /subscribe [url] - подписаться
• /unsubscribe [url] - отписаться
• /list - мои подписки
• /check - проверить сайты сейчас

💡 *Примеры:*
/monitor https://github.com/status
/subscribe https://github.com/status

📌 *Популярные сайты:*
• https://www.githubstatus.com
• https://status.cloud.google.com
• https://status.aws.amazon.com
• https://status.slack.com
        """
        update.message.reply_text(help_text, parse_mode='Markdown')

    def cmd_status(self, update: Update, context: CallbackContext):
        """Handle /status command"""
        user = self.db.get_user(update.effective_user.id)
        if not user:
            update.message.reply_text("❌ Используйте /start для регистрации")
            return

        stats = self.db.get_stats(user['id'])
        subscriptions = self.db.get_user_subscriptions(user['id'])

        status_text = f"""
📊 *Статус мониторинга*

👥 *Ваш ID:* {user['id']}
📋 *Ваших подписок:* {len(subscriptions)}
🌐 *Всего сайтов:* {stats['total_websites']}
👥 *Всего пользователей:* {stats['total_users']}
🔄 *Изменений сегодня:* {stats['changes_today']}

📡 *Ваши сайты:*
{chr(10).join([f"• {s['website']['name']} (изменений: {s['website']['change_count']})" for s in subscriptions]) if subscriptions else "📭 Нет подписок"}

💡 *Совет:* /monitor [url] - добавить сайт
        """
        update.message.reply_text(status_text, parse_mode='Markdown')

    def cmd_monitor(self, update: Update, context: CallbackContext):
        """Handle /monitor command"""
        if not context.args:
            update.message.reply_text(
                "❌ *Укажите URL сайта*\n\n"
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

        # Check if website exists
        existing = self.db.get_website_by_url(url)
        if existing:
            update.message.reply_text(
                f"ℹ️ Сайт {url} уже есть в системе!\n\n"
                f"Используйте /subscribe {url} для подписки"
            )
            return

        # Add website
        website = self.db.add_website(url)

        if website:
            # Test check
            test_check = self.monitor.check_website(website)

            update.message.reply_text(
                f"✅ *Сайт добавлен!*\n\n"
                f"📍 *URL:* {url}\n"
                f"📊 *ID:* {website['id']}\n\n"
                f"Используйте /subscribe {url} для подписки на уведомления",
                parse_mode='Markdown'
            )
        else:
            update.message.reply_text(f"❌ Не удалось добавить {url}")

    def cmd_subscribe(self, update: Update, context: CallbackContext):
        """Handle /subscribe command"""
        if not context.args:
            update.message.reply_text("❌ Укажите URL: /subscribe https://site.com")
            return

        url = context.args[0]
        user = self.db.get_user(update.effective_user.id)

        if not user:
            user = self.db.add_user(update.effective_user.id)

        website = self.db.get_website_by_url(url)
        if not website:
            update.message.reply_text(
                f"❌ Сайт {url} не найден.\n\n"
                f"Сначала добавьте его: /monitor {url}"
            )
            return

        # Check if already subscribed
        subscriptions = self.db.get_user_subscriptions(user['id'])
        for sub in subscriptions:
            if sub['website']['url'] == url:
                update.message.reply_text(f"ℹ️ Вы уже подписаны на {url}")
                return

        success = self.db.subscribe(user['id'], website['id'])

        if success:
            subscriptions_count = len(subscriptions) + 1
            update.message.reply_text(
                f"✅ *Подписка оформлена!*\n\n"
                f"📍 *Сайт:* {website['name']}\n"
                f"📊 *Всего подписок:* {subscriptions_count}\n\n"
                f"💡 *Совет:* Используйте /list для просмотра всех подписок",
                parse_mode='Markdown'
            )
        else:
            update.message.reply_text("❌ Ошибка подписки")

    def cmd_unsubscribe(self, update: Update, context: CallbackContext):
        """Handle /unsubscribe command"""
        if not context.args:
            # Show subscriptions list
            user = self.db.get_user(update.effective_user.id)
            if user:
                subs = self.db.get_user_subscriptions(user['id'])
                if subs:
                    text = "📋 *Ваши подписки:*\n\n"
                    for s in subs:
                        text += f"• {s['website']['name']}\n  `{s['website']['url']}`\n\n"
                    text += "Для отписки: /unsubscribe [url]"
                    update.message.reply_text(text, parse_mode='Markdown')
                else:
                    update.message.reply_text("📭 У вас нет активных подписок")
            return

        url = context.args[0]
        user = self.db.get_user(update.effective_user.id)
        website = self.db.get_website_by_url(url)

        if not user or not website:
            update.message.reply_text("❌ Пользователь или сайт не найден")
            return

        success = self.db.unsubscribe(user['id'], website['id'])

        if success:
            update.message.reply_text(f"✅ Отписка от {url} выполнена")
        else:
            update.message.reply_text("❌ Вы не подписаны на этот сайт")

    def cmd_list(self, update: Update, context: CallbackContext):
        """Handle /list command - show subscriptions"""
        user = self.db.get_user(update.effective_user.id)

        if not user:
            update.message.reply_text("❌ Используйте /start для регистрации")
            return

        subscriptions = self.db.get_user_subscriptions(user['id'])

        if not subscriptions:
            update.message.reply_text(
                "📭 *У вас нет активных подписок*\n\n"
                "Добавьте сайт: /monitor [url]\n"
                "Подпишитесь: /subscribe [url]\n\n"
                "💡 *Пример:*\n"
                "/monitor https://github.com/status\n"
                "/subscribe https://github.com/status",
                parse_mode='Markdown'
            )
            return

        text = "📋 *Ваши подписки:*\n\n"
        for i, s in enumerate(subscriptions, 1):
            text += f"{i}. *{s['website']['name']}*\n"
            text += f"   📍 `{s['website']['url']}`\n"
            text += f"   🔔 Изменений: {s['website']['change_count']}\n"
            text += f"   🕐 Добавлено: {s['created_at'][:10]}\n\n"

        text += f"📊 *Всего:* {len(subscriptions)} подписок"

        update.message.reply_text(text, parse_mode='Markdown')

    def cmd_check(self, update: Update, context: CallbackContext):
        """Handle /check command - manual check"""
        user = self.db.get_user(update.effective_user.id)

        if not user:
            update.message.reply_text("❌ Используйте /start для регистрации")
            return

        subscriptions = self.db.get_user_subscriptions(user['id'])

        if not subscriptions:
            update.message.reply_text("📭 У вас нет подписок для проверки")
            return

        update.message.reply_text("🔍 *Начинаю проверку сайтов...*", parse_mode='Markdown')

        changes_found = 0
        for sub in subscriptions:
            website = self.db.get_website_by_url(sub['website']['url'])
            if website:
                result = self.monitor.check_website(website)

                if result.get('has_changes') and result.get('change_id'):
                    changes_found += 1
                    # Send notification
                    self.send_notification(update.effective_user.id, result, website)

        if changes_found == 0:
            update.message.reply_text("✅ *Изменений не обнаружено*", parse_mode='Markdown')
        else:
            update.message.reply_text(
                f"📢 *Обнаружено {changes_found} изменений!*\n"
                f"Уведомления отправлены.",
                parse_mode='Markdown'
            )

    def send_notification(self, chat_id: int, change: Dict, website: Dict):
        """Send notification to user"""
        emojis = {
            'critical': '🔴',
            'warning': '⚠️',
            'info': 'ℹ️'
        }
        emoji = emojis.get(change['change_type'], '📢')

        notification = f"""
{emoji} *{change['change_type'].upper()}* - *{website['name']}*

📋 *Что изменилось:*
{change['summary']}

🕐 *Время:* {datetime.now().strftime('%H:%M:%S')}

---
👍 *Полезно?* Оцените уведомление
        """

        keyboard = [
            [
                InlineKeyboardButton("👍 Полезно", callback_data=f"like_{change['change_id']}"),
                InlineKeyboardButton("👎 Не полезно", callback_data=f"dislike_{change['change_id']}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            self.updater.bot.send_message(
                chat_id=chat_id,
                text=notification,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            logger.info(f"Notification sent to {chat_id}")
        except Exception as e:
            logger.error(f"Error sending notification: {e}")

    def handle_message(self, update: Update, context: CallbackContext):
        """Handle text messages from keyboard"""
        text = update.message.text

        if text == "📊 Статус":
            self.cmd_status(update, context)
        elif text == "📋 Мои подписки":
            self.cmd_list(update, context)
        elif text == "🔍 Проверить":
            self.cmd_check(update, context)
        elif text == "ℹ️ Помощь":
            self.cmd_help(update, context)
        else:
            update.message.reply_text(
                "🤖 *Используйте /help для списка команд*\n\n"
                "💡 *Быстрые команды:*\n"
                "• /status - статус\n"
                "• /list - мои подписки\n"
                "• /monitor [url] - добавить сайт",
                parse_mode='Markdown'
            )

    def handle_callback(self, update: Update, context: CallbackContext):
        """Handle callback queries from inline keyboards"""
        query = update.callback_query
        query.answer()

        data = query.data

        if data.startswith("like_"):
            query.edit_message_reply_markup(reply_markup=None)
            query.edit_message_text(
                query.message.text + "\n\n✅ *Спасибо за оценку!*",
                parse_mode='Markdown'
            )
        elif data.startswith("dislike_"):
            query.edit_message_reply_markup(reply_markup=None)
            query.edit_message_text(
                query.message.text + "\n\n👍 *Спасибо за отзыв!*",
                parse_mode='Markdown'
            )

    def run(self):
        """Start the bot"""
        logger.info("🚀 Starting bot...")
        logger.info(f"Bot token: {TOKEN[:10]}...")

        self.updater.start_polling()
        self.updater.idle()


# ==================== MAIN ====================

def main():
    """Main entry point"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   🚀 SMART MONITOR BOT - Production Ready for Railway                        ║
║                                                                              ║
║   🤖 Умная система мониторинга веб-сайтов                                   ║
║   📡 Автоматическое отслеживание изменений                                  ║
║   🔔 Умные уведомления в Telegram                                            ║
║   🎯 ИИ-анализ важности изменений                                            ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)

    try:
        bot = SmartMonitorBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()