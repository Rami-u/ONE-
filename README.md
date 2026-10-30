# Educational Platform Backend

The backend is a Django, Django REST Framework, and PostgreSQL project. Stages 1–5 provide workspace accounts, courses, enrollments, and manual payments. Stage 6 adds content and assessment models, constraints, migrations, admin pages, and tests.

## App layout and ownership

Apps live under `backend/apps/`; project settings live under `backend/config/`.

| App | Tables and responsibility |
|---|---|
| `workspaces` | `workspaces`; tenant configuration and shared workspace validation |
| `accounts` | `users`; staff/student authentication and approval |
| `public` | Safe public profiles and branding using workspace/account/course tables |
| `courses` | `courses`, `course_sections`, `lessons`, `lesson_assets`; catalog and content skeleton |
| `enrollments` | `course_enrollments`; course access and price snapshots |
| `payments` | `payment_submissions`; manual claims, receipts, and review |
| `assessments` | `topics`, `lesson_topics`, `questions`, `question_topics`, `exams`, `exam_questions`, `exam_attempts`, `answers`; assessment skeleton |
| `ai` | Empty registered app owned by the AI teammate; deferred table contracts in its README |
| `proctoring` | Empty registered app owned by the AI teammate; deferred event/evidence contracts in its README |

Stage 6 has no endpoints and no uploads. `LessonAsset.storage_key` is a plain string; asset storage, extraction, and access are deferred. AI and proctoring have no models or migrations. Future proctoring events will reference `exam_attempts` in `assessments`.

Model `clean()` validates related workspaces, content/course consistency, and the student role on attempts. It runs through Django admin forms and `full_clean()`, but not `objects.create()` or `save()`. Future serializers must retrieve relations from querysets scoped to the current workspace.

When adding an authorized feature, implement its model, explicit serializer, permission, view, tests, and schema together; update `memory.md` with the verified behavior and reusable pieces. Follow the stage scope and design before adding endpoints to these skeleton tables.

## Stage 6 mutation verification

Final verification: 346 tests passed on fresh PostgreSQL test databases (231 before Stage 6). System and migration checks passed, schema validation had no warnings, and both `/api/schema/` and `/api/docs/` returned 200. Media file counts stayed unchanged: private_media 121 before/121 after; public_media 1 before/1 after. AI and proctoring have no migrations. `memory.md` grew from 183 to 200 lines and records all supplied decisions (a–h) in section 8.

All 22 source mutations caused the expected test failures; each file was restored byte for byte before the next mutation. Every FK assertion was run separately (21 workspace assertions across 11 models). The six database constraints were also dropped individually within rolled-back test transactions: all six duplicate tests failed with `IntegrityError not raised`. Generated migrations were never edited. The table names one failing test per source mutation; multi-FK mutations failed every corresponding isolated test.

| Rule | Temporary mutation | Failing test |
|---|---|---|
| CourseSection workspace | Remove shared-validator call | `test_section_rejects_a_course_from_another_workspace` |
| Lesson workspace | Remove shared-validator call | `test_lesson_rejects_a_course_from_another_workspace` |
| LessonAsset workspace | Remove shared-validator call | `test_asset_rejects_a_lesson_from_another_workspace` |
| Topic workspace | Remove shared-validator call | `test_topic_rejects_cross_workspace_course` |
| LessonTopic workspace | Remove shared-validator call | `test_lesson_topic_rejects_cross_workspace_topic` |
| Question workspace | Remove shared-validator call | `test_question_rejects_cross_workspace_reviewer` |
| QuestionTopic workspace | Remove shared-validator call | `test_question_topic_rejects_cross_workspace_topic` |
| Exam workspace | Remove shared-validator call | `test_exam_rejects_cross_workspace_lesson` |
| ExamQuestion workspace | Remove shared-validator call | `test_exam_question_rejects_cross_workspace_question` |
| ExamAttempt workspace | Remove shared-validator call | `test_exam_attempt_rejects_cross_workspace_student` |
| Answer workspace | Remove shared-validator call | `test_answer_rejects_cross_workspace_attempt` |
| Lesson section/course | Remove consistency check | `test_lesson_rejects_a_section_in_another_course_of_the_same_workspace` |
| Question lesson/course | Remove consistency check | `test_question_rejects_lesson_from_another_course` |
| Exam lesson/course | Remove consistency check | `test_exam_rejects_lesson_from_another_course` |
| Attempt student role | Remove role check | `test_exam_attempt_rejects_non_student` |
| Topic workspace/slug uniqueness | Remove UniqueConstraint; separately drop DB constraint | `test_topic_slug_is_unique_within_workspace` |
| Lesson/topic uniqueness | Remove UniqueConstraint; separately drop DB constraint | `test_lesson_topic_pair_is_unique` |
| Question/topic uniqueness | Remove UniqueConstraint; separately drop DB constraint | `test_question_topic_pair_is_unique` |
| Exam/question uniqueness | Remove UniqueConstraint; separately drop DB constraint | `test_exam_question_pair_is_unique` |
| Exam/student/attempt-number uniqueness | Remove UniqueConstraint; separately drop DB constraint | `test_exam_attempt_number_is_unique_per_student_and_exam` |
| Attempt/question uniqueness | Remove UniqueConstraint; separately drop DB constraint | `test_answer_question_is_unique_per_attempt` |
| Question origin default | Change manual to ai_generated | `test_question_defaults_choices_and_field_types` |

Content tests live in `backend/apps/courses/tests/test_content_models.py`; question-bank and exam tests live in `backend/apps/assessments/tests/test_question_models.py` and `test_exam_models.py`.

Review `docs/backend-design.md`: Build Scope; section 1 AI policy; sections 5.4 and 5.7–5.23 (deferred AI/proctoring tables are contracts only); section 6; section 12 rules 24–25; section 14 Stage 6. No additional product decisions or unresolved design questions were needed.

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
python manage.py spectacular --validate
python manage.py test --noinput --parallel 4
```

Django's test runner creates and removes temporary PostgreSQL test databases; `--parallel 4` uses Django's built-in runner with four workers. The PostgreSQL role must be allowed to create databases. Receipt fixtures also need write access to the system temporary directory; use a session that permits temporary-file creation.

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

## Seeding demo data (development only)

`seed_demo_data` fills a development database with a demo chemistry workspace so the exam content API can be tried by hand. It runs only when `DEBUG` is true and refuses to run otherwise. It does not touch proctoring or AI tables.

Run it from `backend` with the virtual environment active:

```powershell
python manage.py seed_demo_data --password "choose-a-demo-password"
```

You can also set the password in the `DEMO_USER_PASSWORD` environment variable instead of passing `--password`. The password is never printed.

| Option | Default | Meaning |
|---|---|---|
| `--password` | none | Password for the demo teacher and students |
| `--workspace-slug` | `demo-chem` | Slug of the demo workspace |
| `--students` | `5` | Number of demo students |

The command creates:

- Workspace `demo-chem` ("Demo Chemistry", active).
- Teacher `teacher@demo.local` and approved students `student1@demo.local`, `student2@demo.local`, and so on, each with an active enrollment in the course.
- A published course, "Organic Chemistry 101", with sections, lessons, topics, and 24 approved questions.
- Three exams:

| Exam | Duration | Max attempts | Proctoring | State |
|---|---|---|---|---|
| Quiz 1: Alkanes and Alkenes | 20 min | 2 | off | published |
| Midterm: Aromatic compounds | 30 min | 1 | on | published (passing score 60) |
| Draft exam | 15 min | 1 | off | draft, so publishing can be tested by hand |

The command is idempotent: running it again reuses existing records and skips an exam that already exists without changing it. It prints a summary of the emails and exams when it finishes.

### Trying it by hand

1. Sign in as a student at `POST /api/v1/workspaces/demo-chem/auth/login/`, or as the teacher at `POST /api/v1/workspaces/demo-chem/staff/auth/login/`. Session `POST` requests also need the CSRF token (see "Trying session endpoints by hand" below).
2. List exams with `GET /api/v1/workspaces/demo-chem/exams/`. Students see only published exams; the teacher also sees the draft.
3. Start an attempt with `POST /api/v1/workspaces/demo-chem/exams/<id>/attempts/start/`. For Quiz 1 the body is `{}`. The Midterm has proctoring enabled, so its body must be `{"consent": true}`.
4. As the teacher, publish the draft with `POST /api/v1/workspaces/demo-chem/exams/<id>/publish/`.

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

## Stage 5 courses, enrollment, and manual payments

- `GET /api/v1/workspaces/{slug}/courses/` lists courses. Approved students see only published courses with their own `enrollment_status`; teachers see all courses.
- `POST /api/v1/workspaces/{slug}/courses/` creates a course (workspace teacher only). Course `price` is required on creation (`"0"` or `"0.00"` for free; at most 8 digits before decimal and 2 decimal places, up to `"99999999.99"`). `PATCH` without price remains valid. The workspace is set from the URL slug.
- `GET /api/v1/workspaces/{slug}/courses/{id}/` retrieves a course (teachers see any; students see only published courses in their workspace).
- `PATCH /api/v1/workspaces/{slug}/courses/{id}/` updates a course (teacher only).
- `POST /api/v1/workspaces/{slug}/courses/{id}/enroll/` enrolls an approved student. Free courses become `active` immediately; paid courses become `pending_payment`. Enrolling twice returns the existing enrollment. Response includes `payment_instructions`.
- `GET /api/v1/workspaces/{slug}/enrollments/me/` returns the student's enrollments and statuses.
- `POST /api/v1/workspaces/{slug}/enrollments/{id}/payments/` submits a manual payment claim (multipart, optional receipt; `note` limited to 1000 characters; amount copied from `price_at_enrollment`, never from the client). Only one `submitted` claim allowed per enrollment; resubmission allowed after rejection.
- `GET /api/v1/workspaces/{slug}/payments/` lists payments for the workspace teacher (filterable by `?status=submitted|confirmed|rejected`; invalid status returns 400 with `{"status": ["Select a valid choice."]}`).
- `GET /api/v1/workspaces/{slug}/payments/{id}/receipt/` serves private payment receipts only to the workspace teacher or owning student via `FileResponse` with strict binary `Content-Type` headers (`application/pdf`, `image/png`, or `image/jpeg`), `X-Content-Type-Options: nosniff`, and private `Cache-Control`.
- `POST /api/v1/workspaces/{slug}/payments/{id}/confirm/` confirms a submitted claim and activates the enrollment in the same transaction.
- `POST /api/v1/workspaces/{slug}/payments/{id}/reject/` rejects a claim with a non-blank, stripped reason up to 1000 characters; enrollment stays `pending_payment`.
- Receipts are validated for type (JPEG, PNG, PDF) and size (at most 5 MB), stored privately in `backend/private_media/receipts`, and never served through a public URL. In tests, media storage is isolated using `TemporaryMediaMixin`.
- Public showcases (`GET /api/v1/public/teachers/{slug}/` and `GET /api/v1/workspaces/{slug}/public-profile/`) now return real published courses.

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
