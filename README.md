# Grammar School Library

A small Flask web application for a school library. Includes a book catalog
with search, borrow/return tracking, student & staff accounts, an admin panel
for managing books, and a news/announcements section.

## Tech

- Python 3.10+
- Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF
- SQLite (file-based, lives in `instance/library.db`)

## Project layout

```
run.py                      # entry point
requirements.txt
library/
  __init__.py               # app factory
  models.py                 # User, Book, Loan, NewsPost
  seed.py                   # CLI commands: init-db, seed
  decorators.py             # @admin_required
  blueprints/
    main.py     auth.py     catalog.py
    loans.py    news.py     admin.py
  templates/                # Jinja2 templates
  static/css/style.css
```

## Setup (Windows PowerShell)

```powershell
# from the project folder
pip install -r requirements.txt

$env:FLASK_APP = "run.py"
flask init-db          # create tables
flask seed             # add admin user + sample books + news

python run.py          # http://127.0.0.1:5000
```

## Default accounts (after `flask seed`)

| Role    | Username | Password    |
|---------|----------|-------------|
| Admin   | admin    | admin123    |
| Student | student  | student123  |

Change these immediately in any real deployment, and set a strong
`SECRET_KEY` environment variable.

## Features

- Browse / search book catalog (title, author, ISBN, category filter)
- Book detail pages with availability
- Borrow & return books (logged-in users)
- Student / staff registration & login
- Admin dashboard: add/edit/delete books, view active loans and users
- News & announcements (admins post; everyone reads)
- Contact page with opening hours
- Email verification for new accounts
- Password reset via email link

## Email Setup

Set these environment variables before running the app if you want real email delivery:

```powershell
$env:MAIL_SERVER = "live.smtp.mailtrap.io"
$env:MAIL_PORT = "587"
$env:MAIL_USE_TLS = "1"
$env:MAIL_USERNAME = "api"
$env:MAIL_PASSWORD = "YOUR_MAILTRAP_API_TOKEN"
$env:MAIL_DEFAULT_SENDER = "Private Person <hello@skolniknihovnats.com>"

# Optional token expiry settings
$env:EMAIL_VERIFICATION_TOKEN_TTL_HOURS = "24"
$env:PASSWORD_RESET_TOKEN_TTL_HOURS = "2"
```

If `MAIL_SERVER` is not configured, the app shows verification/reset links in flash messages so you can still test the flow locally.

### Recommended: .env file (auto-loaded)

The app now loads settings automatically from `.env` in the project root on startup.

1. Copy `.env.example` to `.env`.
2. Set your real `MAIL_PASSWORD` (Mailtrap API token).
3. Run `python run.py`.

PowerShell copy command:

```powershell
Copy-Item .env.example .env
```

## Account Flow

- Register with username, email, role, and password.
- Open the verification link sent by email (or shown in a flash message in local mode).
- Sign in only after email verification.
- Use "Forgot password?" on the sign-in page to receive a reset link.
