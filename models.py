from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import json

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    is_active = Column(Boolean, default=True)

    # Настройки
    preferences = Column(JSON, default={})
    learning_data = Column(JSON, default={})

    # Статистика
    total_notifications = Column(Integer, default=0)
    likes_count = Column(Integer, default=0)
    dislikes_count = Column(Integer, default=0)
    ignores_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.now)
    last_active = Column(DateTime, default=datetime.now)

    # Отношения
    subscriptions = relationship('Subscription', back_populates='user')
    feedbacks = relationship('Feedback', back_populates='user')


class Website(Base):
    __tablename__ = 'websites'

    id = Column(Integer, primary_key=True)
    url = Column(String(500), unique=True, nullable=False)
    name = Column(String(200))

    # Статус
    is_active = Column(Boolean, default=True)
    stability_score = Column(Float, default=0.5)  # 0-1, чем выше, тем стабильнее
    check_interval = Column(Integer, default=300)  # секунды
    last_check = Column(DateTime)
    last_change = Column(DateTime)

    # Статистика
    check_count = Column(Integer, default=0)
    change_count = Column(Integer, default=0)
    false_positive_count = Column(Integer, default=0)

    # Хэши
    last_hash = Column(String(64))
    last_content = Column(Text)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Отношения
    subscriptions = relationship('Subscription', back_populates='website')
    changes = relationship('Change', back_populates='website')


class Subscription(Base):
    __tablename__ = 'subscriptions'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    website_id = Column(Integer, ForeignKey('websites.id'))

    # Персональные настройки
    custom_threshold = Column(Float, default=0.3)
    notification_types = Column(JSON, default={'critical': True, 'warning': True, 'info': True})
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.now)

    # Отношения
    user = relationship('User', back_populates='subscriptions')
    website = relationship('Website', back_populates='subscriptions')


class Change(Base):
    __tablename__ = 'changes'

    id = Column(Integer, primary_key=True)
    website_id = Column(Integer, ForeignKey('websites.id'))

    # Тип и важность
    change_type = Column(String(50))  # content, design, functional, status
    importance = Column(String(20))  # critical, warning, info, trivial
    importance_score = Column(Float)

    # Содержание
    title = Column(String(500))
    content = Column(Text)
    diff = Column(Text)  # HTML diff

    # Метаданные
    category = Column(String(50))
    is_false_positive = Column(Boolean, default=False)

    detected_at = Column(DateTime, default=datetime.now)
    notified_count = Column(Integer, default=0)

    # Отношения
    website = relationship('Website', back_populates='changes')
    feedbacks = relationship('Feedback', back_populates='change')


class Feedback(Base):
    __tablename__ = 'feedbacks'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    change_id = Column(Integer, ForeignKey('changes.id'))

    feedback_type = Column(String(20))  # like, dislike, ignore
    feedback_score = Column(Float)

    created_at = Column(DateTime, default=datetime.now)

    # Отношения
    user = relationship('User', back_populates='feedbacks')
    change = relationship('Change', back_populates='feedbacks')


class MonitoringLog(Base):
    __tablename__ = 'monitoring_logs'

    id = Column(Integer, primary_key=True)
    website_id = Column(Integer, ForeignKey('websites.id'))

    status = Column(String(20))  # success, error, timeout
    response_time = Column(Float)
    error_message = Column(Text)

    created_at = Column(DateTime, default=datetime.now)
