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
| 3 | Public showcase, workspace settings | merged (PR #5) | stage-3-public-showcase | - |
| 4 | Student registration, login, approval | done - awaiting review | stage-4-student-auth | - |
| 5 | Courses, enrollment, manual payments | done - awaiting review | stage-5-courses-payments | - |
| 6 | Content and assessment skeleton | not started | - | - |

## 6. Repository map

Fill this in as apps are created. One row per app, kept to one line each.

| App | Responsibility | Key models | Endpoints (prefix `/api/v1/`) | Stage |
|---|---|---|---|---|
| workspaces | Tenant configuration and identity; admin workspace lifecycle | `Workspace` | Admin workspace list/detail/suspend/activate (`admin/workspaces/`) | 2 |
| accounts | Custom identity, teacher onboarding, staff and student auth, student review | `User` | Admin teacher management; staff/student auth; workspace students/review (`workspaces/{slug}/...`) | 2–4 |
| public | Safe teacher directory, profiles, branding, and teacher workspace settings | `Workspace` (uses `User` for teacher display name) | Public teacher directory/profile; workspace branding/public-profile/settings | 3 |
| courses | Workspace course catalog, teacher course authoring, student list | `Course` | Workspace courses list/create/retrieve/update (`workspaces/{slug}/courses/`) | 5 |
| enrollments | Course enrollment lifecycle, price snapshots, and content access | `CourseEnrollment` | Course enroll, my enrollments (`workspaces/{slug}/courses/.../enroll/`, `enrollments/me/`) | 5 |
| payments | Manual payment claims, receipts, review, and enrollment activation | `PaymentSubmission` | Submit claim, list, view receipt, confirm, reject (`workspaces/{slug}/payments/`) | 5 |

## 7. Reusable building blocks

The patterns the team will copy. Record where each one lives so nobody rewrites it.

| Name | Location | Use it for |
|---|---|---|
| Workspace slug validator | `backend/apps/workspaces/validators.py` | Enforce normalized slug syntax and reserved names |
| Workspace slug immutability | `backend/apps/workspaces/models.py` | Reject slug changes after creation |
| User manager and login key derivation | `backend/apps/accounts/managers.py`, `backend/apps/accounts/models.py` | Create workspace accounts and Platform Admins; derive normalized login keys |
| Teacher/workspace onboarding transaction and invitation mail | `backend/apps/accounts/services.py` | Atomically create teacher/workspace; send invitation after commit; resend/reset password links |
| Platform Admin, teacher, approved-student, and workspace-member permissions | `backend/apps/accounts/permissions.py` | Check role, approval state, workspace ownership, and active workspace status |
| Workspace slug resolvers | `backend/apps/accounts/permissions.py` | `ActiveWorkspaceSlugMixin` keeps the Stage 2 suspended message; `WorkspaceSlugMixin` uses `Workspace is unavailable.` for public and Stage 4 routes |
| Staff password token and API routes | `backend/apps/accounts/tokens.py`, `backend/apps/accounts/urls.py`, `backend/apps/accounts/views.py` | Expiring, single-use password tokens; teacher login and password setup/reset |
| Shared login-key construction | `backend/apps/accounts/identity.py` | Build a normalized workspace-scoped login key consistently in model saves and staff login |
| Client-IP throttling | `backend/apps/accounts/views.py`, `backend/apps/accounts/student_views.py`, `backend/config/settings.py`, `backend/.env.example` | Reuse `ClientIPRateThrottle` for staff and student auth; set trusted proxy count with `DRF_NUM_PROXIES` (default 0) |
| Environment-driven email delivery, token expiry, and safe email error helpers | `backend/config/settings.py`, `backend/apps/accounts/services.py`, `backend/.env.example` | Configure console/SMTP delivery and `PASSWORD_RESET_TIMEOUT_SECONDS` (default 259200); `safe_email_exception_message` redacts links, tokens, and passwords from email errors, and `password_reset_expiry_sentence` provides shared expiry wording for future email flows. New emails must reuse these helpers instead of copying them. |
| Workspace teacher/student role permissions | `backend/apps/accounts/permissions.py` | `IsWorkspaceTeacher`, `IsApprovedStudent`, and `IsWorkspaceMember` enforce active workspace and tenant membership |
| Student auth serializers and views | `backend/apps/accounts/student_serializers.py`, `backend/apps/accounts/student_views.py` | Safe registration, login, session, CSRF, `me`, and password reset API contracts |
| Student review service and endpoints | `backend/apps/accounts/services.py`, `backend/apps/accounts/student_review_views.py` | Lock and scope a pending student, record reviewer and time, and notify after commit |
| Account test helpers and Stage 4 coverage | `backend/apps/accounts/tests/helpers.py`, `backend/apps/accounts/tests/test_student_*.py` | Create workspace accounts; cover student auth, isolation, permissions, throttling, review, and schemas |
| Safe public response serializers and logo validation/storage | `backend/apps/public/serializers.py`, `backend/apps/workspaces/image_validators.py`, `backend/apps/workspaces/storage.py` | Restrict showcase fields; validate public JPEG/PNG/WebP logos and store uploads separately from private media |
| Public showcase endpoint tests | `backend/apps/public/tests/test_public_api.py` | Cover visibility, search, pagination, safe fields, workspace scoping, settings, and logo validation |
| Active enrollment permission | `backend/apps/enrollments/permissions.py` | `HasActiveEnrollment` verifies active student course enrollment before granting course content access |
| Course catalog permission | `backend/apps/courses/permissions.py` | `IsWorkspaceTeacherOrApprovedStudent` allows approved teachers and students to view catalog |
| Course enrollment and payment services | `backend/apps/enrollments/services.py`, `backend/apps/payments/services.py` | Idempotent student course enrollment; atomic payment claim submission, review, and enrollment activation |
| Receipt access permission | `backend/apps/payments/permissions.py` | `IsReceiptTeacherOrOwner` checks active workspace, teacher role or owning student for receipts |
| Private receipt storage and file validator | `backend/apps/payments/storage.py`, `backend/apps/payments/validators.py` | Store receipts privately with no public URL; validate JPEG/PNG/PDF files up to 5 MB |
| Temporary media test mixin | `backend/apps/payments/tests/helpers.py` | `TemporaryMediaMixin` isolates media uploads to a clean temporary directory during test runs |
| Course, enrollment, payment test helpers | `backend/apps/courses/tests/helpers.py`, `backend/apps/enrollments/tests/helpers.py`, `backend/apps/payments/tests/helpers.py` | Create courses, enrollments, and payment submissions for test suites |

## 8. Decisions the design did not cover

One line each: what you decided, why, and the stage. The reviewer checks this list.

- Workspace slugs use 3–63 lowercase letters/digits joined by single hyphens; additionally reserve `auth`, `accounts`, `dashboard`, `billing`, `docs`, `help`, `cdn`, `assets`, and `files` to keep common service subdomains unavailable to workspaces (Stage 1).
- Stage 1 stored workspace logos as nullable URL references; Stage 3 changes the field to `ImageField` and stores new uploads in a separate public media directory as requested.
- New accounts default to pending approval; the user manager marks teacher, assistant, and Platform Admin accounts approved on creation.
- Exact dependencies are pinned to Django 6.0.8, DRF 3.17.2, drf-spectacular 0.30.0, psycopg 3.3.6, and django-environ 0.14.0 for the Python 3.14.4 environment and documented framework compatibility.
- Password reset completion uses the staff set-password endpoint with the same `uid`, token, and new password shape; the design specifies no separate finish-reset route (Stage 2).
- Invitation and reset hosts are built from `PLATFORM_URL_SCHEME` and `PLATFORM_BASE_DOMAIN` (defaults `https` and `edunova.com`) so the design's example domain is configurable (Stage 2).
- Invitation links target the workspace's `/teacher/set-password/` frontend route and carry `uid` and token as query parameters; the frontend submits them to the API (Stage 2).
- Staff auth throttle rates are 5 login attempts/minute, 3 password-reset starts/hour, and 5 set-password attempts/hour per client IP; the design requires throttling but does not specify rates (Stage 2).
- DRF throttling uses `SimpleRateThrottle.get_ident`; `DRF_NUM_PROXIES=0` ignores forwarded IP headers, and deployments set it to the known trusted proxy count. Email expiry is displayed as an upper-bound whole number of days so the text remains accurate for non-whole-day timeout values (Stage 2 hardening).
- `Pillow==12.3.0` is pinned for Stage 3 image validation and supports the project's Python 3.14 environment.
- Logo uploads use `backend/public_media` with `/media/` routing enabled only in development; `PublicLogoStorage.url()` returns legacy absolute logo URLs unchanged so existing Stage 2 references remain readable.
- Suspended branding, public-profile, and workspace settings requests return 403 with `Workspace is unavailable.`; unknown workspace slugs return 404 so the frontend can distinguish unavailable workspaces from missing ones. Logo PATCH requests use multipart form data for file uploads.
- `COMPONENT_SPLIT_REQUEST=True` in `SPECTACULAR_SETTINGS` separates multipart logo upload schemas from JSON request schemas for accurate API documentation (Stage 3).
- Student reset email subject is `Reset your student password`; its body says `Use this link to set or reset your password. It expires within N day(s):` followed by the `/reset-password/` URL, reusing Stage 2 expiry wording. Start response is `If the account exists, a reset link has been sent.`; confirmation reuses the staff details `Password has been set.` and `Invalid or expired password link.` (Stage 4).
- Approval mail subject/body are `Your student account was approved` and `Your account for {workspace} has been approved. You can now sign in.` Rejection mail uses `Your student account was rejected` and `Your account for {workspace} was rejected. Reason: {reason}` (Stage 4; exact copy was unspecified).
- Duplicate student registration returns a field error on `email` with a workspace-specific duplicate message; the design specifies rejection and status but not the response wording (Stage 4).
- Rejected student login uses the message `Your account was rejected.` and returns the saved `rejection_reason`; the design requires the state and reason but leaves the message text open (Stage 4).
- Student auth serializers use the requested names `email`, `password`, `full_name`, and the safe `me` fields; review serializers use the listed student fields exactly, with no privileged additions (Stage 4).
- phone is optional at registration; design 5.2 defines the field, 8.1 does not show it (Stage 4).
- Swagger UI uses drf-spectacular's documented string-valued `SWAGGER_UI_SETTINGS` to add `X-CSRFToken` from the same-host cookie for unsafe requests (Stage 4).
- The Swagger UI request interceptor guards `request.method` because it also runs for the schema request; without the guard `/api/docs/` failed to load in the browser (Stage 4, commit d2bc620).
- `ENUM_NAME_OVERRIDES` in `SPECTACULAR_SETTINGS` resolves OpenAPI enum naming collisions for `status` across Workspace, CourseEnrollment, and PaymentSubmission without warnings (Stage 5).
- In-progress payment claims return 409 Conflict when submitting a second claim for the same enrollment or when reviewing an already-reviewed claim; the design specifies state verification but leaves the HTTP error code open (Stage 5).
- Course enrollment endpoint returns 201 Created on initial enrollment and 200 OK on duplicate enrollment with existing enrollment details (Stage 5).
- Authorized receipt retrieval stores uploaded files as <uuid4 hex>.<ext> and serves them via FileResponse with Content-Type mapped from the stored extension (pdf, jpg, jpeg, png inline; fallback application/octet-stream attachment), nosniff, and private, no-store Cache-Control (Stage 5).
- Receipt file storage strips client filenames to <uuid4 hex>.<ext> based on content detection and serves fixed MIME types to prevent content spoofing and path traversal (Stage 5 repair).
- Receipt validation catches Pillow SyntaxError, EOFError, DecompressionBombError, and enforces MAX_RECEIPT_PIXELS=25M before verify() so malicious/corrupt images return 400 instead of 500 (Stage 5 repair).
- Course enrollment and payment claim submission handle concurrent race conditions by locking rows and catching database IntegrityError inside savepoints to return 200/409 instead of 500 (Stage 5 repair).
- HasActiveEnrollment fails closed by returning False when a student's course_id cannot be resolved and removes the pk fallback so unassociated requests cannot bypass content authorization (Stage 5 repair).
- The ai/proctoring README placeholders were added during Stage 5, ahead of Stage 6, which will replace them, to keep the repository layout consistent with scope rules (Stage 5).
- Course price is required on create in CourseCreateUpdateSerializer without a serializer default so teachers make an explicit pricing decision on creation (Stage 5 repair).
- Payment claim note and payment rejection reason enforce a 1000-character limit to prevent unbounded text storage while leaving ample room for user input (Stage 5 repair).
- Invalid status query parameters on GET /payments/ return 400 Bad Request matching GET /students/ to keep staff review endpoint filters consistent (Stage 5 repair).
- Storage location is resolved lazily and tests use TemporaryMediaMixin to prevent test uploads from polluting backend/private_media (Stage 5 repair).
- apps/payments/permissions.py was created in Batch 1 outside that item's scope and reshaped into IsReceiptTeacherOrOwner in this batch (one permission class per rule, no inline duplicate) (Stage 5 repair).
- Receipt endpoint OpenAPI 200 response documents binary schemas across application/pdf, image/png, and image/jpeg removing inaccurate application/json defaults (Stage 5 repair).

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

Stage 3 verification from `backend/`: `python manage.py check`; `python manage.py makemigrations --check --dry-run`; `python manage.py spectacular --validate`; `python manage.py test` (49 tests passed).

Stage 4 verification from `backend/`: `python manage.py check`; `python manage.py makemigrations --check --dry-run`; `python manage.py spectacular --validate` (no warnings); `python manage.py test` (97 tests passed).

Stage 5 verification from `backend/`: `python manage.py check`; `python manage.py makemigrations --check --dry-run`; `python manage.py spectacular --validate` (no warnings); `python manage.py test` (223 tests passed).

## 11. Known problems

- Local development sets `DJANGO_SESSION_COOKIE_SECURE=False` in `backend/.env.example` for HTTP `runserver`; production must keep it `True`. If unset, the setting defaults to `True`.
- The `/teacher/set-password/` invitation/reset destination is a frontend route; this backend stage supplies the API but does not build the frontend page.
- Stage 5 and later permissions must check workspace status. Suspension blocks later requests but does not revoke sessions already issued.
- Password-reset responses have the same body for known and unknown emails, but response time can still reveal account existence because email is sent in the request; move reset email delivery to a background task later.
- Development serves logos only when `DEBUG=True`; production needs a web server mapping `/media/` to `backend/public_media`.
- Replacing a workspace logo does not delete the old file, so orphan logo files accumulate; this is known and not fixed here.
- `MEDIA_URL="/media/"` while `MEDIA_ROOT` remains `backend/private_media`; only `backend/public_media` is served. Stage 5 receipts must use their own private storage and the authorized endpoint, never `.url` or `MEDIA_URL`.
- Throttle counters are per-process until a shared cache is configured (see section 12).
- Old receipt files stay on disk after a rejected claim is resubmitted.
- A claim submission that loses a race on the unique constraint can leave an unreferenced receipt file on disk.
- The PDF check is signature-only.
- The JPEG check validates only the header (Pillow verify() does nothing for JPEG), so a truncated JPEG with a valid header is accepted.
- apps/workspaces/image_validators.py (Stage 3) has the same unhandled Pillow exceptions and was not changed.
- Unpublishing a course does not change existing enrollments and enrollments/me still lists them.

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

Shared cache for throttling (pre-deployment TODO): the default cache is per process, so throttle limits multiply by the number of workers. The recommended fix is Django `DatabaseCache` with `python manage.py createcachetable`; Redis is an alternative and needs approval to add a dependency. A reverse-proxy limit on login routes complements DRF throttling but does not replace it; `DRF_NUM_PROXIES` must also be correct. See README's “Production: shared cache for throttling” subsection.

`backend/requirements.txt` has no WSGI server or static-file package; deployment needs `collectstatic` and a web server for `/static/`.

Map `/media/` to `backend/public_media` in the production web server.
