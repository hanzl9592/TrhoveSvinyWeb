from datetime import datetime, time

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from .. import db
from ..i18n import tr
from ..models import Book, Loan, User, Reservation

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
    if not current_user.is_admin:
        abort(403)
    book_ids = _get_cart()
    books = _cart_books(book_ids)
    return render_template("loans/cart.html", books=books)


@bp.route("/cart/add/<int:book_id>", methods=["POST"])
@login_required
def cart_add(book_id: int):
    if not current_user.is_admin:
        abort(403)
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
    if not current_user.is_admin:
        abort(403)
    cart = _get_cart()
    if book_id in cart:
        cart.remove(book_id)
        session[CART_SESSION_KEY] = cart
    return redirect(url_for("loans.cart"))


@bp.route("/cart/confirm", methods=["POST"])
@login_required
def cart_confirm():
    if not current_user.is_admin:
        abort(403)
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


# ── reservations (user) ───────────────────────────────────────────────────────

@bp.route("/reserve/<int:book_id>", methods=["POST"])
@login_required
def reserve(book_id: int):
    """User makes a reservation for a book."""
    if current_user.is_admin:
        abort(403)
    
    book = Book.query.get_or_404(book_id)

    if book.copies_available <= 0:
        flash(tr("loans.no_copies_available", title=book.title), "warning")
        next_url = request.form.get("next") or url_for("catalog.index")
        return redirect(next_url)
    
    # Check if user already has this book on loan
    if current_user.loans.filter_by(book_id=book.id, returned_at=None).first():
        flash(tr("loans.already_on_loan", title=book.title), "warning")
        next_url = request.form.get("next") or url_for("catalog.index")
        return redirect(next_url)
    
    # Check if user already has a pending reservation
    existing = Reservation.query.filter_by(
        user_id=current_user.id, 
        book_id=book.id, 
        status="pending"
    ).first()
    if existing:
        flash(tr("loans.already_reserved", title=book.title), "info")
        next_url = request.form.get("next") or url_for("catalog.index")
        return redirect(next_url)
    
    # Create reservation
    reservation = Reservation(user_id=current_user.id, book_id=book.id)
    db.session.add(reservation)
    db.session.commit()
    flash(tr("loans.reservation_made", title=book.title), "success")
    
    next_url = request.form.get("next") or url_for("catalog.index")
    return redirect(next_url)


@bp.route("/reservations")
@login_required
def reservations():
    """View user's reservations."""
    if current_user.is_admin:
        abort(403)
    
    pending = current_user.reservations.filter_by(status="pending").order_by(Reservation.reserved_at.desc()).all()
    confirmed = current_user.reservations.filter_by(status="confirmed").order_by(Reservation.reserved_at.desc()).all()
    return render_template("loans/reservations.html", pending=pending, confirmed=confirmed)


@bp.route("/reservation/cancel/<int:reservation_id>", methods=["POST"])
@login_required
def cancel_reservation(reservation_id: int):
    """User cancels their reservation."""
    reservation = Reservation.query.get_or_404(reservation_id)
    
    if reservation.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    if reservation.status == "pending":
        db.session.delete(reservation)
        db.session.commit()
        flash(tr("loans.reservation_cancelled", title=reservation.book.title), "success")
    else:
        flash(tr("loans.cannot_cancel_confirmed"), "warning")
    
    return redirect(url_for("loans.reservations"))


# ── reservations (admin) ──────────────────────────────────────────────────────

@bp.route("/admin/reservations")
@login_required
def admin_reservations():
    """Admin view all pending reservations."""
    if not current_user.is_admin:
        abort(403)
    
    pending = Reservation.query.filter_by(status="pending").order_by(Reservation.reserved_at.asc()).all()
    return render_template("loans/admin_reservations.html", reservations=pending)


@bp.route("/admin/reservation/confirm/<int:reservation_id>", methods=["POST"])
@login_required
def admin_confirm_reservation(reservation_id: int):
    """Admin confirms a reservation and creates a loan."""
    if not current_user.is_admin:
        abort(403)
    
    reservation = Reservation.query.get_or_404(reservation_id)

    due_date_raw = (request.form.get("due_date") or "").strip()
    if not due_date_raw:
        flash(tr("loans.due_date_required"), "warning")
        return redirect(url_for("loans.admin_reservations"))
    try:
        due_date = datetime.strptime(due_date_raw, "%Y-%m-%d").date()
        due_at = datetime.combine(due_date, time(hour=23, minute=59, second=59))
    except ValueError:
        flash(tr("loans.due_date_invalid"), "warning")
        return redirect(url_for("loans.admin_reservations"))
    
    if reservation.status != "pending":
        flash(tr("loans.not_pending_reservation"), "info")
        return redirect(url_for("loans.admin_reservations"))
    
    book = reservation.book
    
    # A pending reservation already reduces copies_available by 1.
    # Add it back so the reservation can confirm the copy it already holds.
    available_for_confirmation = book.copies_available + 1
    if available_for_confirmation <= 0:
        flash(tr("loans.no_copies_available", title=book.title), "warning")
        return redirect(url_for("loans.admin_reservations"))
    
    # Check if user already has this book on loan
    if Loan.query.filter_by(user_id=reservation.user_id, book_id=book.id, returned_at=None).first():
        flash(tr("loans.user_already_has_book", title=book.title), "warning")
        return redirect(url_for("loans.admin_reservations"))
    
    # Create loan from reservation
    loan = Loan(user_id=reservation.user_id, book_id=book.id, due_at=due_at)
    reservation.status = "confirmed"
    reservation.confirmed_at = datetime.utcnow()
    
    db.session.add(loan)
    db.session.commit()
    
    flash(tr("loans.reservation_confirmed", title=book.title, username=reservation.user.username), "success")
    return redirect(url_for("loans.admin_reservations"))


@bp.route("/admin/reservation/decline/<int:reservation_id>", methods=["POST"])
@login_required
def admin_decline_reservation(reservation_id: int):
    """Admin declines/removes a reservation."""
    if not current_user.is_admin:
        abort(403)
    
    reservation = Reservation.query.get_or_404(reservation_id)
    
    if reservation.status == "pending":
        book_title = reservation.book.title
        db.session.delete(reservation)
        db.session.commit()
        flash(tr("loans.reservation_declined", title=book_title), "success")
    else:
        flash(tr("loans.cannot_decline_confirmed"), "info")
    
    return redirect(url_for("loans.admin_reservations"))
