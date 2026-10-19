# AGENTS.md - Rules for the coding agent

Read `memory.md` first and then this file, completely, before you write any code, and again at the start of every stage. `memory.md` is the map and the current state of the project, so you do not need to scan the whole repository.

## 1. What you are building

The backend foundation of a multi-tenant educational platform (Django + Django REST Framework + PostgreSQL). Each teacher has a workspace on their own sub-domain. The team of juniors will review your work stage by stage and extend it afterwards, so **clear, consistent, boring code matters more than clever code or extra features.**

## 2. Source of truth

- `memory.md` tells you what exists, what is done, and which design section answers which question. Start there.
- The design is in `docs/backend-design.md`. Read only the sections named in the stage prompt (and the design index in `memory.md`), plus section 12 (business rules) every time. Do not read the whole design or every file in the repository unless the task needs it.
- The section "Build Scope for This Round" and section 15 (decisions) override everything else in that document.
- If something you need is missing or contradictory, **stop and ask**. Do not guess, and do not invent endpoints, fields, or behavior that the design does not describe.

## 3. Scope

In scope: Stages 1-5 fully working; Stage 6 as a models-only skeleton; backend only.

Out of scope, do not build: the React frontend, deployment/DNS/SSL, AI generation, mistake analysis, proctoring, the assistant role's permissions, the email-verification endpoint, online payments. Do not create models for the AI and proctoring tables. `apps/ai/` and `apps/proctoring/` are empty placeholders with a README only.

Do exactly the stage you are given. Do not start the next stage, and do not "improve" earlier stages unless the stage prompt says so.

## 4. Environment and dependencies

- Run `python --version` in the active virtual environment and use that interpreter. Choose package versions that officially support it. If no stable, compatible combination exists, stop and report.
- Allowed dependencies: `Django`, `djangorestframework`, `drf-spectacular`, `psycopg` (v3), `django-environ`, `Pillow`. Ask before adding anything else.
- Pin exact versions in `backend/requirements.txt` in Stage 1. Never upgrade a pinned package without asking.
- Configuration comes from environment variables read by `django-environ`. Commit `backend/.env.example` with every variable and a safe placeholder. Never commit `.env` or any secret.
- Database: PostgreSQL. Do not add SQLite fallbacks.
- Development defaults: emails use Django's console email backend; uploaded files go to a local private folder under the backend directory that is **never** served directly (only through an authorized view).

## 5. Layout and naming

- Follow section 10.1 of the design: `backend/config/` and `backend/apps/<app>/`.
- Models use the table names from section 5 of the design as `Meta.db_table` (for example `PaymentSubmission` with `db_table = "payment_submissions"`).
- If the repository already contains a bare `django-admin startproject` skeleton, reuse it (rename the settings package to `config` if needed) instead of creating a second project.
- One responsibility per file: `models.py`, `serializers.py`, `views.py`, `permissions.py`, `services.py` (only when an operation needs several coordinated steps), `urls.py`, `tests/`.

## 6. Patterns every app must follow

These patterns are the part the team will copy. Write them once, cleanly, and reuse them.

1. **Workspace comes from the URL slug.** A single mixin loads the `Workspace` from the slug (404 if missing) and exposes it as `view.workspace`. Never read workspace, role, reviewer, amount, or approval state from the request body.
2. **Every tenant query is scoped.** Retrieve objects from a queryset already filtered by `workspace=view.workspace` (and by the user where relevant), never globally and then check afterwards.
3. **Permission classes** live in each app's `permissions.py` and check `role`, `workspace`, `approval_status`, and workspace `status` as in section 9.4. The project default is `IsAuthenticated`; public endpoints opt in with `AllowAny` explicitly.
4. **Serializers** always list `fields` explicitly (never `__all__`). Privileged fields (`role`, `workspace`, `approval_status`, `login_key`, `reviewed_by`, `amount`, `price_at_enrollment`) are read-only or not exposed. Public serializers expose only the safe fields in section 7.1.
5. **Multi-step operations** go in a service function wrapped in `transaction.atomic()`. Emails and notifications are sent with `transaction.on_commit()`, never inside the transaction.
6. **State changes verify the current state** inside the transaction (for example, a payment must still be `submitted`) and use `select_for_update()` where two requests could race.
7. **Database constraints back up validation.** Unique and conditional constraints from sections 5 and 12 are declared on the models, not only checked in serializers.
8. **Errors:** use DRF's standard error responses and correct status codes. Login failures must not reveal whether an email exists, except as section 7.2 describes.
9. **Throttling** (DRF scoped throttles) on login, staff login, registration, and password-reset endpoints.
10. **Documentation:** every view declares its serializer and permission so `drf-spectacular` generates a correct schema. Use `extend_schema` where the schema cannot be inferred.

## 7. Security rules that are never optional

- Passwords only through Django's password hashing. Invitation and reset links use Django's built-in token generator, not custom cryptography.
- Session cookies are host-only: never set `SESSION_COOKIE_DOMAIN`. Keep the settings from section 9.3.
- Receipts and other private files: validate type and size (JPEG, PNG, PDF; at most 5 MB), store them privately, and serve them only through the authorized endpoint.
- A suspended workspace must be rejected by the backend, not only hidden in the UI.
- Pending and rejected students cannot log in. Rejected accounts are never deleted.
- Never log passwords, tokens, or receipt contents.

## 8. Tests

- Use Django's built-in test runner and DRF `APITestCase`. No extra test framework.
- Small helper functions that create a workspace, a teacher, and a student (in `tests/helpers.py` of each app, or one shared module) are better than a factory library.
- Every rule you implement from section 9.7 and section 12 needs a test that fails if the rule is removed.
- Cross-workspace tests are mandatory for every endpoint that touches tenant data: a user from workspace A must get 403/404 on workspace B, including by guessing IDs.
- Email-after-commit behavior is tested with `captureOnCommitCallbacks`.

## 9. Definition of done for a stage

A stage is finished only when all of these are true:

1. Everything the stage prompt lists is implemented, and nothing from a later stage.
2. `python manage.py check`, `makemigrations --check --dry-run`, and the full test suite pass on a clean PostgreSQL database.
3. `GET /api/schema/` generates without warnings you can fix, and the new endpoints appear in `/api/docs/` with correct request and response shapes.
4. `README.md` is updated: how to set up `.env`, create the database, run migrations, run tests, create a Platform Admin, and anything new from this stage.
5. `memory.md` is updated (section 13) in the same commit as the code.
6. Your final report (section 11) is written.

## 10. Git

- Work on a branch named `stage-<n>-<short-name>` (for example `stage-1-foundation`). Never commit to `main`, never merge, never force-push.
- Commit in small logical steps with clear messages (for example `Add Workspace model and slug validators`).
- Do not rewrite migrations that are already committed in an earlier stage. If an earlier migration is wrong, stop and report.

## 11. Final report

End every stage with a short report containing:

- What was built, in a few lines.
- How to run it and how to run the tests (exact commands).
- Decisions you had to make that the design did not cover, each with the reason.
- Anything you left out or are unsure about.
- The list of design sections a reviewer should read to follow the code.

## 12. Stop and ask when

- The design is ambiguous, contradictory, or silent on something you need.
- A required package version conflicts with the Python version.
- You think a rule in the design is wrong or unsafe.
- The stage seems to need work from a later stage or a different scope.

A short question is always cheaper than a wrong guess the team has to find later.

## 13. Keeping `memory.md` up to date

`memory.md` is what the next session (and the next teammate) reads instead of scanning everything. At the end of every stage, before your final report:

1. Set the stage row in section 5 to `done - awaiting review` and fill in the branch name.
2. Add or refresh one line per app in "Repository map": responsibility, key models, endpoints, stage.
3. Add the reusable building blocks you created (workspace mixin, permission classes, test helpers, services) with their file paths, so nobody rewrites them.
4. List every decision the design did not cover, one line each, with the reason. These are the same decisions as in your final report.
5. Fill in "How to run" with the exact commands you used, and record known problems.
6. Remove entries that are no longer true. Keep the file under about 200 lines.

Rules:

- Write only what you verified in the code or by running it. If you are unsure, say so under "Known problems" instead of guessing.
- Do not paste code, long explanations, or copies of the design. Point to files and sections.
- Do not edit the scope reminder or the deferred list unless the team asked you to.
- If you find that `memory.md` contradicts the code, trust the code, fix `memory.md`, and mention it in your report.
