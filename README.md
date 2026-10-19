# Educational Platform Backend

The backend is a Django, Django REST Framework, and PostgreSQL project. Stage 2 adds Platform Admin teacher/workspace management and teacher invitation, login, and password setup/reset APIs.

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

Edit `backend\.env` and set a private `DJANGO_SECRET_KEY` and your PostgreSQL password. The example sets `DJANGO_SESSION_COOKIE_SECURE=False` for local HTTP development. Keep it `True` in production. Development uses Django's console email backend, and private uploads (when added) will be stored under `backend\private_media`; that directory is not served directly.

Create the PostgreSQL database and user if needed:

```powershell
psql -U postgres -c "CREATE DATABASE educational_platform;"
```

Set `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and `POSTGRES_PORT` in `backend\.env` to match your local PostgreSQL setup.
Set `PLATFORM_BASE_DOMAIN` to the domain used for workspace subdomains (default `edunova.com`) and `PLATFORM_URL_SCHEME` to `https` in production. Invitation links use `{slug}.{PLATFORM_BASE_DOMAIN}`.

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

The local example disables the Secure cookie flag so browser sessions work over `runserver`'s plain HTTP. Production must set `DJANGO_SESSION_COOKIE_SECURE=True`; the setting also defaults to `True` when unset.

## API documentation

Set `DJANGO_ENABLE_API_DOCS=True` to enable `GET /api/schema/` and `GET /api/docs/`. The example environment enables them for development. Set it to `False` to make both paths return 404.

## Stage 2 teacher onboarding and authentication

All Platform Admin API routes require an authenticated account with the `admin` role:

- `POST` and `GET /api/v1/admin/teachers/` create and list teachers.
- `GET /api/v1/admin/teachers/{id}/` views a teacher; `POST /api/v1/admin/teachers/{id}/resend-invite/` sends another password invitation.
- `GET /api/v1/admin/workspaces/` and `GET /api/v1/admin/workspaces/{id}/` list and view workspaces. `POST` to `{id}/suspend/` or `{id}/activate/` changes workspace status.

The staff authentication routes are workspace scoped:

- `POST /api/v1/workspaces/{slug}/staff/auth/login/` accepts `login_key` and `password` for an active teacher account.
- `POST /api/v1/workspaces/{slug}/staff/auth/set-password/` accepts `uid`, `token`, and `new_password` from an invitation or reset link. The link opens the future frontend route `/teacher/set-password/`; that page must submit the values to this API.
- `POST /api/v1/workspaces/{slug}/staff/auth/password-reset/` accepts the teacher's `email` and sends a reset link when the account exists.

Invitation and reset links expire according to Django's `PASSWORD_RESET_TIMEOUT`. The set-password route also completes password resets because the design defines no separate reset-finish endpoint. Emails use Django's console backend in development. If invitation delivery fails after teacher creation, the account remains available and an admin can resend the invite.

## Stage 1 models and rules

- Workspace slugs are 3–63 lowercase letters and digits with single hyphens between segments. They cannot begin or end with a hyphen. Reserved names include `admin`, `api`, `www`, `app`, `static`, `media`, `mail`, `support`, `teacher`, `login`, `signup`, `platform`, `auth`, `accounts`, `dashboard`, `billing`, `docs`, `help`, `cdn`, `assets`, and `files`.
- Workspace slugs cannot be changed after the workspace is saved.
- User `login_key` values are generated as `<workspace-id>:<lowercase-email>` or `admin:<lowercase-email>` for Platform Admins.
- New accounts default to pending approval; teacher accounts and Platform Admins created through the manager are approved.
- DRF uses session authentication, requires authentication by default, and has page-number pagination with 20 items per page.
