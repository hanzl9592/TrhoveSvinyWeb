"""Database models."""
from __future__ import annotations

from datetime import datetime, timedelta

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from . import db


LOAN_PERIOD_DAYS = 14


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(80), nullable=True)
    last_name = db.Column(db.String(80), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    is_email_verified = db.Column(db.Boolean, nullable=False, default=False)
    email_verification_token = db.Column(db.String(128), unique=True, nullable=True)
    email_verification_expires_at = db.Column(db.DateTime, nullable=True)
    password_reset_token = db.Column(db.String(128), unique=True, nullable=True)
    password_reset_expires_at = db.Column(db.DateTime, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(16), nullable=False, default="student")  # student|staff|admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    loans = db.relationship("Loan", back_populates="user", lazy="dynamic")
    reservations = db.relationship("Reservation", back_populates="user", lazy="dynamic")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role})>"


class Book(db.Model):
    __tablename__ = "books"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    author = db.Column(db.String(200), nullable=False, index=True)
    isbn = db.Column(db.String(20), unique=True, nullable=True)
    category = db.Column(db.String(80), nullable=True, index=True)
    description = db.Column(db.Text, nullable=True)
    year = db.Column(db.Integer, nullable=True)
    total_copies = db.Column(db.Integer, nullable=False, default=1)
    cover_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    loans = db.relationship("Loan", back_populates="book", lazy="dynamic")
    reservations = db.relationship("Reservation", back_populates="book", lazy="dynamic")

    @property
    def copies_on_loan(self) -> int:
        return self.loans.filter_by(returned_at=None).count()

    @property
    def copies_available(self) -> int:
        return max(self.total_copies - self.copies_on_loan, 0)

    def __repr__(self) -> str:
        return f"<Book {self.title!r} by {self.author!r}>"


class Loan(db.Model):
    __tablename__ = "loans"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False)
    borrowed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    due_at = db.Column(
        db.DateTime,
        default=lambda: datetime.utcnow() + timedelta(days=LOAN_PERIOD_DAYS),
        nullable=False,
    )
    returned_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", back_populates="loans")
    book = db.relationship("Book", back_populates="loans")

    @property
    def is_active(self) -> bool:
        return self.returned_at is None

    @property
    def is_overdue(self) -> bool:
        return self.is_active and datetime.utcnow() > self.due_at


class Reservation(db.Model):
    __tablename__ = "reservations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False)
    reserved_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="pending")  # pending|confirmed
    confirmed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", back_populates="reservations")
    book = db.relationship("Book", back_populates="reservations")

    def __repr__(self) -> str:
        return f"<Reservation {self.user.username} → {self.book.title} ({self.status})>"


class NewsPost(db.Model):
    __tablename__ = "news_posts"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    published_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    author = db.relationship("User")
