import re
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import (
    CLASSIFICATION_KEYWORDS, IMPORTANCE_THRESHOLDS,
    ADAPTIVE_INTERVALS, CHANGE_TYPES
)


class AIEngine:
    """ИИ-движок для анализа изменений и оптимизации"""

    def __init__(self, db):
        self.db = db
        self.vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
        self._init_models()

    def _init_models(self):
        """Инициализация моделей"""
        self.classification_keywords = CLASSIFICATION_KEYWORDS
        self.importance_thresholds = IMPORTANCE_THRESHOLDS

    def classify_change(self, old_content: str, new_content: str) -> Dict:
        """
        Классифицирует тип изменения
        Возвращает: тип изменения, уверенность, описание
        """
        # Анализируем разницу
        diff = self._get_diff(old_content, new_content)

        # Определяем тип
        scores = {}
        for change_type, keywords in self.classification_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in diff.lower():
                    score += 1
            scores[change_type] = score

        # Выбираем тип с максимальным счетом
        if max(scores.values()) > 0:
            change_type = max(scores, key=scores.get)
            confidence = scores[change_type] / sum(scores.values())
        else:
            change_type = 'content'
            confidence = 0.5

        return {
            'type': change_type,
            'confidence': confidence,
            'description': CHANGE_TYPES.get(change_type, {}).get('name', 'Изменение'),
            'diff': diff
        }

    def _get_diff(self, old_content: str, new_content: str) -> str:
        """Извлекает значимую разницу между версиями"""
        old_words = set(old_content.lower().split())
        new_words = set(new_content.lower().split())

        added = new_words - old_words
        removed = old_words - new_words

        return ' '.join(added | removed)

    def calculate_importance(self, change: Dict, user_profile: Dict = None) -> Dict:
        """
        Рассчитывает важность изменения
        Учитывает тип, контент и предпочтения пользователя
        """
        base_score = self._base_importance(change)

        # Корректировка на основе типа
        type_multiplier = {
            'functional': 1.0,
            'status': 0.9,
            'content': 0.6,
            'design': 0.4
        }.get(change.get('type', 'content'), 0.5)

        importance_score = base_score * type_multiplier

        # Персонализация
        if user_profile:
            personalization_factor = self._personalization_factor(change, user_profile)
            importance_score *= personalization_factor

        # Определяем уровень важности
        if importance_score >= self.importance_thresholds['critical']:
            level = 'critical'
        elif importance_score >= self.importance_thresholds['warning']:
            level = 'warning'
        elif importance_score >= self.importance_thresholds['info']:
            level = 'info'
        else:
            level = 'trivial'

        return {
            'score': round(importance_score, 3),
            'level': level,
            'factors': {
                'base_score': base_score,
                'type_multiplier': type_multiplier,
                'personalization': personalization_factor if user_profile else None
            }
        }

    def _base_importance(self, change: Dict) -> float:
        """Базовая важность на основе контента"""
        text = change.get('diff', '')
        text_lower = text.lower()

        # Критические ключевые слова
        critical_keywords = ['outage', 'down', 'offline', 'critical', 'emergency']
        warning_keywords = ['degraded', 'slow', 'delay', 'warning']

        for kw in critical_keywords:
            if kw in text_lower:
                return 0.9

        for kw in warning_keywords:
            if kw in text_lower:
                return 0.7

        # Длина текста как фактор
        text_length = min(len(text), 500) / 500
        return 0.3 + text_length * 0.4

    def _personalization_factor(self, change: Dict, user_profile: Dict) -> float:
        """Персонализация на основе профиля пользователя"""
        factor = 1.0

        # Учитываем предпочтения по типам
        preferred_types = user_profile.get('preferred_types', [])
        if change.get('type') in preferred_types:
            factor *= 1.2

        # Учитываем ключевые слова
        text = change.get('diff', '').lower()
        preferred_keywords = user_profile.get('preferred_keywords', [])
        for kw in preferred_keywords:
            if kw in text:
                factor *= 1.1

        return min(2.0, factor)

    def detect_false_positive(self, change: Dict, history: List[Dict]) -> bool:
        """
        Обнаруживает ложные срабатывания
        Анализирует паттерны изменений и историю
        """
        text = change.get('diff', '').lower()

        # Паттерны ложных срабатываний
        noise_patterns = [
            r'counter_\d+',
            r'advertisement',
            r'analytics',
            r'facebook\.com/tr',
            r'google-analytics',
            r'cookie',
            r'\d+\s*(views?|reads?)',
            r'last updated'
        ]

        for pattern in noise_patterns:
            if re.search(pattern, text):
                return True

        # Проверяем историю
        if history:
            # Если похожее изменение уже было и получило dislikes
            similar_count = sum(1 for h in history[-10:]
                                if self._similarity(text, h.get('diff', '')) > 0.8)
            if similar_count > 3:
                return True

        return False

    def _similarity(self, text1: str, text2: str) -> float:
        """Вычисляет схожесть двух текстов"""
        if not text1 or not text2:
            return 0.0

        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    def optimize_interval(self, website_id: int) -> int:
        """
        Оптимизирует интервал проверки для сайта
        Учитывает стабильность, частоту изменений и важность
        """
        from database import Database
        db = Database()

        website = db.get_website(website_id)
        if not website:
            return ADAPTIVE_INTERVALS['normal']

        # Получаем историю изменений
        changes = db.get_website_changes(website_id, limit=50)

        if not changes:
            return ADAPTIVE_INTERVALS['normal']

        # Вычисляем стабильность
        recent_changes = [c for c in changes
                          if (datetime.now() - c['detected_at']).days < 7]

        change_frequency = len(recent_changes) / 7  # изменений в день

        # Коэффициент стабильности
        if change_frequency == 0:
            stability = 1.0
        else:
            stability = 1 / (1 + change_frequency)

        # Вычисляем среднюю важность
        avg_importance = np.mean([c.get('importance_score', 0.3) for c in changes[-10:]])

        # Определяем интервал
        if avg_importance > 0.8:  # Критический сайт
            interval = ADAPTIVE_INTERVALS['critical']
        elif avg_importance > 0.5:  # Важный сайт
            interval = ADAPTIVE_INTERVALS['warning']
        elif stability > 0.9:  # Очень стабильный
            interval = ADAPTIVE_INTERVALS['stable']
        elif stability > 0.7:  # Стабильный
            interval = ADAPTIVE_INTERVALS['normal']
        else:  # Нестабильный
            interval = ADAPTIVE_INTERVALS['warning']

        # Обновляем в БД
        db.update_website_interval(website_id, interval)

        return interval

    def generate_recommendations(self, user_id: int) -> List[Dict]:
        """
        Генерирует персонализированные рекомендации
        """
        from database import Database
        db = Database()

        user = db.get_user(user_id)
        subscriptions = db.get_user_subscriptions(user_id)
        profile = db.get_user_profile(user_id)

        recommendations = []

        # Рекомендация по настройке порога
        if profile.get('likes_ratio', 0) < 0.5:
            recommendations.append({
                'type': 'settings',
                'title': 'Настройте порог важности',
                'description': 'Вы часто игнорируете уведомления. Попробуйте повысить порог важности в /settings',
                'priority': 'high'
            })

        # Рекомендация по добавлению сайтов
        if len(subscriptions) < 3:
            recommendations.append({
                'type': 'add_sites',
                'title': 'Добавьте больше сайтов',
                'description': 'Популярные сайты для мониторинга: GitHub Status, Cloudflare Status, Google Cloud Status',
                'priority': 'medium'
            })

        # Рекомендация на основе интересов
        interests = profile.get('interests', [])
        if 'technical' in interests:
            recommendations.append({
                'type': 'suggestion',
                'title': 'Технические сайты',
                'description': 'Рекомендуем добавить: Hacker News, Stack Overflow Status, GitHub Blog',
                'priority': 'low'
            })

        return recommendations