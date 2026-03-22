import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')

# База данных
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///monitoring.db')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Настройки мониторинга
DEFAULT_CHECK_INTERVAL = 300  # 5 минут
MAX_CHECK_INTERVAL = 3600      # 1 час
MIN_CHECK_INTERVAL = 60        # 1 минута

# Адаптивные интервалы
ADAPTIVE_INTERVALS = {
    'critical': 60,      # 1 минута для критических сайтов
    'warning': 300,      # 5 минут для важных
    'normal': 600,       # 10 минут для обычных
    'stable': 1800,      # 30 минут для стабильных
    'inactive': 3600     # 1 час для неактивных
}

# Пороги для ИИ
IMPORTANCE_THRESHOLDS = {
    'critical': 0.8,
    'warning': 0.5,
    'info': 0.3,
    'trivial': 0.1
}

# Типы изменений
CHANGE_TYPES = {
    'content': {'emoji': '📝', 'priority': 3, 'name': 'Изменение контента'},
    'design': {'emoji': '🎨', 'priority': 4, 'name': 'Изменение дизайна'},
    'functional': {'emoji': '⚙️', 'priority': 1, 'name': 'Изменение функционала'},
    'status': {'emoji': '🔴', 'priority': 2, 'name': 'Изменение статуса'}
}

# Ключевые слова для классификации
CLASSIFICATION_KEYWORDS = {
    'functional': ['error', 'outage', 'down', 'offline', 'failed', 'crash', 'bug'],
    'status': ['degraded', 'partial', 'investigating', 'monitoring'],
    'content': ['update', 'new', 'added', 'changed', 'modified'],
    'design': ['layout', 'color', 'button', 'menu', 'header', 'footer']
}

# Метрики и мониторинг
METRICS_ENABLED = True
PROMETHEUS_PORT = 9090
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Системные настройки
MAX_WORKERS = 4
REQUEST_TIMEOUT = 15
USER_AGENT = 'SmartMonitorBot/1.0 (+https://github.com/smart-monitor)'
MAX_RETRIES = 3
RETRY_DELAY = 5
