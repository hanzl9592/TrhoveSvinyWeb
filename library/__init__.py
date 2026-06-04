"""Application factory for the Grammar School Library site."""
from __future__ import annotations

import os
from pathlib import Path
from flask import Flask, url_for
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import text

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "info"

STATIC_ADMIN_USERNAME = "admin"
STATIC_ADMIN_PASSWORD = "admin1984"


def _get_gallery_images(app: Flask) -> list[dict[str, str]]:
    """Return homepage gallery images from static/img/main with a safe fallback."""
    static_root = Path(app.static_folder or "")
    gallery_root = static_root / "img" / "main"
    allowed_suffixes = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    images: list[dict[str, str]] = []

    if gallery_root.exists():
        for file_path in sorted(gallery_root.iterdir(), key=lambda item: item.name.lower()):
            if not file_path.is_file() or file_path.suffix.lower() not in allowed_suffixes:
                continue
            relative_path = file_path.relative_to(static_root).as_posix()
            alt_text = file_path.stem.replace("_", " ").replace("-", " ").strip() or "Library"
            images.append(
                {
                    "src": url_for("static", filename=relative_path),
                    "alt": alt_text,
                }
            )

    if images:
        return images

    # Fallback keeps homepage slider working when folder is empty.
    return [
        {
            "src": url_for("static", filename="img/Library.jpg"),
            "alt": "Library",
        },
        {
            "src": url_for("static", filename="img/Library2.jpg"),
            "alt": "Library 2",
        },
    ]


def _ensure_schema_upgrades(app: Flask) -> None:
    """Apply lightweight runtime schema upgrades for SQLite deployments."""
    with app.app_context():
        inspector = db.inspect(db.engine)
        if "users" not in inspector.get_table_names():
            return

        columns = {col["name"] for col in inspector.get_columns("users")}
        conn = db.session.connection()

        if "is_email_verified" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN is_email_verified BOOLEAN NOT NULL DEFAULT 0"
                )
            )
            # Existing accounts are trusted to avoid accidental lockouts.
            conn.execute(text("UPDATE users SET is_email_verified = 1"))

        if "email_verification_token" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN email_verification_token VARCHAR(128)"
                )
            )

        if "first_name" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN first_name VARCHAR(80)"
                )
            )

        if "last_name" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN last_name VARCHAR(80)"
                )
            )

        if "email_verification_expires_at" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN email_verification_expires_at DATETIME"
                )
            )

        if "password_reset_token" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN password_reset_token VARCHAR(128)"
                )
            )

        if "password_reset_expires_at" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN password_reset_expires_at DATETIME"
                )
            )

        db.session.commit()


def _ensure_static_admin() -> None:
    """Create or normalize the built-in admin account used for local login."""
    from .models import User

    admin_email = "admin@school.local"
    admin_user = User.query.filter_by(username=STATIC_ADMIN_USERNAME).first()
    email_owner = User.query.filter_by(email=admin_email).first()
    if email_owner is not None and email_owner.username != STATIC_ADMIN_USERNAME:
        admin_email = f"{STATIC_ADMIN_USERNAME}-{email_owner.id}@school.local"

    if admin_user is None:
        admin_user = User(
            username=STATIC_ADMIN_USERNAME,
            first_name="Admin",
            last_name="",
            email=admin_email,
            role="admin",
            is_email_verified=True,
        )
        db.session.add(admin_user)

    admin_user.email = admin_email
    admin_user.role = "admin"
    admin_user.is_email_verified = True
    admin_user.email_verification_token = None
    admin_user.email_verification_expires_at = None
    admin_user.password_reset_token = None
    admin_user.password_reset_expires_at = None
    admin_user.set_password(STATIC_ADMIN_PASSWORD)
    db.session.commit()


def create_app(config: dict | None = None) -> Flask:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    env_path = os.path.join(project_root, ".env")
    if load_dotenv is not None:
        load_dotenv(env_path)
    elif os.path.exists(env_path):
        # Fallback loader so app still works if python-dotenv is not installed.
        with open(env_path, "r", encoding="utf-8") as env_file:
            for line in env_file:
                raw = line.strip()
                if not raw or raw.startswith("#") or "=" not in raw:
                    continue
                key, value = raw.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)

    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-change-me"),
        SQLALCHEMY_DATABASE_URI="sqlite:///"
        + os.path.join(app.instance_path, "library.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAIL_SERVER=os.environ.get("MAIL_SERVER", "live.smtp.mailtrap.io"),
        MAIL_PORT=int(os.environ.get("MAIL_PORT", "587")),
        MAIL_USE_TLS=os.environ.get("MAIL_USE_TLS", "1") == "1",
        MAIL_USERNAME=os.environ.get("MAIL_USERNAME", "api"),
        MAIL_PASSWORD=os.environ.get("MAIL_PASSWORD", ""),
        MAIL_DEFAULT_SENDER=os.environ.get(
            "MAIL_DEFAULT_SENDER", "Private Person <hello@skolniknihovnats.com>"
        ),
        EMAIL_VERIFICATION_TOKEN_TTL_HOURS=int(
            os.environ.get("EMAIL_VERIFICATION_TOKEN_TTL_HOURS", "24")
        ),
        PASSWORD_RESET_TOKEN_TTL_HOURS=int(
            os.environ.get("PASSWORD_RESET_TOKEN_TTL_HOURS", "2")
        ),
    )
    if config:
        app.config.update(config)

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from .i18n import init_i18n
    init_i18n(app)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    # Blueprints
    from .blueprints.main import bp as main_bp
    from .blueprints.auth import bp as auth_bp
    from .blueprints.catalog import bp as catalog_bp
    from .blueprints.loans import bp as loans_bp
    from .blueprints.news import bp as news_bp
    from .blueprints.admin import bp as admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(catalog_bp, url_prefix="/catalog")
    app.register_blueprint(loans_bp, url_prefix="/loans")
    app.register_blueprint(news_bp, url_prefix="/news")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    @app.context_processor
    def inject_main_gallery_images():
        return {"main_gallery_images": _get_gallery_images(app)}

    with app.app_context():
        db.create_all()
        _ensure_static_admin()

    _ensure_schema_upgrades(app)

    # CLI
    from .seed import register_cli
    register_cli(app)

    return app
