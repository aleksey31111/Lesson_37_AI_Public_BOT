#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

# Простая настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Загружаем конфигурацию
load_dotenv()


def check_environment():
    """Проверяет переменные окружения"""
    token = os.getenv('TELEGRAM_TOKEN')
    if not token:
        print("❌ Отсутствует TELEGRAM_TOKEN в .env файле!")
        print("\n📝 Создайте файл .env в папке smart_monitoring_system/ с содержимым:")
        print("TELEGRAM_TOKEN=ваш_токен_бота")
        print("\nПолучите токен у @BotFather в Telegram")
        return False

    logger.info("✅ Токен загружен: %s...", token[:10])
    return True


def main():
    """Основная функция запуска"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   🚀 SMART MONITOR BOT v1.0 - Production Ready                              ║
║                                                                              ║
║   🤖 Умная система мониторинга веб-сайтов с ИИ-анализом                     ║
║   🎯 Персонализация | 📦 Группировка | 🎓 Обучение на реакциях              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)

    # Проверка окружения
    if not check_environment():
        sys.exit(1)

    try:
        from telegram_bot import SmartMonitorBot

        # Запуск бота
        bot = SmartMonitorBot()
        bot.run()

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except ImportError as e:
        logger.error(f"Ошибка импорта: {e}")
        print("\n❌ Не установлены зависимости. Выполните:")
        print("pip install python-telegram-bot==13.7 requests beautifulsoup4 python-dotenv")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()