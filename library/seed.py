"""CLI commands and sample data seeding."""
from __future__ import annotations

import click
from flask import Flask

from . import db
from .models import Book, NewsPost, User


SAMPLE_BOOKS = [
    ("To Kill a Mockingbird", "Harper Lee", "Fiction", 1960, 3,
     "A novel about racial injustice in the American South."),
    ("1984", "George Orwell", "Fiction", 1949, 4,
     "A dystopian story about totalitarian surveillance."),
    ("Pride and Prejudice", "Jane Austen", "Classic", 1813, 2,
     "A witty exploration of love, class and reputation."),
    ("The Hobbit", "J.R.R. Tolkien", "Fantasy", 1937, 5,
     "Bilbo Baggins joins a quest to reclaim a dwarven kingdom."),
    ("A Brief History of Time", "Stephen Hawking", "Science", 1988, 2,
     "From the Big Bang to black holes — modern cosmology explained."),
    ("Sapiens", "Yuval Noah Harari", "History", 2011, 3,
     "A sweeping account of the history of humankind."),
    ("Harry Potter and the Philosopher's Stone", "J.K. Rowling",
     "Fantasy", 1997, 6, "A young wizard discovers his magical heritage."),
    ("The Great Gatsby", "F. Scott Fitzgerald", "Classic", 1925, 2,
     "Wealth, love, and the American dream in the Jazz Age."),
    ("Cosmos", "Carl Sagan", "Science", 1980, 2,
     "A journey through the universe and the history of science."),
    ("The Diary of a Young Girl", "Anne Frank", "Biography", 1947, 3,
     "The wartime diary of a teenage girl hiding in Amsterdam."),
]


def register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db():
        """Create all tables."""
        db.create_all()
        click.echo("Database initialised.")

    @app.cli.command("seed")
    def seed():
        """Insert sample data (admin user + books + news)."""
        if not User.query.filter_by(username="M.Hanzlova").first():
            admin = User(username="M.Hanzlova", email="hanzlova@school.local", role="admin")
            admin.set_password("Hanzlova1984")
            admin.is_email_verified = True
            db.session.add(admin)

        if not User.query.filter_by(username="student").first():
            student = User(
                username="student", email="student@school.local", role="student"
            )
            student.set_password("student123")
            student.is_email_verified = True
            db.session.add(student)

        for title, author, category, year, copies, desc in SAMPLE_BOOKS:
            if not Book.query.filter_by(title=title, author=author).first():
                db.session.add(
                    Book(
                        title=title,
                        author=author,
                        category=category,
                        year=year,
                        total_copies=copies,
                        description=desc,
                    )
                )

        if NewsPost.query.count() == 0:
            db.session.add(
                NewsPost(
                    title="Welcome to the new library website!",
                    body=(
                        "We're delighted to launch our new online catalog. "
                        "Browse books, reserve titles, and keep up with library news."
                    ),
                )
            )
            db.session.add(
                NewsPost(
                    title="Summer reading challenge",
                    body=(
                        "Read 5 books over the summer break and earn a certificate. "
                        "Sign up at the front desk!"
                    ),
                )
            )

        db.session.commit()
        click.echo("Sample data seeded. Admin login: M.Hanzlova / Hanzlova1984")
