# AI app contract

Owned by the AI teammate. Stage 6 registers this empty Django app only: no models, migrations, endpoints, AI calls, or background jobs are implemented.

The contracts below come from `docs/backend-design.md`. Each future table carries a required `workspace_id` foreign key with `PROTECT` and must validate workspace consistency across its relations.

- **5.11 `ai_generation_jobs`:** Tracks asynchronous question generation or analysis. Required `requested_by` references `users`; `job_type` is `question_gen` or `analysis`, and `status` is `queued`, `running`, `succeeded`, or `failed`. Provider/model/prompt metadata, token counters (default 0), estimated cost, error JSON, and creation/completion times describe the work.
- **5.14 `ai_question_generations`:** Links a required AI job, source lesson, and generated question, with an optional target exam. `created_at` records generation time; the question remains a reviewable draft.
- **5.19 `performance_analyses`:** One analysis per `exam_attempts` row, enforced by unique `exam_attempt_id`; optional `job_id` links its AI job. `overall_summary` stores performance/mistake feedback and `generated_at` records analysis time.
- **5.20 `topic_weaknesses`:** Links an analysis and topic, unique on `(analysis_id, topic_id)`. Stores attempted/correct counts, accuracy, and severity (`low`, `medium`, `high`, or `insufficient`).
- **5.21 `learning_recommendations`:** Belongs to an analysis; optional topic and lesson links identify suggested study material. Stores `recommendation_text` and `priority_order` (default 1).

Section 1 policy: AI output stays a reviewable draft until a teacher approves it. Proctoring produces signals for review, never an automatic cheating verdict; teachers make the final decisions.

`exam_attempts`, owned by `apps/assessments`, is the table future proctoring events will reference. It is also the attempt table used by performance analyses.
