# AI-Powered Educational Platform
## Backend Workflow, Database Entities, and Django REST Framework API Design — Final Version

> **Document purpose:** This document consolidates the workflow, database entities, API endpoints, permission rules, and implementation recommendations for the AI-Powered Educational Platform.
>
> **Architecture status:** This is a proposed MVP design, not implemented code. Endpoint names and model fields may be adjusted during implementation.
>
> **Final version:** The main domain is a public showcase for students (no registration or login). It explains the platform, lists the teachers, and shows each teacher's public profile (name, bio, about, and courses) with **Sign up** and **Login** buttons that send the student to that teacher's sub-domain. All student authentication happens on the teacher's sub-domain using **Django session authentication**. Teachers are created by the Platform Admin. Students are approved by the teacher, then choose free or paid courses. Paid courses use manual payment confirmation in the MVP.

---

## Build Scope for This Round (read first)

This copy of the design is prepared for an AI coding agent that builds the **backend foundation** of the platform. The team reviews it stage by stage and extends it afterwards. **Where this section conflicts with the rest of the document, this section wins.**

### In scope

- **Backend only:** Django + Django REST Framework + PostgreSQL. No React frontend and no deployment, DNS, or SSL work (section 13 and Stage 7 are reference only).
- **Stages 1-5** of section 14, fully working and tested.
- **Stage 6 as a skeleton:** models, migrations, and Django admin registration for the non-AI content and assessment tables. **No endpoints.**
- **API documentation from Stage 1:** OpenAPI schema and Swagger UI through `drf-spectacular`, so the frontend developer can work in parallel against a written contract.

### Out of scope (do not build, and do not create models for)

- 5.11 `ai_generation_jobs`, 5.14 `ai_question_generations`, 5.19 `performance_analyses`, 5.20 `topic_weaknesses`, 5.21 `learning_recommendations`, 5.22 `proctoring_events`, 5.23 `proctoring_evidence`.
- Two empty placeholder apps, `apps/ai/` and `apps/proctoring/`, are created with a README that restates the relevant contract from this document. They contain no models, no endpoints, and no migrations.
- The assistant role (the value exists in the `role` enum; nothing grants it permissions yet).
- The email-verification endpoint, online payment gateways, platform billing, and any notification beyond the emails named in this document.
- Plain fields that mention AI or proctoring inside in-scope tables (`questions.source_type`, `exams.proctoring_enabled`, `exam_attempts.proctoring_review_status`) stay as ordinary fields.

### Skeleton tables (Stage 6)

`course_sections`, `lessons`, `lesson_assets`, `topics`, `lesson_topics`, `questions`, `question_topics`, `exams`, `exam_questions`, `exam_attempts`, `answers`. For each one: model, the database constraints from sections 5 and 12, migration, admin registration, and tests for the constraints. No serializers, views, or URLs.

### Decisions made for this round

The product decisions are in section 15. The process and environment decisions are:

- One git branch per stage, tests passing, and a human review before the next stage starts.
- PostgreSQL for everyone, configuration from environment variables, and a committed `.env.example`.
- In development, emails print to the console and files are stored in a local private folder.
- Tests use Django's built-in test runner with DRF `APITestCase`.
- API docs at `GET /api/schema/` and `GET /api/docs/`.

---

## What Changed Compared with the First Draft

| Area | First draft | Final version |
|---|---|---|
| Main domain | Landing page with teacher registration/login | Public showcase only: platform features, advantages, and a teacher directory. **No registration or login.** |
| Student entry | Student opens a workspace, registers or logs in | Student picks a teacher on the main site, then clicks **Sign up** or **Login** on the teacher's profile, which sends the student to the teacher's sub-domain |
| Student accounts | One global account plus `Membership` per workspace | **One account per workspace.** The same email can exist at two teachers as two independent accounts. No `Membership` table. |
| Teacher onboarding | Teacher applies, verifies email, waits for approval, then creates a workspace | **Platform Admin creates the teacher account and the workspace together.** No `TeacherApplication`. |
| Teacher login | Public login on the main platform | **Private URL** on the teacher's own sub-domain |
| Student approval | Not part of the flow (join by invitation/code) | **Teacher approves each student** after registration |
| Course joining | Invitation or join code | Student **chooses a course** inside the workspace (free or paid). `CourseInvitation` is deferred. |
| Paid courses | Out of scope | **Manual payment** in the MVP: student pays outside the platform and submits proof, teacher confirms |
| Subdomain routing | Optional / later | **Core part of the MVP** |
| Authentication | Not decided | **Django session authentication** with host-only cookies; the API is served from the same host as the frontend |
| Public teacher profile | Teacher name and course list | Name, logo, headline, bio, about, and published courses with prices, plus **Sign up** and **Login** buttons for that teacher |
| Roles | Not detailed | **One role per account** on one custom `User` model; no separate Student/Teacher tables; permission classes check role and workspace |

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Roles and Responsibilities](#2-roles-and-responsibilities)
3. [Core Design Decisions](#3-core-design-decisions)
4. [Main User Workflows](#4-main-user-workflows)
5. [Database Entities](#5-database-entities)
6. [Entity Relationships](#6-entity-relationships)
7. [API Endpoints](#7-api-endpoints)
8. [Request and Response Examples](#8-request-and-response-examples)
9. [Roles, Authentication, and Multi-Tenant Isolation](#9-roles-authentication-and-multi-tenant-isolation)
10. [Recommended Django Project Structure](#10-recommended-django-project-structure)
11. [Responsibilities of the Main Backend Layers](#11-responsibilities-of-the-main-backend-layers)
12. [Important Database and Business Rules](#12-important-database-and-business-rules)
13. [Subdomain and Workspace Routing](#13-subdomain-and-workspace-routing)
14. [Implementation Order](#14-implementation-order)
15. [Decisions Status](#15-decisions-status)

---

## 1. Project Overview

The platform is a multi-tenant educational SaaS application. Each teacher has an isolated workspace on their own sub-domain, with their own branding, courses, learning materials, quizzes, and students. AI can help generate quiz-question drafts and analyze student mistakes, while teachers remain responsible for reviewing generated questions and making decisions about suspected cheating.

The main domain (for example `edunova.com`) is a **public showcase**. It explains what the platform can do and lists the teachers on the platform. Students use the system in the browser, and all sign-up, login, and learning happen on the teacher's sub-domain (for example `drahmed.edunova.com`).

The backend is planned around **Django + Django REST Framework (DRF)**. The frontend communicates with the backend through REST API endpoints.

### Main MVP capabilities

> **Build round note:** AI quiz drafts, mistake analysis, and proctoring in this list are **not** built in this round (see Build Scope). Only the non-AI database tables exist, as a skeleton.

- Public landing page, teacher directory, and teacher profile pages with Sign up / Login buttons (no accounts on the main domain).
- Platform Admin creates teacher accounts and workspaces.
- Teacher login through a private URL on the teacher's sub-domain.
- Student registration and login on the teacher's sub-domain.
- Session-based authentication with host-only cookies per sub-domain.
- Teacher approval of students.
- Course management; students choose free or paid courses.
- Manual payment submission and teacher confirmation for paid courses.
- AI-generated quiz drafts that teachers review before publishing.
- Student quiz attempts, results, and mistake analysis.
- Proctoring signals/flags for teacher review.
- Platform administration of teacher workspaces.

The full project may later add online payment gateways, platform billing or commissions, usage limits, and expanded analytics. Those are not required for the first version.

### Important AI policy

- AI-generated questions should remain drafts until a teacher reviews and approves them.
- AI proctoring should produce signals or flags for review; it should not independently make a final cheating decision.
- A teacher should remain the decision-maker for publishing questions and interpreting suspicious activity.

---

## 2. Roles and Responsibilities

### 2.1 Platform Admin

The Platform Admin manages the platform as a whole.

Responsibilities:

- Create teacher accounts together with their workspaces.
- Resend a teacher's set-password invitation when needed.
- View and manage teachers and workspaces.
- Suspend or reactivate workspaces when needed.
- Access platform-level administrative functions.

Platform Admin access must not be offered through any public registration flow. Admins log in through a separate admin URL (a dedicated admin front-end, or Django admin served at a non-default path), never through the main landing page.

### 2.2 Teacher

A Teacher owns one workspace. The teacher account is created by the Platform Admin; teachers do not register themselves.

Responsibilities:

- Set a password from the invitation link and log in through the private teacher URL.
- Manage workspace branding, public profile, and payment instructions.
- Approve or reject student registrations.
- Create courses (free or paid), sections, and lessons.
- Upload learning materials.
- Generate AI question drafts and review them.
- Publish quizzes and exams.
- Confirm or reject manual payments for paid courses.
- Review results, mistakes, and proctoring flags.
- Invite or manage assistants, if enabled later.

### 2.3 Assistant (planned for after the first MVP stages)

An Assistant belongs to one teacher workspace and has limited permissions configured by the Teacher.

Possible responsibilities:

- Help manage course content.
- Assist with student administration (for example, reviewing pending students).
- Review or confirm payments, if the teacher allows it.
- Review allowed quiz or student information.

An assistant's permissions are always scoped to the single workspace the assistant belongs to.

### 2.4 Student

A Student uses the platform to learn and take assessments, always inside one teacher's workspace.

Responsibilities:

- Discover a teacher on the main site and follow the Sign up or Login button to the teacher's sub-domain.
- Register on the teacher's sub-domain and wait for the teacher's approval.
- Log in after approval and choose courses (free or paid).
- Submit payment proof for paid courses.
- Access materials of courses where the enrollment is active.
- Take quizzes or exams.
- Review results and feedback about mistakes.

### 2.5 One account per workspace

Each account belongs to exactly one workspace and carries exactly one role directly. There is no shared global student account.

- A student who studies with two teachers has two separate accounts, one on each sub-domain, each with its own password.
- Platform Admin accounts are the only accounts without a workspace.
- Because accounts are workspace-scoped, an account from Workspace A can never be used in Workspace B.

**Trade-off:** this gives strong isolation and privacy between teachers and keeps permissions simple. The cost is that students manage a separate password for each teacher and there is no unified "my courses" page across teachers.

If the team later prefers a single shared account across teachers, the alternative is a global `User` plus a `Membership` table. That change would mainly affect sections 2, 5.1, and 7.

---

## 3. Core Design Decisions

1. **The main domain is a public showcase.** It has no registration and no login. It shows platform features, advantages, and the teacher directory.
2. **All student authentication happens on the teacher's sub-domain.** The Sign up and Login buttons on the teacher profile are plain links to that sub-domain; no session or token is transferred from the main domain.
3. **Accounts belong to one workspace.** The `User` has a `workspace` and a `role`. Only Platform Admins have no workspace.
4. **Teachers are created by the Platform Admin.** The admin creates the workspace and the teacher account in one transaction. There is no teacher self-registration and no `TeacherApplication` in the MVP.
5. **Teachers set their password from an expiring invitation link** instead of the admin choosing or knowing the password.
6. **Teacher login uses a private URL** on the teacher's sub-domain. The URL is not linked from student pages. It is not a security control by itself; the backend enforces the role.
7. **Students are approved by the teacher.** A new student account is `pending` and cannot log in until approved.
8. **After approval, the student chooses courses.** Free courses activate immediately. Paid courses require manual payment confirmation by the teacher.
9. **Payment is manual in the MVP.** The platform records payment claims and confirmations; it does not process money.
10. **Use a custom Django User model from the beginning**, with a unique internal `login_key` as the `USERNAME_FIELD`.
11. **Do not use `is_staff` to mean "Teacher."** Django's `is_staff` relates to access to Django's admin site only.
12. **The workspace comes from the URL slug / sub-domain, never from a client-supplied field.** Ownership, reviewers, and roles are always derived from the authenticated request.
13. **Workspace slugs are unique, validated, and immutable after creation.** The slug is the sub-domain name.
14. **Authentication uses Django sessions.** Host-only `HttpOnly` cookies per sub-domain; the API is served from the same host as the frontend. JWT is not used in the MVP.
15. **One role per account.** A single custom `User` model carries `role` and `workspace`. There are no separate Student/Teacher login tables, and Django Groups are not used for roles.
16. **Each teacher has a public profile page** on the main site (name, headline, bio, about, published courses with prices) with **Sign up** and **Login** buttons that lead to the teacher's sub-domain.

---

## 4. Main User Workflows

### 4.1 Public landing page and teacher directory

```text
Visitor opens edunova.com
        |
        v
Landing page: what the platform does, features, advantages
        |
        v
Teacher directory (listed and active workspaces only)
        |
        v
Teacher profile page: name, logo/photo, headline, bio, about,
published courses (with prices)
        |
        +---------------------+
        |                     |
        v                     v
    [Sign up]              [Login]
        |                     |
        v                     v
https://{slug}.edunova.com/signup    https://{slug}.edunova.com/login
```

Notes:

- The main domain has no authentication. The buttons are links built from the teacher's slug.
- The landing page content is static frontend content. The directory and teacher profile read from public API endpoints.
- Only workspaces that are active and marked as listed appear in the directory.
- The teacher profile page is where the student decides. It shows who the teacher is (name, headline, bio, about) and what they teach (published courses with prices), and carries the **Sign up** and **Login** buttons for this teacher only.
- A student who wants to register with a teacher does it from this profile (or from the teacher's sub-domain link). There is no sign-up on the main site itself.

### 4.2 Teacher onboarding by the Platform Admin

```text
Platform Admin logs in (separate admin URL)
        |
        v
Enter teacher name, email, workspace name, and slug
        |
        v
Validate email and slug (format, reserved words, uniqueness)
        |
        v
[Single database transaction]
   Create Workspace (status = active)
   Create User (role = teacher, workspace = new workspace, unusable password)
        |
        v
After commit: send set-password email (expiring token link)
        |
        v
Teacher opens the link on https://{slug}.edunova.com and sets a password
        |
        v
Teacher logs in at the private URL:
https://{slug}.edunova.com/teacher/login
        |
        v
Teacher dashboard: branding, public profile, payment instructions, courses
```

Example:

- Main platform: `edunova.com`
- Teacher workspace: `drahmed.edunova.com`
- Workspace name: `Dr Ahmed Academy`
- Workspace slug: `drahmed`

The slug is a unique identifier, not the complete domain name. Actual subdomain routing also requires deployment and DNS configuration (see section 13).

### 4.3 Student registration and approval

```text
Student opens https://{slug}.edunova.com/signup
        |
        v
Submit registration (full name, email, password)
        |
        v
Create User (role = student, workspace = from slug, approval_status = pending)
        |
        v
Student sees "waiting for teacher approval" (no session is issued)
        |
        v
Teacher reviews pending students
        |
        +-------------------------+
        |                         |
        v                         v
     Reject                    Approve
        |                         |
        v                         v
approval_status = rejected   approval_status = approved
Save reason, notify student  Notify student
                                  |
                                  v
                          Student can log in
```

Notes:

- A rejected student is notified of the reason (an email sent after the transaction commits, and a message shown when logging in with correct credentials).
- The rejected account row is kept, so the same email cannot register again with that teacher (duplicate `login_key`). A friendlier message, a teacher "reopen" action, and an explicit block are planned for a later stage.

### 4.4 Course selection, enrollment, and manual payment

```text
Approved student logs in on the teacher's sub-domain
        |
        v
Browses published courses (price or free)
        |
        v
Chooses a course  ->  POST enroll
        |
        +---------------------------------+
        |                                 |
        v                                 v
   Free course                       Paid course
        |                                 |
        v                                 v
Enrollment: active              Enrollment: pending_payment
        |                                 |
        |                       Student sees the teacher's
        |                       payment instructions
        |                                 |
        |                       Student pays outside the platform
        |                                 |
        |                       Student submits a payment claim
        |                       (method, note, optional receipt)
        |                                 |
        |                       Payment: submitted
        |                                 |
        |                       Teacher/assistant reviews
        |                          +------+------+
        |                          |             |
        |                          v             v
        |                       Confirm        Reject (reason)
        |                          |             |
        |                  Payment: confirmed  Payment: rejected
        |                  Enrollment: active  Enrollment stays
        |                          |           pending_payment
        |                          |           (student may resubmit)
        +------------+-------------+
                     |
                     v
Access course content -> take quizzes -> results and mistake analysis
```

Rules:

- Teacher approval is required once per student (workspace access). It is not repeated for each course.
- Course content is available only when the enrollment status is `active`.
- Confirming a payment and activating the enrollment must happen in one transaction.

### 4.5 Platform Admin workflow

```text
Platform Admin logs in (separate admin URL)
        |
        v
Create teacher + workspace  <-- resend invitation if needed
        |
        v
View teachers and workspaces
        |
        v
Suspend or reactivate a workspace when needed
```

---

## 5. Database Entities

The latest database design is the **Unified Database ERD**, with 23 separate tables. Each tenant-owned table stores `workspace_id` as a foreign key to `workspaces` with `PROTECT` behavior. This explicit tenant key supports safe scoping and consistent workspace ownership; validate that all related records belong to that same workspace. Use the project’s selected primary-key type consistently (the ERD allows bigint or UUID), add database indexes for common filters, and store timestamps in UTC.

### 5.1 `workspaces`

One teacher sub-domain and its isolated educational workspace.

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | Primary key (bigint or UUID) | Workspace identifier |
| `name` | `varchar(150)` | Display name |
| `slug` | Unique `varchar(63)`, immutable | Workspace route identifier |
| `subdomain` | Nullable unique `varchar(255)` | Optional full sub-domain / hostname |
| `logo` | Nullable image URL/reference | Workspace branding |
| `headline` | Nullable `varchar(200)` | Public profile headline |
| `bio`, `about` | Nullable text | Public teacher profile content |
| `is_listed` | Boolean, default `false` | Directory visibility |
| `payment_instructions` | Nullable text | Manual payment instructions |
| `status` | `active` or `suspended` | Workspace availability |
| `created_at` | Timestamp | Creation time |

Keep slug validation and reserved-name checks. A workspace is publicly listed only when active and `is_listed=true`.

### 5.2 `users`

One account belongs to one workspace, except a platform admin. The same email can identify independent accounts in different workspaces.

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | Primary key | User identifier |
| `workspace_id` | Nullable FK to `workspaces` (`PROTECT`) | Null only for an admin |
| `role` | `admin`, `teacher`, `assistant`, `student` | Account role |
| `email` | `varchar(254)`, normalized lowercase | Contact and login input |
| `login_key` | Unique `varchar(320)` | Server-derived Django login identifier (`workspace_id:email`; `admin:email` for admins) |
| `password` | Django password hash (`varchar(128)`) | Authentication credential |
| `full_name` | `varchar(150)` | Display name |
| `phone` | Nullable `varchar(30)` | Optional contact number |
| `is_active` | Boolean, default `true` | Account activation |
| `approval_status` | `pending`, `approved`, `rejected` | Student approval; staff/admin are approved on creation |
| `reviewed_by` | Nullable self-FK | Reviewer of a student registration |
| `reviewed_at` | Nullable timestamp | Review time |
| `rejection_reason` | Nullable text | Reason for rejection |
| `email_verified` | Boolean, default `false` | Optional email verification state |
| `date_joined` | Timestamp | Account creation time |

Constraints: unique `login_key`; at most one teacher per workspace; and `workspace_id IS NULL` exactly when `role='admin'`. Never accept `login_key`, role, reviewer, or workspace ownership from an untrusted client. Keep rejected accounts so the same workspace/email cannot register again.

### 5.3 `courses`

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | Primary key | Course identifier |
| `workspace_id` | Required FK to `workspaces` (`PROTECT`) | Tenant owner |
| `title` | `varchar(200)` | Course title |
| `description` | Nullable text | Course details |
| `price` | `decimal(10,2)`, zero means free | Price snapshot source |
| `is_published` | Boolean, default `false` | Student/public visibility |
| `created_at` | Timestamp | Creation time |

Use one platform currency for the MVP. A course must belong to the requesting workspace.

### 5.4 `course_sections`

> **Skeleton only this round (Stage 6):** model + constraints + migration + admin registration + constraint tests. No serializers, views, or URLs.

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | Primary key | Section identifier |
| `workspace_id` | Required FK to `workspaces` (`PROTECT`) | Tenant owner |
| `course_id` | Required FK to `courses` | Parent course |
| `title` | `varchar(200)` | Section title |
| `position` | Integer, default `1` | Display order |
| `created_at` | Timestamp | Creation time |

### 5.5 `course_enrollments`

A student's course enrollment; unique on `(student_id, course_id)`.

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | Primary key | Enrollment identifier |
| `workspace_id` | Required FK to `workspaces` (`PROTECT`) | Tenant owner |
| `student_id` | Required FK to `users` | Enrolled student |
| `course_id` | Required FK to `courses` | Selected course |
| `status` | `pending_payment`, `active`, `withdrawn` | Enrollment lifecycle |
| `price_at_enrollment` | `decimal(10,2)`, copied by the server from `courses.price` when the enrollment is created | Price the student agreed to; later course price changes do not affect it |
| `created_at` | Timestamp | Enrollment time |
| `activated_at` | Nullable timestamp | Activation time |

Require an active, approved student and a published course in the same workspace. Free enrollment is active immediately; paid enrollment starts `pending_payment`.

### 5.6 `payment_submissions`

A manual payment claim for an enrollment. Multiple attempts may exist after rejection; only one `submitted` claim per enrollment may be open at a time.

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | Primary key | Submission identifier |
| `workspace_id` | Required FK to `workspaces` (`PROTECT`) | Tenant owner |
| `enrollment_id` | Required FK to `course_enrollments` | Enrollment being paid for |
| `submitted_by` | Required FK to `users` | Student submitting proof |
| `amount` | `decimal(10,2)`, copied by the server from `course_enrollments.price_at_enrollment` (never from the client) | Amount being claimed |
| `method` | `transfer`, `e_wallet`, `cash`, `other` | Payment method |
| `note` | Nullable text | Reference or message |
| `receipt_image` | Nullable private file key | Payment proof |
| `status` | `submitted`, `confirmed`, `rejected` | Review state |
| `submitted_at` | Timestamp | Submission time |
| `reviewed_by` | Nullable FK to `users` | Authorized reviewer |
| `reviewed_at` | Nullable timestamp | Review time |
| `rejection_reason` | Nullable text | Rejection explanation |

Confirmation activates the enrollment in the same transaction. Rejection leaves it pending payment and permits resubmission. Receipt files must use private storage and authorized delivery.

### 5.7 `lessons`

> **Skeleton only this round (Stage 6):** model + constraints + migration + admin registration + constraint tests. No serializers, views, or URLs.

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | Primary key | Lesson identifier |
| `workspace_id` | Required FK to `workspaces` (`PROTECT`) | Tenant owner |
| `course_id` | Required FK to `courses` | Parent course |
| `section_id` | Nullable FK to `course_sections` | Optional parent section |
| `title` | `varchar(200)` | Lesson title |
| `content` | Nullable text | Lesson content |
| `position` | Integer, default `1` | Display order |
| `is_published` | Boolean, default `true` | Lesson visibility |
| `created_at` | Timestamp | Creation time |

### 5.8 `lesson_assets`

> **Skeleton only this round (Stage 6):** model + constraints + migration + admin registration + constraint tests. No serializers, views, or URLs.

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | Primary key | Asset identifier |
| `workspace_id` | Required FK to `workspaces` (`PROTECT`) | Tenant owner |
| `lesson_id` | Required FK to `lessons` | Parent lesson |
| `title` | `varchar(200)` | Asset title |
| `asset_type` | `pdf`, `video`, `slide`, `doc`, `audio` | File category |
| `storage_key` | `varchar(500)`, private | Private object-storage key |
| `mime_type` | Nullable `varchar(100)` | Media type |
| `file_size` | Nullable bigint | File size in bytes |
| `extraction_status` | `pending`, `running`, `done`, `failed` | Text-processing state |
| `extracted_text` | Nullable text | Extracted content for search/AI |
| `created_at` | Timestamp | Creation time |

### 5.9 `topics`

> **Skeleton only this round (Stage 6):** model + constraints + migration + admin registration + constraint tests. No serializers, views, or URLs.

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | Primary key | Topic identifier |
| `workspace_id` | Required FK to `workspaces` (`PROTECT`) | Tenant owner |
| `course_id` | Nullable FK to `courses` | Optional course scope |
| `name` | `varchar(150)` | Topic name |
| `slug` | `varchar(150)`, unique with workspace | Stable topic key |
| `created_at` | Timestamp | Creation time |

### 5.10 `lesson_topics`

> **Skeleton only this round (Stage 6):** model + constraints + migration + admin registration + constraint tests. No serializers, views, or URLs.

Join table between lessons and topics; unique on `(lesson_id, topic_id)`.

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | Primary key | Link identifier |
| `workspace_id` | Required FK to `workspaces` (`PROTECT`) | Tenant owner |
| `lesson_id` | Required FK to `lessons` | Linked lesson |
| `topic_id` | Required FK to `topics` | Linked topic |

### 5.11 `ai_generation_jobs`

> **OUT OF SCOPE FOR THIS ROUND - contract only.** Do not create this model or its migration. It stays here so the AI team can build against it later.

Tracks asynchronous AI question-generation or analysis work.

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | Primary key | Job identifier |
| `workspace_id` | Required FK to `workspaces` (`PROTECT`) | Tenant owner |
| `requested_by` | Required FK to `users` | Requesting teacher/staff user |
| `job_type` | `question_gen`, `analysis` | Job purpose |
| `status` | `queued`, `running`, `succeeded`, `failed` | Job lifecycle |
| `provider` | Nullable `varchar(60)` | AI provider |
| `model_name` | Nullable `varchar(100)` | Model used |
| `prompt_version` | Nullable `varchar(50)` | Prompt version |
| `input_tokens`, `output_tokens` | Integers, default `0` | Usage counters |
| `estimated_cost` | Nullable `decimal(10,6)` | Estimated cost |
| `error_metadata` | Nullable JSON | Structured failure details |
| `created_at` | Timestamp | Queue time |
| `completed_at` | Nullable timestamp | Completion time |

### 5.12 `questions`

> **Skeleton only this round (Stage 6):** model + constraints + migration + admin registration + constraint tests. No serializers, views, or URLs.

A reusable question, either manually authored or AI-generated. AI output remains a draft until teacher review.

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | Primary key | Question identifier |
| `workspace_id` | Required FK to `workspaces` (`PROTECT`) | Tenant owner |
| `course_id` | Nullable FK to `courses` | Optional course scope |
| `lesson_id` | Nullable FK to `lessons` | Optional lesson scope |
| `source_type` | `manual`, `ai_generated` | Origin |
| `status` | `draft`, `approved`, `rejected`, `archived` | Review/publication state |
| `question_type` | `mcq`, `true_false`, `short`, `essay` | Answer format |
| `stem` | Text | Question prompt |
| `options` | Nullable JSON | Choices for supported types |
| `correct_answer` | JSON or text | Answer key |
| `explanation` | Nullable text | Explanation/feedback |
| `difficulty` | `easy`, `medium`, `hard` | Difficulty level |
| `points` | `decimal(5,2)` | Default score value |
| `reviewed_by` | Nullable FK to `users` | Teacher reviewer |
| `reviewed_at` | Nullable timestamp | Review time |
| `created_at` | Timestamp | Creation time |

### 5.13 `question_topics`

> **Skeleton only this round (Stage 6):** model + constraints + migration + admin registration + constraint tests. No serializers, views, or URLs.

Join table between questions and topics; unique on `(question_id, topic_id)`.

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | Primary key | Link identifier |
| `workspace_id` | Required FK to `workspaces` (`PROTECT`) | Tenant owner |
| `question_id` | Required FK to `questions` | Linked question |
| `topic_id` | Required FK to `topics` | Linked topic |

### 5.14 `ai_question_generations`

> **OUT OF SCOPE FOR THIS ROUND - contract only.** Do not create this model or its migration. It stays here so the AI team can build against it later.

Links a generation job to its output question and optional lesson or exam context.

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | Primary key | Generation record identifier |
| `workspace_id` | Required FK to `workspaces` (`PROTECT`) | Tenant owner |
| `job_id` | Required FK to `ai_generation_jobs` | Generation job |
| `lesson_id` | Required FK to `lessons` | Source lesson |
| `exam_id` | Nullable FK to `exams` | Optional target exam |
| `question_id` | Required FK to `questions` | Generated draft |
| `created_at` | Timestamp | Generation time |

### 5.15 `exams`

> **Skeleton only this round (Stage 6):** model + constraints + migration + admin registration + constraint tests. No serializers, views, or URLs.

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | Primary key | Exam identifier |
| `workspace_id` | Required FK to `workspaces` (`PROTECT`) | Tenant owner |
| `course_id` | Required FK to `courses` | Parent course |
| `lesson_id` | Nullable FK to `lessons` | Optional lesson scope |
| `title` | `varchar(200)` | Exam title |
| `description` | Nullable text | Exam instructions/details |
| `duration_minutes` | Nullable integer | Time limit |
| `passing_score` | Nullable `decimal(5,2)` | Pass threshold |
| `max_attempts` | Integer, default `1` | Attempt limit |
| `proctoring_enabled` | Boolean, default `false` | Whether to collect proctoring events |
| `status` | `draft`, `published`, `archived` | Exam lifecycle |
| `published_at` | Nullable timestamp | Publication time |
| `created_at` | Timestamp | Creation time |

### 5.16 `exam_questions`

> **Skeleton only this round (Stage 6):** model + constraints + migration + admin registration + constraint tests. No serializers, views, or URLs.

Join table between exams and questions; unique on `(exam_id, question_id)`.

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | Primary key | Link identifier |
| `workspace_id` | Required FK to `workspaces` (`PROTECT`) | Tenant owner |
| `exam_id` | Required FK to `exams` | Parent exam |
| `question_id` | Required FK to `questions` | Included question |
| `position` | Integer, default `1` | Display order |
| `points_override` | Nullable `decimal(5,2)` | Exam-specific point value |

### 5.17 `exam_attempts`

> **Skeleton only this round (Stage 6):** model + constraints + migration + admin registration + constraint tests. No serializers, views, or URLs.

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | Primary key | Attempt identifier |
| `workspace_id` | Required FK to `workspaces` (`PROTECT`) | Tenant owner |
| `exam_id` | Required FK to `exams` | Attempted exam |
| `student_id` | Required FK to `users` | Attempting student |
| `attempt_number` | Integer, default `1` | Attempt sequence |
| `status` | `in_progress`, `submitted`, `graded` (and any explicitly defined terminal state) | Attempt lifecycle |
| `started_at` | Timestamp | Start time |
| `submitted_at`, `graded_at` | Nullable timestamps | Submission and grading times |
| `score`, `max_score` | Nullable `decimal(6,2)` | Result values |
| `passed` | Nullable boolean | Pass result |
| `proctoring_review_status` | `clean`, `flagged`, `cleared`, `void` | Human review state |
| `reviewed_by` | Nullable FK to `users` | Staff reviewer |

### 5.18 `answers`

> **Skeleton only this round (Stage 6):** model + constraints + migration + admin registration + constraint tests. No serializers, views, or URLs.

Unique on `(attempt_id, question_id)`.

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | Primary key | Answer identifier |
| `workspace_id` | Required FK to `workspaces` (`PROTECT`) | Tenant owner |
| `attempt_id` | Required FK to `exam_attempts` | Parent attempt |
| `question_id` | Required FK to `questions` | Answered question |
| `selected_option` | Nullable JSON | Selected choice(s) |
| `text_answer` | Nullable text | Free-text response |
| `is_correct` | Nullable boolean | Grading result |
| `points_awarded` | Nullable `decimal(5,2)` | Awarded score |
| `answered_at` | Timestamp | Answer time |

### 5.19 `performance_analyses`

> **OUT OF SCOPE FOR THIS ROUND - contract only.** Do not create this model or its migration. It stays here so the AI team can build against it later.

One analysis per exam attempt; `exam_attempt_id` is unique. Store the AI job when available.

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | Primary key | Analysis identifier |
| `workspace_id` | Required FK to `workspaces` (`PROTECT`) | Tenant owner |
| `exam_attempt_id` | Unique FK to `exam_attempts` | Analyzed attempt |
| `job_id` | Nullable FK to `ai_generation_jobs` | Analysis job |
| `overall_summary` | Text | Summary of performance and mistakes |
| `generated_at` | Timestamp | Analysis time |

### 5.20 `topic_weaknesses`

> **OUT OF SCOPE FOR THIS ROUND - contract only.** Do not create this model or its migration. It stays here so the AI team can build against it later.

Unique on `(analysis_id, topic_id)`.

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | Primary key | Weakness identifier |
| `workspace_id` | Required FK to `workspaces` (`PROTECT`) | Tenant owner |
| `analysis_id` | Required FK to `performance_analyses` | Parent analysis |
| `topic_id` | Required FK to `topics` | Weak topic |
| `questions_attempted`, `questions_correct` | Integers | Topic-level counts |
| `accuracy_rate` | `decimal(5,2)` | Accuracy percentage |
| `severity` | `low`, `medium`, `high`, `insufficient` | Weakness estimate |

### 5.21 `learning_recommendations`

> **OUT OF SCOPE FOR THIS ROUND - contract only.** Do not create this model or its migration. It stays here so the AI team can build against it later.

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | Primary key | Recommendation identifier |
| `workspace_id` | Required FK to `workspaces` (`PROTECT`) | Tenant owner |
| `analysis_id` | Required FK to `performance_analyses` | Parent analysis |
| `topic_id` | Nullable FK to `topics` | Optional topic focus |
| `lesson_id` | Nullable FK to `lessons` | Optional recommended lesson |
| `recommendation_text` | Text | Suggested learning action |
| `priority_order` | Integer, default `1` | Display order |

### 5.22 `proctoring_events`

> **OUT OF SCOPE FOR THIS ROUND - contract only.** Do not create this model or its migration. It stays here so the AI team can build against it later.

Signals are for staff review and do not make an automatic cheating verdict.

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | Primary key | Event identifier |
| `workspace_id` | Required FK to `workspaces` (`PROTECT`) | Tenant owner |
| `attempt_id` | Required FK to `exam_attempts` | Related attempt |
| `student_id` | Required FK to `users` | Student observed |
| `event_type` | `tab_switch`, `face`, `audio`, `copy`, and defined additions | Signal category |
| `severity` | `info`, `warning`, `high` | Signal severity |
| `occurred_at` | Indexed timestamp | Event time |
| `details` | Nullable JSON | Structured event metadata |
| `review_status` | `pending`, `dismissed`, `violation` | Staff decision |
| `reviewed_by` | Nullable FK to `users` | Reviewer |
| `reviewed_at` | Nullable timestamp | Review time |

### 5.23 `proctoring_evidence`

> **OUT OF SCOPE FOR THIS ROUND - contract only.** Do not create this model or its migration. It stays here so the AI team can build against it later.

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | Primary key | Evidence identifier |
| `workspace_id` | Required FK to `workspaces` (`PROTECT`) | Tenant owner |
| `event_id` | Required FK to `proctoring_events` | Parent event |
| `evidence_type` | `snapshot`, `video`, `screen`, `audio` | Evidence category |
| `storage_key` | `varchar(500)`, private | Private object-storage key |
| `mime_type` | Nullable `varchar(100)` | Media type |
| `file_size` | Nullable bigint | File size in bytes |
| `retention_expires_at` | Nullable timestamp | Retention deadline |
| `created_at` | Timestamp | Creation time |
## 6. Entity Relationships

### 6.1 Relationship summary

| Relationship | Meaning |
|---|---|
| `workspaces` 1 — many `users` | One workspace contains its teacher, assistants, and students; admin workspace is null |
| `workspaces` 1 — many tenant tables | All tenant-owned records carry `workspace_id` for isolation |
| `workspaces` 1 — many `courses` | A workspace owns courses |
| `courses` 1 — many `course_sections`, `lessons`, `topics`, and `exams` | Course content and assessments |
| `course_sections` 1 — many `lessons` | A lesson may optionally belong to a section |
| `lessons` 1 — many `lesson_assets` | Private learning material files |
| `lessons` many — many `topics` through `lesson_topics` | Topic tagging for lessons |
| `questions` many — many `topics` through `question_topics` | Topic tagging for questions |
| `users` (student) many — many `courses` through `course_enrollments` | Student participation, unique per student/course |
| `course_enrollments` 1 — many `payment_submissions` | Payment attempts and reviews |
| `lessons` / `exams` 1 — many `ai_question_generations` | Generation source and optional destination exam |
| `ai_generation_jobs` 1 — many generation records / 0..1 performance analysis | Tracks AI work and results |
| `exams` many — many `questions` through `exam_questions` | Ordered exam question set |
| `exams` 1 — many `exam_attempts` | Student attempts |
| `exam_attempts` 1 — many `answers` and `proctoring_events` | Answers and reviewable signals |
| `exam_attempts` 1 — 0..1 `performance_analyses` | One generated performance analysis per attempt |
| `performance_analyses` 1 — many `topic_weaknesses` and `learning_recommendations` | Mistake analysis and follow-up guidance |
| `proctoring_events` 1 — many `proctoring_evidence` | Private evidence associated with a signal |
| `users` 1 — many reviewed records | Staff review students, payments, questions, attempts, and events |

### 6.2 ER diagram

The full 23-table entity relationship diagram is maintained in `docs/database/Database last version.pdf`. The diagram’s key structural rules are reflected above: join tables represent many-to-many relationships, nullable foreign keys represent optional links, and tenant-owned tables carry their own `workspace_id`.
## 7. API Endpoints

These are proposed REST endpoints. They describe API responsibilities and are not implemented automatically by Django REST Framework.

The examples use the prefix `/api/v1/`. The frontend on `{slug}.edunova.com` reads the slug from its hostname and calls these path-based endpoints.

### 7.1 Public endpoints (no authentication)

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/v1/public/teachers/` | List teachers for the main-site directory (active and listed workspaces only; paginated, searchable) |
| `GET` | `/api/v1/public/teachers/{slug}/` | Public teacher profile: name, logo, headline, bio, about, and published courses with prices (listed workspaces only) |
| `GET` | `/api/v1/workspaces/{slug}/branding/` | Branding for a sub-domain (name, logo, headline, status), even if the workspace is not listed |
| `GET` | `/api/v1/workspaces/{slug}/public-profile/` | Same public profile as the directory page (same serializer, same safe fields) for any **active** workspace, listed or not. Served on the teacher's sub-domain before login (see 15.5). A suspended workspace gets the "unavailable" response. |

Public responses must contain only safe fields: workspace name, slug, teacher display name, logo, headline, bio, about, and published course title, description, and price. Never expose emails, student counts, or internal data.

### 7.2 Student authentication (per workspace)

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| `POST` | `/api/v1/workspaces/{slug}/auth/register/` | Register a student with `pending` approval | Public |
| `POST` | `/api/v1/workspaces/{slug}/auth/login/` | Log in an approved student | Public |
| `POST` | `/api/v1/workspaces/{slug}/auth/logout/` | End the session | Authenticated |
| `GET` | `/api/v1/workspaces/{slug}/auth/me/` | Current user and role in this workspace | Authenticated |
| `GET` | `/api/v1/workspaces/{slug}/auth/csrf/` | Set the CSRF cookie for the frontend (also used by the staff login page) | Public |
| `POST` | `/api/v1/workspaces/{slug}/auth/password-reset/` | Start password reset | Public |
| `POST` | `/api/v1/workspaces/{slug}/auth/password-reset/confirm/` | Finish password reset | Public with valid token |
| `POST` | `/api/v1/workspaces/{slug}/auth/verify-email/` | Verify email (**not built in this round, see 15.8**) | Public with valid token |

Registration behavior: resolve the workspace from the slug, check it is active, create the student with `approval_status = pending`, and issue **no** session or token. Reject a duplicate email in the same workspace (the unique `login_key` enforces this).

Login behavior: build `login_key`, authenticate, then check the account state. Reveal `pending` or `rejected` status only after the credentials are verified, so the response does not leak which emails exist. On success, create the Django session (session cookie); logout flushes the session.

### 7.3 Teacher / staff authentication (private URL)

The frontend serves the teacher login page at a private path such as `/teacher/login` on the sub-domain; it is not linked from student pages.

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| `POST` | `/api/v1/workspaces/{slug}/staff/auth/login/` | Log in a teacher or assistant | Public (throttled) |
| `POST` | `/api/v1/workspaces/{slug}/staff/auth/set-password/` | Set the first password from the invitation link | Public with valid token |
| `POST` | `/api/v1/workspaces/{slug}/staff/auth/password-reset/` | Start password reset for staff | Public (throttled) |

The staff login endpoint accepts only accounts whose role is `teacher` or `assistant`. A student presenting valid student credentials gets the same generic failure as a wrong password.

### 7.4 Platform Admin

Admin authentication uses a separate admin URL (a dedicated admin front-end, or Django admin at a non-default path). The endpoints below require role `admin`.

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/admin/teachers/` | Create a teacher and a workspace in one transaction and send the invitation |
| `GET` | `/api/v1/admin/teachers/` | List teachers |
| `GET` | `/api/v1/admin/teachers/{id}/` | View a teacher and their workspace |
| `POST` | `/api/v1/admin/teachers/{id}/resend-invite/` | Resend the set-password email |
| `GET` | `/api/v1/admin/workspaces/` | List workspaces |
| `GET` | `/api/v1/admin/workspaces/{id}/` | View workspace details |
| `POST` | `/api/v1/admin/workspaces/{id}/suspend/` | Suspend a workspace |
| `POST` | `/api/v1/admin/workspaces/{id}/activate/` | Reactivate a workspace |

Teacher creation responsibilities:

1. Authenticate the Platform Admin.
2. Validate email, workspace name, and slug (format, reserved names, uniqueness).
3. In one transaction, create the `Workspace` and the teacher `User` (role `teacher`, workspace set, unusable password, `approval_status = approved`).
4. After the transaction commits, send the set-password email with an expiring token link pointing to `https://{slug}.edunova.com/...`.
5. If sending the email fails, the account remains valid and the admin can use `resend-invite`.

### 7.5 Workspace and student management (teacher)

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| `GET` | `/api/v1/workspaces/{slug}/` | Get workspace details | Workspace staff |
| `PATCH` | `/api/v1/workspaces/{slug}/` | Update name, logo, headline, bio, `is_listed`, `payment_instructions` (slug is not editable) | Teacher |
| `GET` | `/api/v1/workspaces/{slug}/students/` | List students, filterable by `?status=pending|approved|rejected` | Teacher or permitted assistant |
| `POST` | `/api/v1/workspaces/{slug}/students/{id}/approve/` | Approve a pending student | Teacher or permitted assistant |
| `POST` | `/api/v1/workspaces/{slug}/students/{id}/reject/` | Reject a pending student with a reason | Teacher or permitted assistant |

Approve and reject must verify that the student belongs to this workspace, is `pending`, and record `reviewed_by` and `reviewed_at` from the authenticated request. Send the notification after the transaction commits.

### 7.6 Courses and enrollment

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| `GET` | `/api/v1/workspaces/{slug}/courses/` | List published courses (price/free, and the student's enrollment status) | Approved students and staff |
| `POST` | `/api/v1/workspaces/{slug}/courses/` | Create a course | Teacher or permitted assistant |
| `GET` | `/api/v1/workspaces/{slug}/courses/{id}/` | Retrieve a course | Authorized user |
| `PATCH` | `/api/v1/workspaces/{slug}/courses/{id}/` | Update a course | Teacher or permitted assistant |
| `POST` | `/api/v1/workspaces/{slug}/courses/{id}/enroll/` | Choose a course: free becomes `active`, paid becomes `pending_payment` | Approved student |
| `GET` | `/api/v1/workspaces/{slug}/enrollments/me/` | The student's enrollments and statuses | Approved student |

Enrolling twice in the same course should return the existing enrollment rather than creating a duplicate.

### 7.7 Manual payments

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| `POST` | `/api/v1/workspaces/{slug}/enrollments/{id}/payments/` | Submit a payment claim (multipart, optional receipt) | Student who owns the enrollment |
| `GET` | `/api/v1/workspaces/{slug}/payments/` | List payments, filterable by `?status=submitted` | Teacher or permitted assistant |
| `GET` | `/api/v1/workspaces/{slug}/payments/{id}/receipt/` | View the receipt through an authorized endpoint | Teacher/permitted assistant, or the owning student |
| `POST` | `/api/v1/workspaces/{slug}/payments/{id}/confirm/` | Confirm; the enrollment becomes `active` | Teacher or permitted assistant |
| `POST` | `/api/v1/workspaces/{slug}/payments/{id}/reject/` | Reject with a reason | Teacher or permitted assistant |

### 7.8 Endpoint design notes

- Use serializers to validate incoming request data and shape responses.
- Use authentication to establish who is making the request.
- Use permissions and queryset scoping to establish what that user may access.
- Use a service function for multi-step operations such as teacher creation, student approval, enrollment, and payment confirmation.
- Return appropriate HTTP status codes and useful validation errors.
- Document whether each endpoint is public, authenticated, or restricted to a particular role.
- Apply throttling to login, registration, and password-reset endpoints.

### 7.9 Out of scope this round, and API documentation endpoints

- No endpoints are built for sections, lessons, lesson assets, topics, questions, exams, attempts, or answers. Their models exist as a skeleton (Stage 6).
- No AI or proctoring endpoints.
- No assistant-specific endpoints or permissions.
- API documentation (built in Stage 1 with `drf-spectacular`): `GET /api/schema/` returns the OpenAPI schema and `GET /api/docs/` serves Swagger UI. They are enabled by an environment flag, on in development.

---

## 8. Request and Response Examples

### 8.1 Student registration

`POST /api/v1/workspaces/drahmed/auth/register/`

```json
{
  "email": "ali@example.com",
  "password": "A-strong-password",
  "full_name": "Ali Hassan"
}
```

Possible successful response:

```json
{
  "message": "Registration received. Your account is waiting for the teacher's approval.",
  "approval_status": "pending"
}
```

No token or session is returned. The request must not accept `role`, `workspace`, or `approval_status` from the client.

### 8.2 Login while pending (after correct credentials)

`POST /api/v1/workspaces/drahmed/auth/login/`

```json
{
  "email": "ali@example.com",
  "password": "A-strong-password"
}
```

Possible response (HTTP 403):

```json
{
  "code": "pending_approval",
  "message": "Your account is waiting for the teacher's approval."
}
```

These responses are illustrative; the exact format should match the project's API conventions.

### 8.3 Admin creates a teacher and workspace

`POST /api/v1/admin/teachers/`

```json
{
  "full_name": "Dr Ahmed",
  "email": "teacher@example.com",
  "workspace_name": "Dr Ahmed Academy",
  "slug": "drahmed"
}
```

Possible successful response:

```json
{
  "teacher_id": 21,
  "workspace_id": 7,
  "slug": "drahmed",
  "invitation_sent": true
}
```

The backend creates the workspace and teacher in one transaction and sends the invitation after commit.

### 8.4 Teacher sets the first password

`POST /api/v1/workspaces/drahmed/staff/auth/set-password/`

```json
{
  "uid": "<encoded user id>",
  "token": "<expiring token>",
  "new_password": "A-strong-password"
}
```

### 8.5 Public teacher directory

`GET /api/v1/public/teachers/`

```json
{
  "results": [
    {
      "slug": "drahmed",
      "name": "Dr Ahmed Academy",
      "teacher_name": "Dr Ahmed",
      "logo": "https://.../logo.png",
      "headline": "Organic chemistry made simple"
    }
  ]
}
```

Public teacher profile:

`GET /api/v1/public/teachers/drahmed/`

```json
{
  "slug": "drahmed",
  "name": "Dr Ahmed Academy",
  "teacher_name": "Dr Ahmed",
  "logo": "https://.../logo.png",
  "headline": "Organic chemistry made simple",
  "bio": "Short biography of the teacher.",
  "about": "Longer description of the teacher and the academy.",
  "courses": [
    { "id": 12, "title": "Organic Chemistry", "description": "...", "price": "500.00" },
    { "id": 13, "title": "Introduction", "description": "...", "price": "0.00" }
  ]
}
```

The response never includes emails or student counts. The frontend builds the **Sign up** and **Login** links from the slug (`https://drahmed.edunova.com/signup` and `https://drahmed.edunova.com/login`).

### 8.6 Approve a student

`POST /api/v1/workspaces/drahmed/students/45/approve/`

The request body may be empty. The reviewer is taken from the authenticated request, not from the client.

### 8.7 Choose a paid course

`POST /api/v1/workspaces/drahmed/courses/12/enroll/`

Possible response:

```json
{
  "enrollment_id": 88,
  "status": "pending_payment",
  "price": "500.00",
  "payment_instructions": "Transfer to ... then submit your payment proof."
}
```

For a free course the status would be `active` immediately.

### 8.8 Submit a payment claim

`POST /api/v1/workspaces/drahmed/enrollments/88/payments/` (multipart form)

```text
method=e_wallet
note=Reference 12345
receipt_image=<file>
```

The backend sets the amount from `course_enrollments.price_at_enrollment`; the client does not send the amount.

### 8.9 Confirm or reject a payment

`POST /api/v1/workspaces/drahmed/payments/31/confirm/`

`POST /api/v1/workspaces/drahmed/payments/31/reject/`

```json
{
  "rejection_reason": "The receipt is unreadable. Please upload a clearer image."
}
```

The server must verify that the payment is still `submitted` and belongs to this workspace before changing its state.

---

## 9. Roles, Authentication, and Multi-Tenant Isolation

This section explains how the system knows who the user is, how users authenticate, and how permissions keep each teacher's workspace isolated from the others.

### 9.1 One account, one role: how the system knows who the user is

Each account has exactly **one role** and belongs to **one workspace** (except Platform Admins, who have no workspace). A person who is a teacher in one place and a student in another has two separate accounts, so there is no ambiguity about who the user is.

1. **Login:** on the teacher's sub-domain the backend builds `login_key` from the workspace and the submitted email. Because `login_key` is unique, exactly one `User` row can match.
2. **Session:** after a successful login the session identifies that single row, and on every request Django loads it into `request.user`.
3. **Permissions:** `request.user.role`, `request.user.workspace`, and `request.user.approval_status` are compared with the workspace in the URL and the requested action.

Authentication answers "who are you?"; permissions answer "what may you do here?".

### 9.2 Why one custom User model (and not separate Student and Teacher tables)

Django builds `request.user`, sessions, password reset, and DRF authentication on **one** user model (`AUTH_USER_MODEL`). It must be chosen before the first migration, and changing it later is painful. This project needs its own fields (`workspace`, `role`, `login_key`, `approval_status`), so a custom `User` is required.

| Option | Idea | Decision |
|---|---|---|
| A. One `User` table with a `role` field | All accounts in one table | **Chosen** |
| B. `User` plus profile tables | `User` handles login; `StudentProfile` / `TeacherProfile` (one-to-one) hold role-specific data | Add later only if role-specific fields appear |
| C. Independent `Student` and `Teacher` tables without a shared user | Each table has its own email and password | Not recommended |

Why not option C:

- Two login tables duplicate login, password-reset, and hashing logic and need custom authentication backends.
- `request.user` could be a `Student` or a `Teacher`, forcing type checks everywhere.
- Every new role (assistant, admin) would add another table and another login system.
- Foreign keys such as `reviewed_by` (teacher or assistant) become more complicated.

Django's built-in **Groups and Permissions** are not used for roles. They are global, so a "teacher" group would mean a teacher in every workspace and cannot express "teacher of workspace 7 only". The combination of `role` and `workspace` is used instead.

### 9.3 Authentication: Django session authentication (decided)

Use Django sessions with DRF `SessionAuthentication`.

- After login the server stores the session and sends the browser a session cookie, which the browser sends back with every request.
- Cookies are **host-only**, so each teacher's sub-domain has its own login state. This matches the one-account-per-workspace design.
- The API must be served from the **same host** as the frontend: the reverse proxy sends `/` to the React app and `/api/` to Django on every sub-domain. A central API host such as `api.edunova.com` would make all teachers share one session cookie, and logins at two teachers would collide in the same browser.
- Required settings: `SESSION_COOKIE_SECURE = True`, `SESSION_COOKIE_SAMESITE = "Lax"`, **no** `SESSION_COOKIE_DOMAIN`, and `CSRF_TRUSTED_ORIGINS = ["https://*.edunova.com"]`.
- CSRF: a small endpoint (`GET .../auth/csrf/`) sets the CSRF cookie using `ensure_csrf_cookie`, and the frontend sends it back in the `X-CSRFToken` header on POST, PATCH, and DELETE requests.
- Why sessions: the platform is browser-only, a suspension or rejection must take effect immediately, the session cookie is `HttpOnly` (scripts cannot read it), and no token has to be stored in `localStorage`.
- JWT is not used in the MVP. Reconsider it only if a native mobile app or a central API host is introduced.

### 9.4 Permission classes

DRF permission classes run before a view and allow or deny the request. They keep "who may do what" in one reusable, testable place. Illustrative example (not tested):

```python
from rest_framework.permissions import BasePermission


class IsWorkspaceTeacher(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return (
            u.is_authenticated
            and u.role == "teacher"
            and u.workspace_id == view.workspace.id  # workspace from the URL slug
            and view.workspace.status == "active"
        )


class IsApprovedStudent(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return (
            u.is_authenticated
            and u.role == "student"
            and u.approval_status == "approved"
            and u.workspace_id == view.workspace.id
        )


class IsPlatformAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "admin"
```

`view.workspace` is set by a small mixin that reads the `slug` from the URL and loads the `Workspace` (404 if it does not exist). Each view chooses its class, for example `permission_classes = [IsWorkspaceTeacher]`.

| Endpoint | Permission |
|---|---|
| `GET /public/teachers/` and `GET /public/teachers/{slug}/` | `AllowAny` |
| `POST /admin/teachers/` | `IsPlatformAdmin` |
| `POST .../students/{id}/approve/` and `/reject/` | `IsWorkspaceTeacher` |
| `POST .../courses/{id}/enroll/` | `IsApprovedStudent` |
| `POST .../payments/{id}/confirm/` and `/reject/` | `IsWorkspaceTeacher` |

Object-level rules (for example a student may see only their own enrollments) are enforced by scoping the queryset and, where needed, `has_object_permission`.

### 9.5 Do not rely on the URL alone

A request such as:

```text
GET /api/v1/workspaces/drahmed/courses/15/
```

must not retrieve course `15` merely because the caller knows its ID.

The backend should check:

1. The workspace identified by `drahmed` exists and is active.
2. `request.user.workspace` is that same workspace.
3. The requested course belongs to that exact workspace.
4. The user's role and `approval_status` permit the requested operation.
5. Any additional rule is satisfied (for example, the enrollment is `active` for course content).

A queryset should be scoped to the selected workspace, conceptually:

```python
Course.objects.filter(workspace=workspace)
```

Then retrieve the requested course from that scoped queryset, rather than retrieving it globally and forgetting to check its workspace.

### 9.6 Role checks

Examples:

- Only Platform Admins can create teachers and workspaces or suspend workspaces.
- Only the teacher (or a permitted assistant) of a workspace can approve students, manage courses, and confirm payments.
- Only approved students can browse courses and enroll.
- Students can access course content only with an `active` enrollment.
- An account in Workspace A must not grant access to Workspace B.
- The staff login endpoint rejects student accounts.

### 9.7 Important isolation tests

Write automated tests that verify:

- A user from Workspace A cannot read Workspace B's data by changing the slug or an ID in the URL.
- A student token from Workspace A is rejected in Workspace B.
- A pending or rejected student cannot log in or access any data.
- A student cannot create a course, approve students, or confirm payments.
- A student cannot confirm their own payment.
- A non-admin cannot create teachers or workspaces.
- The staff login endpoint rejects student credentials.
- A suspended workspace cannot be used as if it were active.
- A student cannot enroll in a course of another workspace.
- Duplicate enrollment or duplicate email in the same workspace is rejected, while the same email in a different workspace is allowed.
- A rejected payment leaves the enrollment `pending_payment`; a confirmed payment activates it.
- Course content is not accessible while the enrollment is `pending_payment`.
- Payment receipts are not accessible to other students or other workspaces.

---

## 10. Recommended Django Project Structure

One possible structure. Create `workspaces` first (it has no foreign key to `User`), then `accounts` (whose `User` references `Workspace`).

```text
backend/
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── ...
├── apps/
│   ├── workspaces/
│   │   ├── models.py          # Workspace
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── permissions.py
│   │   ├── validators.py      # slug rules, reserved names
│   │   └── ...
│   ├── accounts/
│   │   ├── models.py          # custom User, manager (login_key)
│   │   ├── serializers.py
│   │   ├── views.py           # student auth, staff auth, student approval
│   │   ├── permissions.py
│   │   ├── services.py        # create_teacher_with_workspace, approve_student
│   │   └── ...
│   ├── public/
│   │   ├── serializers.py     # safe public fields only
│   │   ├── views.py           # teacher directory, teacher profile, branding
│   │   └── ...
│   ├── courses/
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── ...
│   ├── enrollments/
│   │   ├── models.py          # Enrollment
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── services.py        # enroll_student
│   │   └── ...
│   └── payments/
│       ├── models.py          # Payment
│       ├── serializers.py
│       ├── views.py
│       ├── services.py        # submit_payment, confirm_payment, reject_payment
│       └── ...
└── manage.py
```

This is a suggested layout, not a mandatory Django convention. App names and boundaries can change as the project evolves.

### 10.1 Layout for this build round

```text
repo/
├── AGENTS.md                    # rules for the coding agent
├── memory.md                    # project map, status, and decisions (read first by the agent)
├── README.md                    # how to run, test, and add a feature
├── docs/
│   └── backend-design.md        # this document
└── backend/
    ├── manage.py
    ├── requirements.txt         # exact pinned versions
    ├── .env.example
    ├── config/                  # env-driven settings, urls
    └── apps/
        ├── workspaces/          # Workspace
        ├── accounts/            # custom User, auth, student approval, teacher onboarding
        ├── public/              # directory, public profile, branding (safe fields only)
        ├── courses/             # courses (Stage 5); course_sections, lessons, lesson_assets (Stage 6 skeleton)
        ├── enrollments/         # CourseEnrollment
        ├── payments/            # PaymentSubmission
        ├── assessments/         # topics, questions, exams, attempts, answers (Stage 6 skeleton)
        ├── ai/                  # EMPTY placeholder: README only
        └── proctoring/          # EMPTY placeholder: README only
```

Use the table names from section 5 as `Meta.db_table` so the database matches the ER diagram.


---

## 11. Responsibilities of the Main Backend Layers

### Models

Models define database entities, relationships, and database-level constraints.

Examples:

- Unique workspace slug and unique `login_key`.
- One teacher per workspace.
- Unique `(student, course)` enrollment.
- Foreign keys between workspace, course, and enrollment.
- Payment and enrollment status fields.

Database constraints are important because validation only in a view or serializer may not protect against every path that writes to the database.

### Serializers

Serializers validate incoming API data and convert model instances to response representations.

Examples:

- Validate a workspace name and slug.
- Accept registration fields without allowing a client to set privileged fields such as `role`, `workspace`, or `approval_status`.
- Serialize course data and public teacher profiles using safe field lists.

Do not expose sensitive fields such as password hashes, `login_key`, or internal security tokens in ordinary API responses.

### Views or ViewSets

Views/ViewSets handle HTTP requests and responses.

Typical responsibilities:

1. Receive the request and resolve the workspace from the slug.
2. Authenticate and authorize the caller through configured mechanisms.
3. Validate data through serializers.
4. Call model/queryset operations or service functions.
5. Return a response with an appropriate status code.

### Permissions

Permission classes answer questions such as:

- Is the user authenticated?
- Is the user a Platform Admin?
- Does the user belong to this workspace, and with which role?
- Is the student approved?
- Does the student have an active enrollment in this course?
- May this user perform this action on this object?

Authentication answers "who are you?"; authorization answers "what are you allowed to do?"

### Services

Service functions are useful for operations that require several coordinated steps.

Good candidates:

- Creating a teacher and workspace atomically and sending the invitation after commit.
- Approving or rejecting a student.
- Enrolling a student (free vs paid).
- Confirming a payment and activating the enrollment atomically.
- Triggering notifications after a successful database update.

Do not create a `services.py` file in every app just for the sake of it. Use a service layer when the operation's complexity or reuse justifies it.

---

## 12. Important Database and Business Rules

1. **Use a custom User model early.** Changing the user model after the project has accumulated migrations and relationships can be disruptive.
2. **Never store plaintext passwords.** Use Django's authentication/password facilities.
3. **Accounts belong to one workspace.** Only Platform Admins have no workspace.
4. **`login_key` is unique and derived by the server.** Build it from the workspace id (or `admin`) plus the normalized email; recompute it if the email changes.
5. **Create the workspace and the teacher atomically.** Avoid a workspace with no teacher or a teacher with no workspace after a partial failure.
6. **One teacher per workspace.** Enforce with a conditional unique constraint.
7. **Slugs are unique, validated, reserved-word-checked, and immutable.**
8. **Student approval and course enrollment are separate.** Approval gives workspace access; enrollment gives course access.
9. **Pending and rejected students cannot log in.** Enforce in the backend, not only in the frontend.
10. **Derive sensitive values from the authenticated request or the URL.** Do not trust `workspace`, `role`, `reviewed_by`, or `amount` sent by an untrusted client.
11. **Scope every tenant-owned query.** Check that a requested object belongs to the workspace in the URL and to the user's workspace.
12. **Check workspace status.** Suspension must be enforced by backend authorization and query behavior, not merely hidden in the frontend.
13. **Course content requires an `active` enrollment.**
14. **Payments are claims until confirmed.** Only the workspace's teacher or a permitted assistant can confirm; confirmation and enrollment activation happen in one transaction.
15. **Protect receipts.** Private storage, authorized access only, file type and size validation.
16. **Send emails after the transaction commits** (or through a reliable background task).
17. **Public endpoints expose only safe fields** and only for active, listed workspaces (the branding endpoint also serves active unlisted workspaces).
18. **Throttle login, registration, and password-reset endpoints.** A private URL is not a security control.
19. **Keep important audit history.** Teacher creation, suspension, student approval/rejection, and payment decisions may need audit records.
20. **Keep AI output reviewable.** Generated quiz questions should not be published automatically, and proctoring flags should not be treated as a definitive cheating verdict.
21. **Rejected accounts are kept.** Never delete a rejected student; the unique `login_key` then stops the same email from registering again with that teacher.
22. **Session cookies are host-only and the API is same-origin.** Never set a shared cookie domain across teachers.
23. **Roles come from the account, not from the client.** Permission classes compare `role`, `workspace`, and `approval_status` of `request.user` with the workspace in the URL.
24. **Every tenant-owned table carries `workspace_id`.** Use `PROTECT` for the workspace foreign key and validate matching workspace IDs across related rows to prevent cross-tenant links.
25. **Preserve relationship constraints.** Enforce uniqueness for student/course enrollment, lesson/topic and question/topic links, exam/question links, attempt/question answers, analysis/attempt, and analysis/topic weakness. Allow only one submitted payment per enrollment at a time.
26. **Protect all learning and proctoring files.** Lesson assets, payment receipts, and proctoring evidence use private storage, authorization checks, file validation, and the configured evidence retention deadline.
27. **Treat AI and proctoring as auditable workflows.** Track AI job state, provider/model/prompt version, token usage and errors; AI questions remain reviewable drafts, while proctoring events remain signals for a human reviewer.

---

## 13. Subdomain and Workspace Routing

Sub-domains are now a core part of the product, not an optional extra. A workspace slug such as `drahmed` maps to a hostname such as `drahmed.edunova.com`.

A database slug alone does not make that sub-domain work. Deployment must also configure:

- A domain with a wildcard DNS record (`*.edunova.com`) pointing to the deployment.
- A wildcard SSL certificate so every sub-domain is served over HTTPS.
- Web server or hosting configuration that serves the same frontend for every sub-domain.
- Django settings that accept sub-domains: `ALLOWED_HOSTS = [".edunova.com"]`, `CSRF_TRUSTED_ORIGINS` with a wildcard origin such as `https://*.edunova.com` (Django 4.0+), and CORS settings that allow the sub-domain origins if the API is on a different host.

### Recommended routing approach

- One React application serves the main domain and all sub-domains.
- On a sub-domain, the frontend reads the slug from `window.location.hostname` and calls the existing path-based API (`/api/v1/workspaces/{slug}/...`).
- The backend always verifies that `request.user.workspace` matches the slug in the URL, so isolation does not depend on the frontend.
- Hostname-to-workspace middleware is optional; it is not needed for the MVP with this approach.
- In production the reverse proxy serves the React build at `/` and forwards `/api/` to Django on every sub-domain, so the API is same-origin with the frontend (required for session cookies, see 9.3).

### Main domain to sub-domain hand-off

- The Sign up and Login buttons on the teacher profile are plain links to `https://{slug}.edunova.com/signup` and `https://{slug}.edunova.com/login`.
- No token or session is passed, because the main domain has no authentication.

### Sessions and storage

- The platform uses Django session authentication (see 9.3).
- Each sub-domain is a separate origin, so the browser keeps login state separately per teacher.
- Keep cookies host-only. Do not set a cookie domain such as `.edunova.com`, because that would share cookies across all teachers and weaken isolation.
- Serve the API from the same host as the frontend (same-origin `/api/`) so each sub-domain has its own session cookie.

### Private teacher URL

- Teacher and assistant login lives at a private path such as `/teacher/login` on the sub-domain.
- Do not link to it from student pages; add `noindex` to keep it out of search results.
- The backend still rejects student accounts at the staff login endpoint and throttles attempts.

### Suspended or unknown sub-domains

- If the slug does not exist, show a neutral "not found" page.
- If the workspace is suspended, show an "unavailable" page and have the backend reject normal operations.

### Local development

The team may use a sub-domain-style host such as:

```text
http://drahmed.localhost:5173
```

Modern browsers generally resolve `*.localhost` to the local machine, so no DNS setup is needed. For session cookies, proxy `/api` to Django through the Vite dev server so the API stays same-origin with `drahmed.localhost:5173`. Alternatively, use the path-based API directly (for example from an API client):

```text
http://localhost:8000/api/v1/workspaces/drahmed/courses/
```

---

## 14. Implementation Order

Build the backend in stages so each stage can be tested before the next one depends on it.

### Stage 1 — Workspaces and accounts foundation

- Create `Workspace` (with slug validation and reserved names).
- Create the custom `User` with `workspace`, `role`, `login_key`, and `approval_status`, plus its manager.
- Add the constraints (unique `login_key`, one teacher per workspace, admin/workspace check).
- Add tests for constraints and `login_key` generation.
- Project bootstrap (part of Stage 1): settings read from environment variables, PostgreSQL connection, `.env.example`, `AUTH_USER_MODEL` set before the first migration, DRF defaults (`SessionAuthentication`, default permission `IsAuthenticated`, so public endpoints must opt in with `AllowAny`), and `drf-spectacular` with `/api/schema/` and `/api/docs/`.
- Platform Admin access: Django admin at a non-default path (`DJANGO_ADMIN_PATH`, default `platform-admin/`). The custom manager implements `create_superuser` (role `admin`, no workspace, `login_key = admin:<email>`, `is_staff = True`). Admins type `admin:<email>` as the username on the Django admin login page; document this in the README.

### Stage 2 — Teacher onboarding and staff login

- Implement the admin endpoint that creates a teacher and workspace atomically.
- Implement the set-password invitation (expiring token) and `resend-invite`.
- Implement the staff login endpoint (role check, throttling).
- Add tests for creation, invitation, and role rejection.

### Stage 3 — Public showcase endpoints

- Implement the teacher directory, teacher profile (name, headline, bio, about, published courses), and branding endpoints with safe fields.
- Add the `is_listed` and workspace status rules.
- Add tests that unlisted and suspended workspaces behave correctly.
- Add `GET /api/v1/workspaces/{slug}/public-profile/` (see 15.5): same serializer as the directory profile, any active workspace, listed or not.

### Stage 4 — Student registration, login, and approval

- Configure session authentication (host-only cookies, CSRF settings, and the CSRF cookie endpoint).
- Implement student registration (pending), login (with pending/rejected handling), password reset, and `me`.
- Implement the teacher's pending-students list and approve/reject.
- Add tests for account states and cross-workspace access.

### Stage 5 — Courses, enrollment, and manual payments

- Create `courses` and `course_enrollments`; implement course management and the `enroll` action (free vs paid).
- Create `payment_submissions`; implement submission, teacher review, confirm and reject with transactions.
- Add protected receipt access.
- Add tests for duplicate enrollment, cross-workspace enrollment, and payment state transitions.
- Set `price_at_enrollment` when an enrollment is created and derive the payment `amount` from it (see 15.7).
- Add a `HasActiveEnrollment` permission class with unit tests, ready for the content endpoints of a later round. Course sections, lessons, and assets are **not** part of Stage 5; they are Stage 6 skeleton tables.

### Stage 6 — Content and assessment skeleton (models only)

- In `apps/courses/` add `course_sections`, `lessons`, and `lesson_assets`. In `apps/assessments/` add `topics`, `lesson_topics`, `questions`, `question_topics`, `exams`, `exam_questions`, `exam_attempts`, and `answers`.
- Enforce the uniqueness rules of section 12, rule 25, for these tables, and validate that related rows share the same `workspace_id` (model `clean()` plus tests).
- Register every model in the Django admin and create the migrations.
- Create `apps/ai/` and `apps/proctoring/` as empty Django apps with a README that restates the contract from sections 5.11, 5.14, and 5.19-5.23. No models, no endpoints.
- No serializers, views, URLs, or AI calls. Deferred to later rounds: AI jobs, AI question generation, mistake analysis, proctoring, exam-taking endpoints, content endpoints, and the rule that exam access needs an active enrollment.

### Stage 7 — Frontend integration and sub-domain deployment (deferred, not in this round)

- Build the landing page and teacher directory/profile on the main domain.
- Implement sub-domain resolution in the React app.
- Implement student sign-up/login, the teacher dashboard, the admin screens, and course/payment screens.
- Configure wildcard DNS, wildcard SSL, and Django host/CSRF/CORS settings.
- Ensure UI state never substitutes for backend permission checks.

---

## 15. Decisions Status

All decisions needed for this build round are settled below. Record any later change here.

### 15.0 Decisions already made

- **Authentication:** Django session authentication (host-only cookies; the API on the same host as the frontend).
- **Accounts:** one account per workspace and one role per account, on a single custom `User` model.
- **Teachers:** created by the Platform Admin together with the workspace; they log in through a private URL.
- **Students:** register on the teacher's sub-domain and need the teacher's approval.
- **Courses:** students choose free or paid courses; payment is manual in the MVP.
- **Rejected students:** notified with the reason; blocking re-registration is implemented later.
- **Main domain:** a teacher directory and teacher profile pages (name, bio, about, courses) with Sign up / Login buttons.

### 15.1 One workspace per teacher (decided)

A teacher owns exactly one workspace. A person who needs two workspaces uses two teacher accounts with different emails.

### 15.2 What happens to a rejected student? (decided)

The student is notified of the reason for the rejection and is restricted from registering again with that teacher. The restriction is implemented in a later stage.

- Keep the rejected account row (never delete it): the unique `login_key` already prevents the same email from registering again with that teacher.
- Later: a clear message on a blocked registration attempt, and an optional teacher action to reopen the account.
- Limitation: the restriction is by email, so a student can still register with a different email.

### 15.3 What authentication mechanism will DRF use? (decided)

Session authentication, as described in section 9.3. JWT is not used in the MVP. Revisit this only if a native mobile app or a central API host is added.

### 15.4 Assistants (decided for this round)

The `assistant` role exists in the `role` enum, but no permission class, endpoint, or test grants it anything this round. Wherever sections 7 and 9 say "teacher or permitted assistant", build the **teacher** check only. Assistant permissions are designed in a later round.

### 15.5 Public profile on the teacher's sub-domain (decided)

Before login, the teacher's sub-domain shows the **same public profile** as the main site: name, logo, headline, bio, about, published courses with prices, and the Sign up / Login actions. Course content (lessons, materials, exams) requires an approved student with an `active` enrollment.

Implementation: `GET /api/v1/workspaces/{slug}/public-profile/` uses the same serializer as `GET /api/v1/public/teachers/{slug}/`, but serves any active workspace, listed or not, because `is_listed` only controls directory visibility.

### 15.6 Student approval (decided)

Mandatory for every student in every workspace. There is no per-workspace setting.

### 15.7 Payments (decided)

- One platform currency; no per-workspace currency.
- The price is fixed at enrollment time: the server copies `courses.price` into `course_enrollments.price_at_enrollment`. Later price changes do not affect existing enrollments, and `payment_submissions.amount` is copied from that value, never from the client.
- Refunds and withdrawals happen outside the platform in this version. `withdrawn` exists as an enrollment status, but no refund workflow is built.
- The receipt retention period is not enforced this round. Receipts are stored privately and served only through the authorized endpoint. Allowed receipt files: JPEG, PNG, or PDF, at most 5 MB (configurable constants).
- If the platform ever takes a commission, online payment processing replaces manual confirmation.

### 15.8 Email verification (decided)

Not required this round. `email_verified` stays `false` and is not checked anywhere. The verify-email endpoint in 7.2 is not built.

### 15.9 Private URLs (decided)

The teacher/assistant login page path is `/teacher/login` (frontend, built later). The Platform Admin uses the Django admin at a non-default path set by `DJANGO_ADMIN_PATH` (default `platform-admin/`).

### 15.10 Separate accounts per teacher (decided)

This design uses separate accounts per teacher. If the team later wants one password across teachers, the alternative is a global `User` plus `Membership`, with sign-up and login still happening on the teacher's sub-domain.

### 15.11 Build-round decisions

- **Scope:** see "Build Scope for This Round" at the top of this document.
- **Process:** one git branch per stage, tests passing, and a human review before the next stage starts.
- **Environment:** PostgreSQL for everyone; configuration from environment variables with a committed `.env.example`. In development, emails go to the console and uploaded files go to a local private folder that is never served directly.
- **Tests:** Django's built-in test runner with DRF `APITestCase`; no extra test framework.
- **API docs:** `drf-spectacular`, with `GET /api/schema/` and `GET /api/docs/` enabled by an environment flag (on in development).

---

## Final Recommendation

> **Build round note:** the order below is superseded by section 14 and the Build Scope for this round. Items 4-8 are not built yet, except as the Stage 6 skeleton.

Implement the backend foundation in this order:

1. `workspaces` and the custom `users` model (workspace, role, `login_key`, approval state, and constraints).
2. `courses`, `course_sections`, `lessons`, and `lesson_assets`.
3. `course_enrollments` and `payment_submissions`.
4. `topics`, `lesson_topics`, `questions`, `question_topics`, `exams`, and `exam_questions`.
5. `ai_generation_jobs` and `ai_question_generations`.
6. `exam_attempts` and `answers`.
7. `performance_analyses`, `topic_weaknesses`, and `learning_recommendations`.
8. `proctoring_events` and `proctoring_evidence`.

The central lifecycle is:

**Admin creates teacher + workspace → teacher sets password and logs in at the private URL → teacher configures profile, payment instructions, and courses → student finds the teacher on the main site and reads the profile (bio, about, courses) → student clicks Sign up and registers on the teacher's sub-domain → teacher approves → student logs in and chooses a course → free: enrollment active; paid: student pays manually and submits proof → teacher confirms → enrollment active → content, quizzes, and results.**

Keep the public showcase, workspace-scoped authentication, student approval, enrollment, and payment confirmation as separate responsibilities. This makes the system easier to reason about, test, and extend.
