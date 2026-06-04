"""Application factory for the Grammar School Library site."""
from __future__ import annotations

import os
from flask import Flask
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

    with app.app_context():
        db.create_all()

    _ensure_schema_upgrades(app)

    # CLI
    from .seed import register_cli
    register_cli(app)

    return app
