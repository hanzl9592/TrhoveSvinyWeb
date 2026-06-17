import re
from datetime import datetime, time

import requests

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from flask_wtf import FlaskForm
from wtforms import IntegerField, PasswordField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional

from .. import db
from ..decorators import admin_required
from ..email_service import send_mailtrap_email
from ..i18n import tr
from ..models import Book, Loan, Reservation, User

bp = Blueprint("admin", __name__)


class BookForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(1, 200)])
    author = StringField("Author", validators=[DataRequired(), Length(1, 200)])
    isbn = StringField("ISBN", validators=[Optional(), Length(0, 20)])
    category = StringField("Category", validators=[Optional(), Length(0, 80)])
    year = IntegerField(
        "Year",
        validators=[Optional(), NumberRange(min=0, max=3000)],
    )
    total_copies = IntegerField(
        "Total copies",
        validators=[Optional(), NumberRange(min=1, max=999)],
        default=1,
    )
    cover_url = StringField("Cover image URL", validators=[Optional(), Length(0, 500)])
    description = TextAreaField("Description", validators=[Optional()])
    submit = SubmitField("Save")


class AdminUserForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(3, 64)])
    first_name = StringField("First name", validators=[DataRequired(), Length(1, 80)])
    last_name = StringField("Last name", validators=[DataRequired(), Length(1, 80)])
    email = StringField("Email (optional)", validators=[Optional(), Email(), Length(3, 120)])
    role = SelectField(
        "Role",
        choices=[("student", "Student"), ("staff", "Staff"), ("admin", "Admin")],
        default="student",
    )
    password = PasswordField("Password", validators=[DataRequired(), Length(6, 128)])
    submit = SubmitField("Create user")


class EditUserRoleForm(FlaskForm):
    role = SelectField(
        "Role",
        choices=[("student", "Student"), ("staff", "Staff")],
        default="student",
    )
    is_admin = SelectField(
        "Admin rights",
        choices=[("0", "No"), ("1", "Yes")],
        default="0",
    )
    submit = SubmitField("Save")


class ManualLoanForm(FlaskForm):
    user_id = SelectField("User", coerce=int, validators=[DataRequired()])
    book_id = SelectField("Book", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Create loan")


def _placeholder_email_for(username: str) -> str:
    # SQLite deployments created earlier may still have NOT NULL on users.email.
    # Use deterministic internal placeholder for accounts created without real email.
    safe = re.sub(r"[^a-zA-Z0-9_.-]", "", username).lower() or "user"
    return f"{safe}@local.invalid"


def _normalize_book_form_values(book: Book) -> None:
    """Keep only title/author required; persist empty optional values as NULL."""
    book.title = (book.title or "").strip()
    book.author = (book.author or "").strip()
    book.isbn = ((book.isbn or "").strip() or None)
    book.category = ((book.category or "").strip() or None)
    book.cover_url = ((book.cover_url or "").strip() or None)
    book.description = ((book.description or "").strip() or None)
    book.total_copies = int(book.total_copies or 1)


@bp.before_request
@login_required
@admin_required
def _gate():
    pass


@bp.route("/")
def dashboard():
    stats = {
        "books": Book.query.count(),
        "users": User.query.count(),
        "active_loans": Loan.query.filter_by(returned_at=None).count(),
    }
    return render_template("admin/dashboard.html", stats=stats)


@bp.route("/books")
def books():
    all_books = Book.query.order_by(Book.title.asc()).all()
    return render_template("admin/books.html", books=all_books)


@bp.route("/books/suggest")
def books_suggest():
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify([])

    candidates = (
        Book.query.filter(Book.title.ilike(f"%{query}%"))
        .order_by(Book.title.asc())
        .limit(12)
        .all()
    )

    q_norm = query.casefold()
    exact = [b for b in candidates if (b.title or "").casefold() == q_norm]
    ordered = exact + [b for b in candidates if b not in exact]

    payload = [
        {
            "id": b.id,
            "title": b.title,
            "author": b.author,
            "isbn": b.isbn or "",
            "category": b.category or "",
            "year": b.year if b.year is not None else "",
            "cover_url": b.cover_url or "",
            "description": b.description or "",
            "total_copies": b.total_copies,
            "source": "local",
        }
        for b in ordered
    ]

    seen = {
        ((item.get("title") or "").strip().casefold(), (item.get("author") or "").strip().casefold())
        for item in payload
    }

    try:
        google_url = "https://www.googleapis.com/books/v1/volumes"
        params = {
            "q": f"intitle:{query}",
            "langRestrict": "cs",
            "printType": "books",
            "maxResults": 12,
        }
        response = requests.get(
            google_url,
            params=params,
            headers={"User-Agent": "Mozilla/5.0 (compatible; LibraryApp/1.0)"},
            timeout=6.0,
        )
        response.raise_for_status()
        data = response.json()

        for item in data.get("items", []):
            info = item.get("volumeInfo") or {}
            title = (info.get("title") or "").strip()
            if not title:
                continue

            authors = info.get("authors") or []
            author = (authors[0] if authors else "").strip()
            key = (title.casefold(), author.casefold())
            if key in seen:
                continue
            seen.add(key)

            published = (info.get("publishedDate") or "").strip()
            year_match = re.match(r"^(\d{4})", published)
            year = int(year_match.group(1)) if year_match else ""

            isbn = ""
            for ident in info.get("industryIdentifiers") or []:
                if ident.get("type") in {"ISBN_13", "ISBN_10"} and ident.get("identifier"):
                    isbn = ident["identifier"].strip()
                    break

            categories = info.get("categories") or []
            category = (categories[0] if categories else "").strip()
            image_links = info.get("imageLinks") or {}
            cover_url = (image_links.get("thumbnail") or "").replace("http://", "https://")

            payload.append(
                {
                    "id": None,
                    "title": title,
                    "author": author,
                    "isbn": isbn,
                    "category": category,
                    "year": year,
                    "cover_url": cover_url,
                    "description": (info.get("description") or "").strip(),
                    "total_copies": 1,
                    "source": "google-cs",
                }
            )
    except requests.exceptions.RequestException as exc:
        current_app.logger.warning("Book suggest: Google Books API call failed: %s", exc)
    except (ValueError, KeyError) as exc:
        current_app.logger.warning("Book suggest: failed to parse Google Books response: %s", exc)

    return jsonify(payload)


@bp.route("/books/new", methods=["GET", "POST"])
def book_new():
    form = BookForm()
    if form.validate_on_submit():
        book = Book()
        form.populate_obj(book)
        _normalize_book_form_values(book)
        db.session.add(book)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("ISBN already exists. Leave ISBN empty or use a unique value.", "warning")
            return render_template("admin/book_form.html", form=form, book=None)
        flash(tr("admin.book_added"), "success")
        return redirect(url_for("admin.books"))
    return render_template("admin/book_form.html", form=form, book=None)


@bp.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
def book_edit(book_id: int):
    book = Book.query.get_or_404(book_id)
    form = BookForm(obj=book)
    if form.validate_on_submit():
        form.populate_obj(book)
        _normalize_book_form_values(book)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("ISBN already exists. Leave ISBN empty or use a unique value.", "warning")
            return render_template("admin/book_form.html", form=form, book=book)
        flash(tr("admin.book_updated"), "success")
        return redirect(url_for("admin.books"))
    return render_template("admin/book_form.html", form=form, book=book)


@bp.route("/books/<int:book_id>/delete", methods=["POST"])
def book_delete(book_id: int):
    book = Book.query.get_or_404(book_id)
    if book.copies_on_loan:
        flash(tr("admin.book_delete_blocked"), "warning")
        return redirect(url_for("admin.books"))
    db.session.delete(book)
    db.session.commit()
    flash(tr("admin.book_deleted"), "info")
    return redirect(url_for("admin.books"))


@bp.route("/loans")
def loans():
    # Redirect old active-loans URL to the combined history page
    return redirect(url_for("admin.loans_history"))


@bp.route("/loans/history")
def loans_history():
    reservations = (
        Reservation.query.filter_by(status="pending")
        .order_by(Reservation.reserved_at.asc())
        .all()
    )
    active = (
        Loan.query.filter_by(returned_at=None).order_by(Loan.due_at.asc()).all()
    )
    history = (
        Loan.query.filter(Loan.returned_at.isnot(None))
        .order_by(Loan.borrowed_at.desc())
        .limit(500)
        .all()
    )
    return render_template(
        "admin/loans_history.html",
        reservations=reservations,
        active=active,
        history=history,
    )


@bp.route("/users")
def users():
    all_users = User.query.order_by(User.username.asc()).all()
    return render_template("admin/users.html", users=all_users)


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
def user_delete(user_id: int):
    user = User.query.get_or_404(user_id)

    if current_user.id == user.id:
        flash(tr("admin.cannot_delete_self"), "warning")
        return redirect(url_for("admin.users"))

    Loan.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    db.session.delete(user)
    db.session.commit()
    flash(tr("admin.user_deleted"), "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/new", methods=["GET", "POST"])
def user_new():
    form = AdminUserForm()
    form.role.choices = [
        ("student", tr("role.student")),
        ("staff", tr("role.staff")),
        ("admin", tr("role.admin")),
    ]
    if form.validate_on_submit():
        username = (form.username.data or "").strip()
        first_name = (form.first_name.data or "").strip()
        last_name = (form.last_name.data or "").strip()
        raw_email = (form.email.data or "").strip().lower()
        email = raw_email or _placeholder_email_for(username)

        if User.query.filter_by(username=username).first():
            flash(tr("admin.username_taken"), "warning")
            return render_template("admin/user_form.html", form=form)

        if User.query.filter_by(email=email).first():
            flash(tr("admin.email_taken"), "warning")
            return render_template("admin/user_form.html", form=form)

        user = User(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            role=form.role.data,
            is_email_verified=True,
            email_verification_token=None,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(tr("admin.user_created"), "success")
        return redirect(url_for("admin.users"))

    return render_template("admin/user_form.html", form=form)


PROTECTED_ADMIN_USERNAME = "M.Hanzlova"


@bp.route("/users/<int:user_id>/edit-role", methods=["GET", "POST"])
def user_edit_role(user_id: int):
    user = User.query.get_or_404(user_id)
    form = EditUserRoleForm(obj=user)
    form.role.choices = [
        ("student", tr("role.student")),
        ("staff", tr("role.staff")),
    ]
    form.is_admin.choices = [("0", tr("common.no")), ("1", tr("common.yes"))]

    # Pre-fill is_admin field from current role
    if request.method == "GET":
        form.is_admin.data = "1" if user.role == "admin" else "0"

    if form.validate_on_submit():
        new_role = form.role.data  # student / staff
        grant_admin = form.is_admin.data == "1"

        # M.Hanzlova can only be changed by herself; everyone else is free to change
        if user.username == PROTECTED_ADMIN_USERNAME and current_user.username != PROTECTED_ADMIN_USERNAME:
            flash(tr("admin.cannot_change_protected"), "warning")
            return redirect(url_for("admin.users"))

        # Determine final role value
        if grant_admin:
            final_role = "admin"
        else:
            final_role = new_role  # student or staff

        # If M.Hanzlova is the target, she can change her own role but still keeps admin
        # unless she explicitly removes it herself (grant_admin == False means she chose to remove)
        user.role = final_role
        db.session.commit()
        flash(tr("admin.user_role_updated"), "success")
        return redirect(url_for("admin.users"))

    return render_template("admin/user_edit_role.html", form=form, user=user)


@bp.route("/loans/new", methods=["GET", "POST"])
def loans_new():
    form = ManualLoanForm()
    users = User.query.order_by(User.username.asc()).all()
    books = Book.query.order_by(Book.title.asc()).all()

    form.user_id.choices = [(u.id, f"{u.username} ({u.role})") for u in users]
    form.book_id.choices = [(b.id, f"{b.title} - {b.author}") for b in books]

    if form.validate_on_submit():
        due_date_raw = (request.form.get("due_date") or "").strip()
        if not due_date_raw:
            flash(tr("loans.due_date_required"), "warning")
            return render_template("admin/loan_form.html", form=form)
        try:
            due_date = datetime.strptime(due_date_raw, "%Y-%m-%d").date()
            due_at = datetime.combine(due_date, time(hour=23, minute=59, second=59))
        except ValueError:
            flash(tr("loans.due_date_invalid"), "warning")
            return render_template("admin/loan_form.html", form=form)

        user = db.session.get(User, form.user_id.data)
        book = db.session.get(Book, form.book_id.data)
        if not user or not book:
            flash(tr("admin.invalid_selection"), "warning")
            return render_template("admin/loan_form.html", form=form)

        if book.copies_available <= 0:
            flash(tr("admin.book_unavailable"), "warning")
            return render_template("admin/loan_form.html", form=form)

        existing = Loan.query.filter_by(
            user_id=user.id,
            book_id=book.id,
            returned_at=None,
        ).first()
        if existing:
            flash(tr("admin.loan_exists"), "info")
            return render_template("admin/loan_form.html", form=form)

        loan = Loan(user_id=user.id, book_id=book.id, due_at=due_at)
        db.session.add(loan)
        db.session.commit()
        flash(tr("admin.loan_created", username=user.username, due=loan.due_at.strftime("%Y-%m-%d")), "success")
        return redirect(url_for("admin.loans"))

    return render_template("admin/loan_form.html", form=form)


@bp.route("/send-test-email", methods=["POST"])
@login_required
@admin_required
def send_test_email():
    """Send a test verification email for debugging purposes."""
    test_email = "ondrejhanzl@seznam.cz"
    verify_link = "https://trhovesvinyweb.onrender.com/auth/verify-email/test-token"
    subject = tr("auth.verify_subject")
    
    ok, code, detail = send_mailtrap_email(
        to_email=test_email,
        subject=subject,
        text=f"{verify_link}\n",
        category="Test Email",
    )
    
    if ok:
        current_app.logger.info("Test email sent successfully [%s]", code)
        flash(tr("admin.test_email_sent", email=test_email), "success")
    else:
        current_app.logger.warning("Test email failed [%s]: %s", code, detail)
        flash(tr("admin.test_email_failed", code=code, detail=detail), "danger")
    
    return redirect(url_for("admin.dashboard"))
