import requests
import hashlib
import asyncio
import aiohttp
from datetime import datetime
from typing import Optional, Dict, List
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

from config import USER_AGENT, REQUEST_TIMEOUT, MAX_RETRIES, RETRY_DELAY
from ai_engine import AIEngine
from database import Database
from utils import measure_time, log_metric


class SmartMonitor:
    """Умная система мониторинга с оптимизацией"""

    def __init__(self, db=None, ai_engine=None):
        self.db = db or Database()
        self.ai = ai_engine or AIEngine(self.db)
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
        self.executor = ThreadPoolExecutor(max_workers=4)

    @measure_time
    async def check_website(self, website_id: int) -> Dict:
        """
        Асинхронная проверка сайта с оптимизацией
        """
        website = self.db.get_website(website_id)
        if not website:
            return {'error': 'Website not found'}

        start_time = datetime.now()

        try:
            # Загружаем страницу с retry
            content = await self._fetch_with_retry(website['url'])

            if not content:
                self._log_error(website_id, 'Fetch failed')
                return {'error': 'Failed to fetch', 'website': website}

            # Вычисляем хэш
            current_hash = hashlib.sha256(content.encode()).hexdigest()

            # Проверяем изменения
            if website['last_hash'] == current_hash:
                self._update_check(website_id, success=True)
                return {'has_changes': False, 'website': website}

            # Обнаружены изменения
            print(f"📊 Изменения на {website['url']}")

            # Анализируем изменение
            change_analysis = self.ai.classify_change(
                website.get('last_content', ''),
                content
            )

            # Рассчитываем важность
            importance = self.ai.calculate_importance(change_analysis)

            # Проверяем на ложное срабатывание
            history = self.db.get_website_changes(website_id, limit=20)
            is_false_positive = self.ai.detect_false_positive(change_analysis, history)

            if is_false_positive:
                self.db.increment_false_positive(website_id)
                return {'has_changes': False, 'false_positive': True}

            # Сохраняем изменение
            change_id = self.db.save_change(
                website_id=website_id,
                change_type=change_analysis['type'],
                importance=importance['level'],
                importance_score=importance['score'],
                title=self._generate_title(change_analysis, importance),
                content=change_analysis.get('diff', ''),
                diff=self._generate_diff(website.get('last_content', ''), content)
            )

            # Обновляем сайт
            self._update_check(website_id, success=True,
                               new_hash=current_hash, new_content=content)

            # Оптимизируем интервал проверки
            new_interval = self.ai.optimize_interval(website_id)

            response_time = (datetime.now() - start_time).total_seconds()

            return {
                'has_changes': True,
                'change_id': change_id,
                'website': website,
                'analysis': change_analysis,
                'importance': importance,
                'response_time': response_time,
                'new_interval': new_interval
            }

        except Exception as e:
            print(f"❌ Ошибка проверки {website['url']}: {e}")
            self._log_error(website_id, str(e))
            return {'error': str(e), 'website': website}

    async def _fetch_with_retry(self, url: str) -> Optional[str]:
        """Загружает страницу с повторными попытками"""
        for attempt in range(MAX_RETRIES):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=REQUEST_TIMEOUT,
                                           headers={'User-Agent': USER_AGENT}) as response:
                        if response.status == 200:
                            return await response.text()
                        else:
                            print(f"⚠️ HTTP {response.status} for {url}")
            except Exception as e:
                print(f"⚠️ Attempt {attempt + 1} failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))

        return None

    def _update_check(self, website_id: int, success: bool,
                      new_hash: str = None, new_content: str = None):
        """Обновляет информацию о проверке"""
        self.db.update_website_check(
            website_id,
            success=success,
            new_hash=new_hash,
            new_content=new_content
        )

    def _log_error(self, website_id: int, error: str):
        """Логирует ошибку"""
        self.db.add_monitoring_log(website_id, 'error', error)

    def _generate_title(self, analysis: Dict, importance: Dict) -> str:
        """Генерирует заголовок уведомления"""
        emojis = {
            'critical': '🔴',
            'warning': '⚠️',
            'info': 'ℹ️',
            'trivial': '📝'
        }

        emoji = emojis.get(importance['level'], '📢')
        change_name = analysis.get('description', 'Изменение')

        return f"{emoji} {change_name}"

    def _generate_diff(self, old_content: str, new_content: str) -> str:
        """Генерирует diff между версиями"""
        # Простая реализация, можно улучшить
        old_soup = BeautifulSoup(old_content, 'html.parser')
        new_soup = BeautifulSoup(new_content, 'html.parser')

        old_text = old_soup.get_text()
        new_text = new_soup.get_text()

        # Находим измененные участки
        if len(old_text) > 1000:
            old_text = old_text[:1000]
        if len(new_text) > 1000:
            new_text = new_text[:1000]

        return f"--- a\n+++ b\n\nИзменения обнаружены в текстовом содержимом."

    def check_all_websites(self) -> List[Dict]:
        """Проверяет все активные сайты"""
        websites = self.db.get_active_websites()
        results = []

        # Используем asyncio для параллельной проверки
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        tasks = [self.check_website(w['id']) for w in websites]
        results = loop.run_until_complete(asyncio.gather(*tasks))
        loop.close()

        return results