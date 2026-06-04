from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from .. import db
from ..i18n import tr
from ..models import Book, Loan, User

bp = Blueprint("loans", __name__)

CART_SESSION_KEY = "loan_cart"
ADMIN_CART_SESSION_KEY = "admin_loan_cart"


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_cart() -> list[int]:
    return list(session.get(CART_SESSION_KEY, []))


def _get_admin_cart() -> dict:
    """Returns {user_id: int, book_ids: [int]}."""
    return session.get(ADMIN_CART_SESSION_KEY, {"user_id": None, "book_ids": []})


def _cart_books(book_ids: list[int]) -> list[Book]:
    if not book_ids:
        return []
    books = Book.query.filter(Book.id.in_(book_ids)).all()
    id_map = {b.id: b for b in books}
    return [id_map[bid] for bid in book_ids if bid in id_map]


# ── user cart ─────────────────────────────────────────────────────────────────

@bp.route("/cart")
@login_required
def cart():
    book_ids = _get_cart()
    books = _cart_books(book_ids)
    return render_template("loans/cart.html", books=books)


@bp.route("/cart/add/<int:book_id>", methods=["POST"])
@login_required
def cart_add(book_id: int):
    book = Book.query.get_or_404(book_id)
    cart = _get_cart()
    if book_id not in cart:
        cart.append(book_id)
        session[CART_SESSION_KEY] = cart
        flash(tr("loans.cart_added", title=book.title), "success")
    else:
        flash(tr("loans.cart_already"), "info")
    next_url = request.form.get("next") or url_for("catalog.index")
    return redirect(next_url)


@bp.route("/cart/remove/<int:book_id>", methods=["POST"])
@login_required
def cart_remove(book_id: int):
    cart = _get_cart()
    if book_id in cart:
        cart.remove(book_id)
        session[CART_SESSION_KEY] = cart
    return redirect(url_for("loans.cart"))


@bp.route("/cart/confirm", methods=["POST"])
@login_required
def cart_confirm():
    cart = _get_cart()
    if not cart:
        flash(tr("loans.cart_empty"), "warning")
        return redirect(url_for("loans.cart"))

    borrowed, skipped = [], []
    for book_id in cart:
        book = Book.query.get(book_id)
        if not book:
            continue
        if book.copies_available <= 0:
            skipped.append(book.title)
            continue
        if current_user.loans.filter_by(book_id=book.id, returned_at=None).first():
            skipped.append(book.title)
            continue
        loan = Loan(user_id=current_user.id, book_id=book.id)
        db.session.add(loan)
        borrowed.append(book.title)

    db.session.commit()
    session.pop(CART_SESSION_KEY, None)

    if borrowed:
        flash(tr("loans.cart_confirmed", count=len(borrowed)), "success")
    if skipped:
        flash(tr("loans.cart_skipped", titles=", ".join(skipped)), "warning")

    return redirect(url_for("loans.my_loans"))


# ── admin cart ────────────────────────────────────────────────────────────────

@bp.route("/admin-cart")
@login_required
def admin_cart():
    if not current_user.is_admin:
        abort(403)
    acart = _get_admin_cart()
    books = _cart_books(acart.get("book_ids") or [])
    users = User.query.order_by(User.username.asc()).all()
    selected_user = db.session.get(User, acart.get("user_id")) if acart.get("user_id") else None
    return render_template("loans/admin_cart.html", books=books, users=users, selected_user=selected_user)


@bp.route("/admin-cart/set-user", methods=["POST"])
@login_required
def admin_cart_set_user():
    if not current_user.is_admin:
        abort(403)
    acart = _get_admin_cart()
    try:
        uid = int(request.form.get("user_id", 0))
    except (TypeError, ValueError):
        uid = 0
    acart["user_id"] = uid or None
    session[ADMIN_CART_SESSION_KEY] = acart
    return redirect(url_for("loans.admin_cart"))


@bp.route("/admin-cart/add/<int:book_id>", methods=["POST"])
@login_required
def admin_cart_add(book_id: int):
    if not current_user.is_admin:
        abort(403)
    book = Book.query.get_or_404(book_id)
    acart = _get_admin_cart()
    book_ids = acart.get("book_ids") or []
    if book_id not in book_ids:
        book_ids.append(book_id)
        acart["book_ids"] = book_ids
        session[ADMIN_CART_SESSION_KEY] = acart
        flash(tr("loans.cart_added", title=book.title), "success")
    else:
        flash(tr("loans.cart_already"), "info")
    next_url = request.form.get("next") or url_for("catalog.index")
    return redirect(next_url)


@bp.route("/admin-cart/remove/<int:book_id>", methods=["POST"])
@login_required
def admin_cart_remove(book_id: int):
    if not current_user.is_admin:
        abort(403)
    acart = _get_admin_cart()
    book_ids = acart.get("book_ids") or []
    if book_id in book_ids:
        book_ids.remove(book_id)
        acart["book_ids"] = book_ids
        session[ADMIN_CART_SESSION_KEY] = acart
    return redirect(url_for("loans.admin_cart"))


@bp.route("/admin-cart/confirm", methods=["POST"])
@login_required
def admin_cart_confirm():
    if not current_user.is_admin:
        abort(403)
    acart = _get_admin_cart()
    book_ids = acart.get("book_ids") or []
    user_id = acart.get("user_id")

    if not user_id:
        flash(tr("loans.admin_cart_no_user"), "warning")
        return redirect(url_for("loans.admin_cart"))
    if not book_ids:
        flash(tr("loans.cart_empty"), "warning")
        return redirect(url_for("loans.admin_cart"))

    target_user = db.session.get(User, user_id)
    if not target_user:
        flash(tr("loans.admin_cart_no_user"), "warning")
        return redirect(url_for("loans.admin_cart"))

    borrowed, skipped = [], []
    for book_id in book_ids:
        book = Book.query.get(book_id)
        if not book:
            continue
        if book.copies_available <= 0:
            skipped.append(book.title)
            continue
        if Loan.query.filter_by(user_id=target_user.id, book_id=book.id, returned_at=None).first():
            skipped.append(book.title)
            continue
        loan = Loan(user_id=target_user.id, book_id=book.id)
        db.session.add(loan)
        borrowed.append(book.title)

    db.session.commit()
    session.pop(ADMIN_CART_SESSION_KEY, None)

    if borrowed:
        flash(tr("loans.cart_confirmed", count=len(borrowed)), "success")
    if skipped:
        flash(tr("loans.cart_skipped", titles=", ".join(skipped)), "warning")

    return redirect(url_for("admin.loans"))


# ── my loans / return ─────────────────────────────────────────────────────────

@bp.route("/")
@login_required
def my_loans():
    active = (
        current_user.loans.filter_by(returned_at=None)
        .order_by(Loan.due_at.asc())
        .all()
    )
    history = (
        current_user.loans.filter(Loan.returned_at.isnot(None))
        .order_by(Loan.returned_at.desc())
        .limit(50)
        .all()
    )
    return render_template("loans/my_loans.html", active=active, history=history)


@bp.route("/return/<int:loan_id>", methods=["POST"])
@login_required
def return_book(loan_id: int):
    if not current_user.is_admin:
        abort(403)
    loan = Loan.query.get_or_404(loan_id)
    if loan.returned_at is not None:
        flash(tr("loans.return_already"), "info")
    else:
        loan.returned_at = datetime.utcnow()
        db.session.commit()
        flash(tr("loans.return_success", title=loan.book.title), "success")
    return redirect(url_for("admin.loans"))
