# Smart Monitor Bot

🤖 Telegram бот для мониторинга веб-сайтов с автоматическим анализом изменений.

## Возможности

- 📡 Автоматический мониторинг изменений на сайтах
- 🔔 Умные уведомления в Telegram
- 📋 Система подписок на сайты
- 🎯 Анализ важности изменений
- 💾 Хранение истории изменений

## Команды

- `/start` - запуск бота
- `/monitor [url]` - добавить сайт для мониторинга
- `/subscribe [url]` - подписаться на уведомления
- `/unsubscribe [url]` - отписаться
- `/list` - список ваших подписок
- `/status` - статус мониторинга
- `/check` - ручная проверка сайтов
- `/help` - помощь

## Деплой на Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/your-template)

### Переменные окружения

- `TELEGRAM_TOKEN` - токен вашего Telegram бота

## Локальный запуск

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск
python bot.py