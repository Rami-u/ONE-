# Proctoring app contract

Owned by the AI teammate. Stage 6 registers this empty Django app only: no models, migrations, endpoints, evidence collection, or storage code are implemented.

The contracts below come from `docs/backend-design.md`. Each future table carries a required `workspace_id` foreign key with `PROTECT` and must validate workspace consistency across its relations.

- **5.22 `proctoring_events`:** Stores reviewable signals for an attempt and student. Required `attempt_id` references **`exam_attempts` in `apps/assessments`**; `student_id` references `users`. Fields include event type (`tab_switch`, `face`, `audio`, `copy`, and defined additions), severity (`info`, `warning`, `high`), indexed `occurred_at`, optional JSON details, review status (`pending`, `dismissed`, `violation`), and optional reviewer/time.
- **5.23 `proctoring_evidence`:** Belongs to a proctoring event through required `event_id`. Stores evidence type (`snapshot`, `video`, `screen`, `audio`), private `storage_key` (500 characters), optional MIME type/file size/retention deadline, and `created_at`. Evidence storage and access are deferred.

Section 1 policy: proctoring produces signals for staff review, never an automatic cheating verdict. AI output stays a reviewable draft until teacher approval; teachers decide whether to publish questions and how to interpret suspicious activity.
