# memory.md - Project memory for the coding agent

**Read this file first, at the start of every session.** It is the map and the current state of the project, so you do not need to scan the whole repository.

It is **not a copy of the design.** For details, read only the design sections named in your prompt or in the index below. It is also **not a log of everything you did**: keep it short (about 200 lines at most) and rewrite entries instead of appending forever.

You update it at the end of every stage, in the same commit as the code (see AGENTS.md, definition of done). If this file and the code disagree, the code is right: fix this file and mention it in your report.

---

## 1. The project in five lines

- A multi-tenant educational platform: each teacher has a workspace on their own sub-domain.
- Backend only for now: Django + Django REST Framework + PostgreSQL, session authentication.
- Roles: Platform Admin (no workspace), teacher, student (assistant is planned, not active).
- Flow: admin creates a teacher and workspace, students register and wait for approval, then enroll in free or paid courses (manual payment confirmed by the teacher).
- AI quiz generation, mistake analysis, and proctoring are planned for later and are **not built** in this round.

## 2. Files and when to read them

| File | What it is | When to read |
|---|---|---|
| `memory.md` | This file: map, status, decisions | Every session, first |
| `AGENTS.md` | Rules, patterns, definition of done | Every session, completely |
| `docs/backend-design.md` | The full design | Only the sections named in your prompt |
| `README.md` | How to run, test, add a feature | When setting up or finishing a stage |
| `backend/.env.example` | Every environment variable | When touching settings |

## 3. Design index: which section answers what

| Question | Section |
|---|---|
| What is in and out of this round? | Build Scope (top of the design), section 15 |
| Roles and what each may do | 2, 9.6 |
| User flows | 4.1 directory, 4.2 teacher onboarding, 4.3 students, 4.4 enrollment and payment |
| Fields, choices, constraints of a table | 5.x (one subsection per table) |
| How tables relate | 6.1 |
| Endpoints and who may call them | 7.1 public, 7.2 student auth, 7.3 staff auth, 7.4 admin, 7.5 workspace and students, 7.6 courses, 7.7 payments, 7.9 out of scope |
| Request and response examples | 8.x |
| Authentication, permissions, tenant isolation, isolation tests | 9.1-9.7 |
| App layout | 10.1 |
| Business rules that must never break | 12 |
| Sub-domains and local development | 13 |
| Stage order and what each stage contains | 14 |
| Decisions already made | 15 |

## 4. Scope reminder

- **Built this round:** Stages 1-5 working with tests; Stage 6 as models-only skeleton.
- **Not built, do not add:** frontend, deployment, AI generation, mistake analysis, proctoring, assistant permissions, email verification, online payments, refunds, endpoints for sections, lessons, assets, and assessments.
- **Placeholders:** `apps/ai/` and `apps/proctoring/` are empty (README only).

## 5. Status

Update the row of the stage you worked on. Statuses: `not started`, `in progress`, `done - awaiting review`, `merged`.

| Stage | Content | Status | Branch | Reviewer |
|---|---|---|---|---|
| 1 | Bootstrap, workspaces, accounts | merged (PR #1) | stage-1-fixes | - |
| 2 | Teacher onboarding, staff login | merged (PR #2; hardening PR #3) | stage-2-teacher-onboarding; stage-2-hardening | - |
| 3 | Public showcase, workspace settings | not started | - | - |
| 4 | Student registration, login, approval | not started | - | - |
| 5 | Courses, enrollment, manual payments | not started | - | - |
| 6 | Content and assessment skeleton | not started | - | - |

## 6. Repository map

Fill this in as apps are created. One row per app, kept to one line each.

| App | Responsibility | Key models | Endpoints (prefix `/api/v1/`) | Stage |
|---|---|---|---|---|
| workspaces | Tenant configuration and identity; admin workspace lifecycle | `Workspace` | Admin workspace list/detail/suspend/activate (`admin/workspaces/`) | 2 |
| accounts | Custom identity, teacher onboarding, and staff auth | `User` | Admin teacher management (`admin/teachers/`); staff auth (`workspaces/{slug}/staff/auth/`) | 2 |

## 7. Reusable building blocks

The patterns the team will copy. Record where each one lives so nobody rewrites it.

| Name | Location | Use it for |
|---|---|---|
| Workspace slug validator | `backend/apps/workspaces/validators.py` | Enforce normalized slug syntax and reserved names |
| Workspace slug immutability | `backend/apps/workspaces/models.py` | Reject slug changes after creation |
| User manager and login key derivation | `backend/apps/accounts/managers.py`, `backend/apps/accounts/models.py` | Create workspace accounts and Platform Admins; derive normalized login keys |
| Teacher/workspace onboarding transaction and invitation mail | `backend/apps/accounts/services.py` | Atomically create teacher/workspace; send invitation after commit; resend/reset password links |
| Platform Admin and active workspace checks | `backend/apps/accounts/permissions.py` | Protect platform admin routes and reject staff auth for missing/suspended workspaces |
| Staff password token and API routes | `backend/apps/accounts/tokens.py`, `backend/apps/accounts/urls.py`, `backend/apps/accounts/views.py` | Expiring, single-use password tokens; teacher login and password setup/reset |
| Shared login-key construction | `backend/apps/accounts/identity.py` | Build a normalized workspace-scoped login key consistently in model saves and staff login |
| Client-IP throttling | `backend/apps/accounts/views.py`, `backend/config/settings.py`, `backend/.env.example` | Use DRF `get_ident` for all staff auth throttles; set trusted proxy count with `DRF_NUM_PROXIES` (default 0) |
| Environment-driven email delivery and token expiry | `backend/config/settings.py`, `backend/apps/accounts/services.py`, `backend/.env.example` | Configure console/SMTP delivery and `PASSWORD_RESET_TIMEOUT_SECONDS` (default 259200); email links state expiry in days |

## 8. Decisions the design did not cover

One line each: what you decided, why, and the stage. The reviewer checks this list.

- Workspace slugs use 3–63 lowercase letters/digits joined by single hyphens; additionally reserve `auth`, `accounts`, `dashboard`, `billing`, `docs`, `help`, `cdn`, `assets`, and `files` to keep common service subdomains unavailable to workspaces (Stage 1).
- Workspace logos are stored as nullable URL references, matching the design's “image URL/reference” without introducing uploads in Stage 1.
- New accounts default to pending approval; the user manager marks teacher, assistant, and Platform Admin accounts approved on creation.
- Exact dependencies are pinned to Django 6.0.8, DRF 3.17.2, drf-spectacular 0.30.0, psycopg 3.3.6, and django-environ 0.14.0 for the Python 3.14.4 environment and documented framework compatibility.
- Password reset completion uses the staff set-password endpoint with the same `uid`, token, and new password shape; the design specifies no separate finish-reset route (Stage 2).
- Invitation and reset hosts are built from `PLATFORM_URL_SCHEME` and `PLATFORM_BASE_DOMAIN` (defaults `https` and `edunova.com`) so the design's example domain is configurable (Stage 2).
- Invitation links target the workspace's `/teacher/set-password/` frontend route and carry `uid` and token as query parameters; the frontend submits them to the API (Stage 2).
- Staff auth throttle rates are 5 login attempts/minute, 3 password-reset starts/hour, and 5 set-password attempts/hour per client IP; the design requires throttling but does not specify rates (Stage 2).
- DRF throttling uses `SimpleRateThrottle.get_ident`; `DRF_NUM_PROXIES=0` ignores forwarded IP headers, and deployments set it to the known trusted proxy count. Email expiry is displayed as an upper-bound whole number of days so the text remains accurate for non-whole-day timeout values (Stage 2 hardening).

## 9. Deferred to later rounds

- Endpoints for course sections, lessons, and lesson assets (the design has none yet).
- Exam-taking endpoints and the rule that exam access needs an active enrollment.
- AI question generation, mistake analysis, and proctoring.
- Assistant permissions.
- React frontend and sub-domain deployment.
- Email verification, refunds, receipt retention, online payments.

## 10. How to run

From the repository root in PowerShell: `py -3.14 -m venv .venv`; `.\.venv\Scripts\Activate.ps1`; `python -m pip install -r backend\requirements.txt`; `Copy-Item backend\.env.example backend\.env`; `psql -U postgres -c "CREATE DATABASE educational_platform;"`; `Set-Location backend`; `python manage.py migrate`; `python manage.py createsuperuser`; `python manage.py runserver`.

Verify a stage: from `backend/` with the virtual environment active, run `python manage.py check`, `python manage.py makemigrations --check --dry-run`, `python manage.py spectacular --validate`, and `python manage.py test`.

## 11. Known problems

- Local development sets `DJANGO_SESSION_COOKIE_SECURE=False` in `backend/.env.example` for HTTP `runserver`; production must keep it `True`. If unset, the setting defaults to `True`.
- The `/teacher/set-password/` invitation/reset destination is a frontend route; this backend stage supplies the API but does not build the frontend page.
- Every later stage must add suspended-workspace checks to its permission classes. Suspension blocks later requests but does not revoke teacher sessions already issued.
- Password-reset responses have the same body for known and unknown emails, but response time can still reveal account existence because email is sent in the request; move reset email delivery to a background task later.

## 12. Production deployment checklist

Set these in the server's `backend/.env`; never copy `.env.example` as-is. Variable names come from `backend/.env.example`.

| Variable | Dev example | Production |
|---|---|---|
| `DJANGO_SECRET_KEY` | `replace-with-a-long-random-secret` | Generate a new long random secret. |
| `DJANGO_DEBUG` | `True` | `False` |
| `DJANGO_ENABLE_API_DOCS` | `True` | `False` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,testserver` | `.<domain>,<domain>`; the leading dot covers every teacher sub-domain. |
| `CSRF_TRUSTED_ORIGINS` | `https://*.edunova.com` | `https://*.<domain>` |
| `PLATFORM_BASE_DOMAIN`, `PLATFORM_URL_SCHEME` | `edunova.com`, `https` | Your real domain, `https`. |
| `DJANGO_SESSION_COOKIE_SECURE` | `False` for local HTTP | `True` |
| `DJANGO_ADMIN_PATH` | `platform-admin/` | Use a non-guessable path. |
| `DRF_NUM_PROXIES` | `0` | Set to `1` only when exactly one trusted proxy is in front of Django. |
| `EMAIL_BACKEND` | `.env.example` explicitly sets the console backend | Switch to `django.core.mail.backends.smtp.EmailBackend` or delete the line to use the non-debug SMTP default. Configure `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, and `DEFAULT_FROM_EMAIL`. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` | Local PostgreSQL values | Set real database connection details and credentials. |

Never set `SESSION_COOKIE_DOMAIN` (AGENTS.md section 7).

Not configurable from `.env` yet: run `DJANGO_DEBUG=False ... python manage.py check --deploy` with a production-like environment. It currently warns that `SECURE_SSL_REDIRECT` is not enabled, `SECURE_HSTS_SECONDS` is unset, and `CSRF_COOKIE_SECURE` is not enabled; record these as pre-deployment TODOs.

`backend/requirements.txt` has no WSGI server or static-file package; deployment needs `collectstatic` and a web server for `/static/`.
