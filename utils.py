import time
import functools
from datetime import datetime
from prometheus_client import Counter, Histogram, Gauge

# Метрики
CHECK_COUNTER = Counter('monitor_checks_total', 'Total number of checks')
CHECK_DURATION = Histogram('monitor_check_duration_seconds', 'Check duration')
CHANGE_COUNTER = Counter('monitor_changes_total', 'Total number of changes')
ERROR_COUNTER = Counter('monitor_errors_total', 'Total number of errors')
ACTIVE_WEBSITES = Gauge('monitor_active_websites', 'Number of active websites')


def measure_time(func):
    """Декоратор для измерения времени выполнения"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start

        if hasattr(func, '__name__'):
            CHECK_DURATION.labels(function=func.__name__).observe(duration)

        return result

    return wrapper


def log_metric(metric_name, value, tags=None):
    """Логирует метрику"""
    logger.info(f"Metric: {metric_name}={value}, tags={tags}")


def format_duration(seconds):
    """Форматирует длительность"""
    if seconds < 60:
        return f"{seconds:.0f} сек"
    elif seconds < 3600:
        return f"{seconds / 60:.0f} мин"
    else:
        return f"{seconds / 3600:.1f} ч"


def safe_json_parse(data, default=None):
    """Безопасный парсинг JSON"""
    import json
    try:
        return json.loads(data)
    except:
        return default or {}