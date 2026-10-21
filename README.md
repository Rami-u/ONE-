# Educational Platform Backend

The backend is a Django, Django REST Framework, and PostgreSQL project. Stage 3 adds public teacher showcase APIs and teacher workspace settings, including public logo uploads.

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

Edit `backend\.env` and set a private `DJANGO_SECRET_KEY` and your PostgreSQL password. The example sets `DJANGO_SESSION_COOKIE_SECURE=False` for local HTTP development. Keep it `True` in production. Development uses Django's console email backend. In production, set `DJANGO_DEBUG=False`, configure `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, and `DEFAULT_FROM_EMAIL`, and set `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` (or omit `EMAIL_BACKEND` to use the SMTP default when debug is off). Workspace logos are JPEG, PNG, or WebP images up to 2 MB; development serves these from `backend\public_media` at `/media/`. Private uploads belong under `backend\private_media` and are not served directly.

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

When prompted for the username, enter `admin:<email>` (for example, `admin:owner@example.com`), then enter that email, a full name, and a password. The account is created with the admin role and no workspace.

Start the development server and open the Django admin at the configured `DJANGO_ADMIN_PATH` (default: `http://127.0.0.1:8000/platform-admin/`):

```powershell
python manage.py runserver
```

The local example disables the Secure cookie flag so browser sessions work over `runserver`'s plain HTTP. Production must set `DJANGO_SESSION_COOKIE_SECURE=True`; the setting also defaults to `True` when unset.

## API documentation

Set `DJANGO_ENABLE_API_DOCS=True` to enable `GET /api/schema/` and `GET /api/docs/`. The example environment enables them for development. Set it to `False` to make both paths return 404.

## Stage 3 public showcase and workspace settings

- `GET /api/v1/public/teachers/` returns active, listed teacher workspaces with page-number pagination (20 per page) and `?search=` across workspace name and headline.
- `GET /api/v1/public/teachers/{slug}/` returns a listed workspace's safe public profile.
- `GET /api/v1/workspaces/{slug}/branding/` returns branding for any active workspace.
- `GET /api/v1/workspaces/{slug}/public-profile/` returns the same safe profile for any active workspace, listed or unlisted. Courses are an empty list until Stage 5.
- The authenticated teacher can `GET` and `PATCH /api/v1/workspaces/{slug}/` for workspace profile settings. The slug cannot be changed. Logo PATCH requests use multipart form data.

Suspended workspaces return `403` with `Workspace is unavailable.` on branding, workspace public-profile, and teacher workspace settings GET/PATCH routes; unknown slugs return `404` with `Workspace not found.`. The public teacher directory omits suspended workspaces and the public teacher profile returns `404`. Public serializers do not include email addresses, passwords, or student counts.

In production, configure the web server to serve `/media/` from `backend/public_media`; Django serves these logos directly only in development.

## Stage 4 student authentication and approval

Student routes use the workspace slug in the URL:

- `GET /api/v1/workspaces/{slug}/auth/csrf/` sets the CSRF cookie and returns `204`.
- `POST /api/v1/workspaces/{slug}/auth/register/` creates a pending student without starting a session; phone is optional at registration.
- `POST /api/v1/workspaces/{slug}/auth/login/`, `logout/`, and `GET .../me/` use Django sessions. Only approved students can log in; `me` also supports the workspace teacher.
- `POST .../password-reset/` starts a generic-response reset email, and `POST .../password-reset/confirm/` consumes its single-use token.
- Teachers can list students at `GET /api/v1/workspaces/{slug}/students/` and approve or reject them at `POST .../{id}/approve/` and `POST .../{id}/reject/`.

Registration, login, reset, and reset-confirm are throttled by client IP. Suspended workspaces return `403` with `Workspace is unavailable.` for these new routes. Rejected students remain in the database and cannot log in or register again with the same workspace email.

### Trying session endpoints by hand

Sign in as the teacher first. This creates `cookies.txt` with the teacher session. The CSRF request adds `csrftoken` to the same cookie jar; the approval request sends it back in `X-CSRFToken`.

```powershell
curl.exe -c cookies.txt -X POST `
  -H "Content-Type: application/json" `
  --data '{"email":"teacher@example.com","password":"replace-with-password"}' `
  http://127.0.0.1:8000/api/v1/workspaces/science/staff/auth/login/
curl.exe -c cookies.txt -b cookies.txt http://127.0.0.1:8000/api/v1/workspaces/science/auth/csrf/
$csrfLine = Get-Content .\cookies.txt | Where-Object { $_ -match '\scsrftoken\s' } | Select-Object -Last 1
$csrfToken = ($csrfLine.Trim() -split '\s+')[-1]
curl.exe -c cookies.txt -b cookies.txt -X POST `
  -H "Content-Type: application/json" `
  -H "X-CSRFToken: $csrfToken" `
  --data '{}' `
  http://127.0.0.1:8000/api/v1/workspaces/science/students/{student_id}/approve/
```

```bash
curl -c cookies.txt -X POST \
  -H 'Content-Type: application/json' \
  --data '{"email":"teacher@example.com","password":"replace-with-password"}' \
  http://127.0.0.1:8000/api/v1/workspaces/science/staff/auth/login/
curl -c cookies.txt -b cookies.txt http://127.0.0.1:8000/api/v1/workspaces/science/auth/csrf/
csrf_token=$(awk '$6 == "csrftoken" { token = $7 } END { print token }' cookies.txt)
curl -c cookies.txt -b cookies.txt -X POST \
  -H 'Content-Type: application/json' \
  -H "X-CSRFToken: $csrf_token" \
  --data '{}' \
  http://127.0.0.1:8000/api/v1/workspaces/science/students/{student_id}/approve/
```

### Troubleshooting

#### `/api/docs/` shows Not Found

API documentation is disabled when `DJANGO_ENABLE_API_DOCS=False`. If `DJANGO_ENABLE_API_DOCS` is unset, it follows `DJANGO_DEBUG`: docs are disabled when `DJANGO_DEBUG=False` and enabled when `DJANGO_DEBUG=True`. Operating-system environment variables override values in `backend/.env`. In PowerShell, an environment variable remains set in that terminal tab after the server is restarted, so it can continue overriding `.env`.

Check and remove a terminal-level debug override with:

```powershell
echo $env:DJANGO_DEBUG
Remove-Item Env:DJANGO_DEBUG
```

If needed, check and remove a terminal-level docs override too:

```powershell
echo $env:DJANGO_ENABLE_API_DOCS
Remove-Item Env:DJANGO_ENABLE_API_DOCS
```

Then set the desired values in `backend/.env` and restart `runserver`.

## Stage 2 teacher onboarding and authentication

All Platform Admin API routes require an authenticated account with the `admin` role:

- `POST` and `GET /api/v1/admin/teachers/` create and list teachers.
- `GET /api/v1/admin/teachers/{id}/` views a teacher; `POST /api/v1/admin/teachers/{id}/resend-invite/` sends another password invitation.
- `GET /api/v1/admin/workspaces/` and `GET /api/v1/admin/workspaces/{id}/` list and view workspaces. `POST` to `{id}/suspend/` or `{id}/activate/` changes workspace status.

The staff authentication routes are workspace scoped:

- `POST /api/v1/workspaces/{slug}/staff/auth/login/` accepts `email` and `password`. The server combines the normalized email with the workspace ID resolved from `{slug}`. Login errors use the same generic response.
- `POST /api/v1/workspaces/{slug}/staff/auth/set-password/` accepts `uid`, `token`, and `new_password` from an invitation or reset link. The link opens the future frontend route `/teacher/set-password/`; that page must submit the values to this API.
- `POST /api/v1/workspaces/{slug}/staff/auth/password-reset/` accepts the teacher's `email` and sends a reset link when the account exists.

Invitation and reset links expire according to `PASSWORD_RESET_TIMEOUT_SECONDS` (default `259200`, or 3 days). The set-password route also completes password resets because the design defines no separate reset-finish endpoint. Email delivery errors do not reveal whether an account exists; failed invites can be resent by an admin. Console email is selected by default with `DJANGO_DEBUG=True`; SMTP is the default with debug disabled.

Staff login, password-reset, and set-password requests are rate limited by the caller's IP, including requests made with an authenticated session. `DRF_NUM_PROXIES` defaults to `0`, which ignores `X-Forwarded-For`; production deployments behind exactly one trusted reverse proxy must set it to `1`. See [Production: shared cache for throttling](#production-shared-cache-for-throttling) for configuring shared counters across workers.

### Production: shared cache for throttling

DRF stores throttle counters in Django's default cache. For a multi-worker deployment, configure a shared cache so requests handled by different workers use the same counters. Django's database cache is available without adding a dependency:

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "throttle_cache",
    }
}
```

Create its table once with `python manage.py createcachetable`. Student throttles use this same default cache as staff throttles. A shared Redis cache is another option, but requires approval to add a dependency. Reverse-proxy rate limits on login routes complement DRF throttling; configure `DRF_NUM_PROXIES` to match the actual number of trusted proxies.

## Stage 1 models and rules

- Workspace slugs are 3–63 lowercase letters and digits with single hyphens between segments. They cannot begin or end with a hyphen. Reserved names include `admin`, `api`, `www`, `app`, `static`, `media`, `mail`, `support`, `teacher`, `login`, `signup`, `platform`, `auth`, `accounts`, `dashboard`, `billing`, `docs`, `help`, `cdn`, `assets`, and `files`.
- Workspace slugs cannot be changed after the workspace is saved.
- Account identifiers are generated as `<workspace-id>:<lowercase-email>` or `admin:<lowercase-email>` for Platform Admins.
- New accounts default to pending approval; teacher accounts and Platform Admins created through the manager are approved.
- DRF uses session authentication, requires authentication by default, and has page-number pagination with 20 items per page.

## Team documents

- `docs/review-checklist.md`: Checklist for the human reviewer of a stage.
- `docs/open-questions.md`: Decisions the team has not made yet.
- `docs/deployment.md`: Production deployment checklist.
