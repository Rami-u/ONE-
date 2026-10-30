# memory.md - Project memory for the coding agent

**Read this file first, at the start of every session.** Map and current state of the project.
It is **not a copy of the design** and **not a log of everything done**: keep it short (about 200 lines at most) and rewrite entries instead of appending forever. Update at the end of every stage in the same commit as code. If this file and code disagree, the code is right.

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
| `docs/review-checklist.md` | Checklist for the human reviewer of a stage | Only if the prompt names it |
| `docs/open-questions.md` | Decisions the team has not made yet | Only if the prompt names it |
| `docs/deployment.md` | Production deployment checklist | Only when preparing a deployment |

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

- **Built this round:** Stages 1-5 working with tests; Stage 6 as models-only skeleton; the stage-8 branch adds the attempts API and manual exam content (topics, questions, exams, student exam list, `seed_demo_data`).
- **Not built, do not add:** frontend, deployment, AI generation, mistake analysis, proctoring, assistant permissions, email verification, online payments, refunds, endpoints for sections, lessons, and assets.
- **Placeholders:** `apps/ai/` and `apps/proctoring/` are empty (README only).

## 5. Status
Update the row of the stage you worked on. Statuses: `not started`, `in progress`, `done - awaiting review`, `merged`.

| Stage | Content | Status | Branch | Reviewer |
|---|---|---|---|---|
| 1 | Bootstrap, workspaces, accounts | merged (PR #1) | stage-1-fixes | - |
| 2 | Teacher onboarding, staff login | merged (PR #2; hardening PR #3) | stage-2-teacher-onboarding; stage-2-hardening | - |
| 3 | Public showcase, workspace settings | merged (PR #5) | stage-3-public-showcase | - |
| 4 | Student registration, login, approval | merged (PR #6) | stage-4-student-auth | - |
| 5 | Courses, enrollment, manual payments | merged (PR #8) | stage-5-courses-payments | - |
| 6 | Content and assessment skeleton | done - awaiting review | stage-6-skeleton | - |
| 8 | Attempts API, manual exam content without AI, seed command (stage number to be confirmed by the lead) | in progress (PR #10) | stage-8-proctoring-attempts | lead |

## 6. Repository map
Fill this in as apps are created. One row per app, kept to one line each.

| App | Responsibility | Key models | Endpoints (prefix `/api/v1/`) | Stage |
|---|---|---|---|---|
| workspaces | Tenant configuration and identity; admin workspace lifecycle | `Workspace` | Admin workspace list/detail/suspend/activate (`admin/workspaces/`) | 2 |
| accounts | Custom identity, teacher onboarding, staff and student auth, student review | `User` | Admin teacher management; staff/student auth; workspace students/review (`workspaces/{slug}/...`) | 2-4 |
| public | Safe teacher directory, profiles, branding, and teacher workspace settings | `Workspace` (uses `User` for teacher display name) | Public teacher directory/profile; workspace branding/public-profile/settings | 3 |
| courses | Workspace catalog and content skeleton | `Course`, `CourseSection`, `Lesson`, `LessonAsset` | Workspace courses list/create/retrieve/update (`workspaces/{slug}/courses/`); content has no endpoints | 5-6 |
| enrollments | Course enrollment lifecycle, price snapshots, and content access | `CourseEnrollment` | Course enroll, my enrollments (`workspaces/{slug}/courses/.../enroll/`, `enrollments/me/`) | 5 |
| payments | Manual payment claims, receipts, review, and enrollment activation | `PaymentSubmission` | Submit claim, list, view receipt, confirm, reject (`workspaces/{slug}/payments/`) | 5 |
| assessments | Question bank, topics, exams, attempts, and answers | `Topic`, `LessonTopic`, `Question`, `QuestionTopic`, `Exam`, `ExamQuestion`, `ExamAttempt`, `Answer` | `workspaces/{slug}/topics/`, `questions/` (+ approve, reject, archive), `exams/` (+ questions, publish, archive; student list), `exams/{id}/attempts/start/`, `attempts/{id}/` and `/submit/` | 6, 8 |
| ai | Empty registered app; AI teammate owns future generation and analysis contracts in README | None | None | 6 |
| proctoring | Empty registered app; AI teammate owns future signals/evidence contracts; events will reference `assessments.ExamAttempt` | None | None | 6 |

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
| Related-workspace validator | `backend/apps/workspaces/tenancy.py` | `validate_same_workspace(instance,*field_names)` rejects each mismatched FK with a field-keyed validation error |
| Content and assessment test helpers | `backend/apps/courses/tests/helpers.py`, `backend/apps/assessments/tests/helpers.py` | Reuse `create_section`, `create_lesson`, `create_lesson_asset`, `create_topic`, `create_question`, `create_exam`, `create_exam_attempt`, `create_answer` with existing account/course helpers |
| Question content validation, exam services, demo seed | `backend/apps/assessments/question_validation.py`, `question_services.py`, `exam_services.py`, `seed_data/`, `management/commands/seed_demo_data.py` | One validator for `options` and `correct_answer`; services lock rows and run in one transaction; the seed reuses them and is dev-only and idempotent |

## 8. Decisions the design did not cover
One line each: what you decided, why, and the stage. The reviewer checks this list.

- Workspace slugs use 3-63 lowercase letters/digits joined by single hyphens; additionally reserve `auth`, `accounts`, `dashboard`, `billing`, `docs`, `help`, `cdn`, `assets`, and `files` to keep common service subdomains unavailable to workspaces (Stage 1).
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
- Receipt file storage strips client filenames to <uuid4 hex>.<ext> based on detected content type, and authorized receipt retrieval serves them via FileResponse with nosniff, fixed MIME types (pdf, jpg, jpeg, png inline; fallback application/octet-stream), and private no-store Cache-Control (Stage 5).
- Receipt validator restricts image decoding to formats=["JPEG", "PNG"], enforces MAX_RECEIPT_PIXELS=25M, and catches all Pillow exceptions to return 400 instead of 500 for corrupt files (Stage 5 repair).
- PaymentSubmissionAdmin displays read-only boolean has_receipt and excludes receipt_image so the Django admin change page does not crash on private file fields (Stage 5 repair).
- CourseQuerysetMixin defines both get_queryset and get_permissions (POST/PATCH requires IsWorkspaceTeacher; GET allows IsWorkspaceTeacherOrApprovedStudent) to centralize course access rules in one place (Stage 5 repair).
- Non-teacher attempts to create or update courses return DRF's standard 403 permission denied message rather than a custom response to adhere to project error response patterns (Stage 5 repair).
- Course enrollment and payment claim submission handle concurrent race conditions by locking rows and catching database IntegrityError inside savepoints to return 200/409 instead of 500 (Stage 5 repair).
- HasActiveEnrollment fails closed by returning False when a student's course_id cannot be resolved and removes the pk fallback so unassociated requests cannot bypass content authorization (Stage 5 repair).
- The ai/proctoring README placeholders were added during Stage 5, ahead of Stage 6, which will replace them, to keep the repository layout consistent with scope rules (Stage 5).
- Course price is required on create in CourseCreateUpdateSerializer without a serializer default so teachers make an explicit pricing decision on creation (Stage 5 repair).
- Payment claim note and payment rejection reason enforce a 1000-character limit to prevent unbounded text storage while leaving ample room for user input (Stage 5 repair).
- Invalid status query parameters on GET /payments/ return 400 Bad Request matching GET /students/ to keep staff review endpoint filters consistent (Stage 5 repair).
- Storage location is resolved lazily and tests use TemporaryMediaMixin to prevent test uploads from polluting backend/private_media (Stage 5 repair).
- apps/payments/permissions.py was created in Batch 1 outside that item's scope and reshaped into IsReceiptTeacherOrOwner in this batch (one permission class per rule, no inline duplicate) (Stage 5 repair).
- Receipt endpoint OpenAPI 200 response documents binary schemas across application/pdf, image/png, and image/jpeg removing inaccurate application/json defaults (Stage 5 repair).
- Stage 6 (a): Use `CourseSection`, `Lesson`, `LessonAsset`, `Topic`, `LessonTopic`, `Question`, `QuestionTopic`, `Exam`, `ExamQuestion`, `ExamAttempt`, `Answer` with section 5 table names and nested `TextChoices` (`Status`, `SourceType`, `QuestionType`, `Difficulty`, `AssetType`, `ExtractionStatus`, `ReviewStatus`) to match existing model conventions.
- Stage 6 (b): All new FKs use `PROTECT` to preserve rows; reverse names equal the owning table except `Question.reviewed_by=reviewed_questions` and `ExamAttempt.reviewed_by=reviewed_exam_attempts`, avoiding clashes between two User FKs.
- Stage 6 (c): Defaults are Question source_type=manual/status=draft/difficulty=medium, Exam status=draft, ExamAttempt status=in_progress/proctoring_review_status=clean, LessonAsset extraction_status=pending; Question points/question_type have no default to require explicit values. `created_at` uses `auto_now_add`; editable attempt `started_at` and answer `answered_at` use `timezone.now`. `correct_answer`, `options`, `selected_option` use JSONField for structured data; Topic.slug uses SlugField(150) for stable keys.
- Stage 6 (d): `full_clean()` enforces non-negative points/points_override/score/max_score/points_awarded, max_attempts >= 1, and optional duration_minutes >= 1; validators only, no additional CheckConstraints, as requested for this skeleton.
- Stage 6 (e): Meta.ordering is `["position", "id"]` for sections/lessons, `["-created_at", "id"]` for questions/exams, `["-started_at", "id"]` for attempts, and `["id"]` for every other new model, giving stable lists.
- Stage 6 (f): Named UniqueConstraints enforce workspace/slug topics, lesson/topic, question/topic, exam/question, and attempt/question pairs; additionally exam/student/attempt_number is unique so the later quiz engine cannot duplicate an attempt number.
- Stage 6 (g): Every new model with non-workspace FKs calls the shared validator for all of them, including student/reviewer; Lesson.section, Exam.lesson, and Question.lesson (when both scopes exist) must match the course, and attempt users must have student role. Validation stays in `clean()` without overriding `save()`, preserving explicit validation and scoped-query responsibilities.
- Stage 6 (h): Admin lists keep id, title/name or identifying relations, workspace, and status where present, with workspace/status filters and search fields; extracted_text stays out of list views to keep review screens concise.
- Stage 8: `passing_score` is a percentage from 0 to 100; manual questions are created `approved` (the client may send `draft`); there are no DELETE endpoints (archive only); `question_type` and `status` on a question and `course` on an exam cannot be changed by PATCH (400).
- Stage 8: once an exam is published and has attempts, duration, passing score, proctoring flag and question list return 409; `max_attempts` can only increase; `lesson` is locked after publishing; archived exams are read-only. A question used by an exam with attempts has frozen content.
- Stage 8: students see only published exams in courses with an active enrollment, never questions or `passing_score`; an unavailable exam returns 404. Files are named `question_*` and `exam_*` instead of the suggested `content_*`.
- Stage 8: `seed_demo_data` runs only with `DEBUG=True`, reads the password from `--password` or `DEMO_USER_PASSWORD`, never prints it, and skips rows that already exist.

## 9. Deferred to later rounds

- Endpoints for course sections, lessons, and lesson assets (the design has none yet).
- Delivering questions during an attempt, saving answers, and grading (starting an attempt already needs an active enrollment).
- AI question generation, mistake analysis, and proctoring.
- Assistant permissions.
- React frontend and sub-domain deployment.
- Email verification, refunds, receipt retention, online payments.

## 10. How to run
From the repository root in PowerShell: `py -3.14 -m venv .venv`; `.\.venv\Scripts\Activate.ps1`; `python -m pip install -r backend\requirements.txt`; `Copy-Item backend\.env.example backend\.env`; `psql -U postgres -c "CREATE DATABASE educational_platform;"`; `Set-Location backend`; `python manage.py migrate`; `python manage.py createsuperuser`; `python manage.py runserver`.

Verify a stage: from `backend/` with virtualenv active, run `python manage.py check`, `python manage.py makemigrations --check --dry-run`, `python manage.py spectacular --validate`, and `python manage.py test`.
Stage 3 verification: 49 tests passed. Stage 4 verification: 97 tests passed.
Stage 5 verification from `backend/`: `python manage.py check`; `python manage.py makemigrations --check --dry-run`; `python manage.py spectacular --validate` (no warnings); `python manage.py test` (231 tests passed).
Stage 6 verification (Python 3.14.4), from `backend/`: `python manage.py migrate --noinput`; `python manage.py check`; `python manage.py makemigrations --check --dry-run`; `python manage.py spectacular --validate --fail-on-warn` (no warnings); `python manage.py test --noinput --parallel 4` (346 passed; 231 before). Schema/docs GET 200; 22 source and 6 DB mutations caught/restored; private_media files 121 before/121 after, public_media 1 before/1 after; ai/proctoring have no migrations.
Stage 8 verification, from `backend/` on commit e7af32f: `check`, `makemigrations --check --dry-run`, `spectacular --validate --fail-on-warn` clean; `python manage.py test --noinput --parallel 4` (573 passed; no migrations added).

## 11. Known problems

- Local development sets `DJANGO_SESSION_COOKIE_SECURE=False` in `backend/.env.example` for HTTP `runserver`; production must keep it `True`. If unset, the setting defaults to `True`.
- The `/teacher/set-password/` invitation/reset destination is a frontend route; this backend stage supplies the API but does not build the frontend page.
- Stage 5 and later permissions must check workspace status. Suspension blocks later requests but does not revoke sessions already issued.
- Password-reset responses have the same body for known and unknown emails, but response time can still reveal account existence because email is sent in the request; move reset email delivery to a background task later.
- Development serves logos only when `DEBUG=True`; production needs a web server mapping `/media/` to `backend/public_media`.
- Replacing a workspace logo does not delete the old file, so orphan logo files accumulate; this is known and not fixed here.
- Old receipt files stay on disk after a rejected claim is resubmitted.
- A claim submission that loses a race on the unique constraint can leave an unreferenced receipt file on disk.
- The PDF check is signature-only.
- The JPEG check validates only the header (Pillow verify() does nothing for JPEG), so a truncated JPEG with a valid header is accepted.
- apps/workspaces/image_validators.py (Stage 3) catches only (UnidentifiedImageError, OSError, ValueError), but corrupt uploads (such as PNG without IDAT or minimal DDS) on the logo endpoint return 400 because DRF's ImageField parser catches them first; Stage 3 is not being retroactively modified because its branch is merged.
- Unpublishing a course does not change existing enrollments and enrollments/me still lists them.
- `MEDIA_URL="/media/"` while `MEDIA_ROOT` remains `backend/private_media`; only `backend/public_media` is served. Stage 5 receipts must use their own private storage and the authorized endpoint, never `.url` or `MEDIA_URL`.
- Throttle counters are per-process until a shared cache is configured (see docs/deployment.md).
- Stage 6 `clean()` runs in Django admin and `full_clean()`, not `objects.create()` or `save()`; future serializers must scope relation querysets (AGENTS.md section 6, pattern 2).
- LessonAsset has no storage yet: storage_key is a plain CharField(500), with no upload, extraction, or serving implementation. Section 4's README-only placeholder wording is preserved as requested; the registered empty app packages are documented in section 6.
- Receipt tests need write access to the system temporary directory; a restricted run raised PermissionError, while the final full suite passed with normal temporary-file access. No application change was needed.
- Stage 8: a null `duration_minutes` means 180 minutes (`DEFAULT_DURATION_MINUTES`), consent is validated but not stored, and expired in-progress attempts stay `in_progress` until someone calls start; these are open questions for the lead.

## 12. Production deployment checklist

See docs/deployment.md.