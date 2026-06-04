from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import or_

from ..models import Book

bp = Blueprint("catalog", __name__)


@bp.route("/")
def index():
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    page = request.args.get("page", 1, type=int)

    books_query = Book.query
    if query:
        like = f"%{query}%"
        books_query = books_query.filter(
            or_(Book.title.ilike(like), Book.author.ilike(like), Book.isbn.ilike(like))
        )
    if category:
        books_query = books_query.filter(Book.category == category)

    pagination = books_query.order_by(Book.title.asc()).paginate(
        page=page, per_page=12, error_out=False
    )

    categories = [
        c[0]
        for c in Book.query.with_entities(Book.category)
        .distinct()
        .order_by(Book.category.asc())
        if c[0]
    ]

    return render_template(
        "catalog/index.html",
        pagination=pagination,
        books=pagination.items,
        q=query,
        category=category,
        categories=categories,
    )


@bp.route("/book/<int:book_id>")
def detail(book_id: int):
    book = Book.query.get_or_404(book_id)
    return render_template("catalog/detail.html", book=book)


@bp.route("/suggest")
def suggest():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])

    like = f"%{query}%"
    books = (
        Book.query.filter(or_(Book.title.ilike(like), Book.author.ilike(like), Book.isbn.ilike(like)))
        .order_by(Book.title.asc())
        .limit(10)
        .all()
    )
    return jsonify(
        [
            {
                "title": b.title,
                "author": b.author,
                "isbn": b.isbn or "",
            }
            for b in books
        ]
    )
