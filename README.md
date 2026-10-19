# Educational Platform Backend

The backend is a Django, Django REST Framework, and PostgreSQL project. Stage 1 provides the project foundation, workspaces, accounts, Django admin, and optional API documentation. No product API endpoints are included yet.

## Requirements

- Python 3.14
- PostgreSQL 15 or newer

## Local setup (PowerShell)

Run these commands from the repository root:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
python -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
```

Edit `backend\.env` and set a private `DJANGO_SECRET_KEY` and your PostgreSQL password. Development uses Django's console email backend, and private uploads (when added) will be stored under `backend\private_media`; that directory is not served directly.

Create the PostgreSQL database and user if needed:

```powershell
psql -U postgres -c "CREATE DATABASE educational_platform;"
```

Set `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and `POSTGRES_PORT` in `backend\.env` to match your local PostgreSQL setup.

## Migrations, checks, and tests

```powershell
Set-Location backend
python manage.py migrate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Django's test runner creates and removes a temporary test database. The PostgreSQL role must be allowed to create databases.

## Create a Platform Admin

```powershell
python manage.py createsuperuser
```

When prompted for the username (`login_key`), enter `admin:<email>` (for example, `admin:owner@example.com`), then enter that email, a full name, and a password. The account is created with the admin role and no workspace.

Start the development server and open the Django admin at the configured `DJANGO_ADMIN_PATH` (default: `http://127.0.0.1:8000/platform-admin/`):

```powershell
python manage.py runserver
```

## API documentation

Set `DJANGO_ENABLE_API_DOCS=True` to enable `GET /api/schema/` and `GET /api/docs/`. The example environment enables them for development. Set it to `False` to make both paths return 404.

## Stage 1 models and rules

- Workspace slugs are 3–63 lowercase letters and digits with single hyphens between segments. They cannot begin or end with a hyphen. Reserved names include `admin`, `api`, `www`, `app`, `static`, `media`, `mail`, `support`, `teacher`, `login`, `signup`, `platform`, `auth`, `accounts`, `dashboard`, `billing`, `docs`, `help`, `cdn`, `assets`, and `files`.
- Workspace slugs cannot be changed after the workspace is saved.
- User `login_key` values are generated as `<workspace-id>:<lowercase-email>` or `admin:<lowercase-email>` for Platform Admins.
- New accounts default to pending approval; teacher accounts and Platform Admins created through the manager are approved.
- DRF uses session authentication, requires authentication by default, and has page-number pagination with 20 items per page.
