from flask import Blueprint, redirect, render_template, request, session, url_for
from ..models import NewsPost, Book
from .. import db
from ..i18n import SUPPORTED_LANGS, tr

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    latest_books = Book.query.order_by(Book.created_at.desc()).limit(6).all()
    latest_news = (
        NewsPost.query.order_by(NewsPost.published_at.desc()).limit(3).all()
    )
    return render_template(
        "index.html", latest_books=latest_books, latest_news=latest_news
    )


@bp.route("/contact")
def contact():
    hours = [
        (tr("day.mon"), "8:00 - 16:00"),
        (tr("day.tue"), "8:00 - 16:00"),
        (tr("day.wed"), "8:00 - 16:00"),
        (tr("day.thu"), "8:00 - 17:00"),
        (tr("day.fri"), "8:00 - 15:00"),
        (tr("day.sat"), tr("hours.closed")),
        (tr("day.sun"), tr("hours.closed")),
    ]
    return render_template("contact.html", hours=hours)


@bp.route("/set-language/<lang>")
def set_language(lang: str):
    if lang in SUPPORTED_LANGS:
        session["lang"] = lang
    return redirect(request.referrer or url_for("main.index"))
