# File: models.py
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Float, Boolean, DateTime, ForeignKey
import datetime as dt

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)


class User(db.Model):
    __tablename__ = 'user'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(80), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=True)
    oauth_provider: Mapped[str] = mapped_column(String(20), nullable=True)
    oauth_id: Mapped[str] = mapped_column(String(200), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
    
    
    # User settings
    milk_price_per_litre: Mapped[float] = mapped_column(Float, default=50.0)
    currency: Mapped[str] = mapped_column(String(10), default='INR')
    currency_symbol: Mapped[str] = mapped_column(String(5), default='₹')
    refresh_token: Mapped[str] = mapped_column(String(500), nullable=True)
    
    # Relationship to Milk records
    milk_records = relationship('Milk', back_populates='user', cascade='all, delete-orphan')


class Milk(db.Model):
    __tablename__ = 'milk'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[str] = mapped_column(String(250), nullable=True, index=True)
    milk_qty: Mapped[float] = mapped_column(Float, nullable=True)
    cost: Mapped[float] = mapped_column(Float, nullable=True)
    month_year: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('user.id'), nullable=False, index=True)
    
    user = relationship('User', back_populates='milk_records')