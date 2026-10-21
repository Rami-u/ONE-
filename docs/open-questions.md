# Open Questions

This file holds decisions the team has not made yet. It is not a task list and not the deferred list (those live in `memory.md` sections 9 and 11). When a question is closed, move the decision to `memory.md` section 8 (or to design section 15 if it changes the design) and delete the entry here.

## Q1 Rejected students

- **Status:** open
- **Question:** Should a rejected student be able to apply again?
- **Why it matters:** Today a rejected student cannot register again with the same email because the login key already exists, no endpoint reopens a review (review returns 409 for any student who is not pending), and rejected accounts are never deleted, so a rejection is permanent until someone edits the database.
- **Options:**
  - A) Rejection is final in this round and reopening is deferred
  - B) Add a teacher endpoint that reopens a rejected student as pending
  - C) Let a rejected student register again and become pending
- **Suggested answer:** A, recorded in `memory.md` section 8.
- **Who decides:** The three backend developers together.
- **Must be decided before:** Deployment (does not block Stage 5).
- **When closed:** -

## Q2 Shared cache backend for throttling

- **Status:** open
- **Question:** Which shared cache should production use?
- **Why it matters:** The default cache is per process, so throttle limits multiply by the number of workers.
- **Options:**
  - A) Django DatabaseCache with `python manage.py createcachetable` (no new dependency, documented in `README.md`)
  - B) Redis (needs the `redis` package, which needs approval under `AGENTS.md` section 4)
- **Suggested answer:** A.
- **Who decides:** The three backend developers together.
- **Must be decided before:** Deployment.
- **When closed:** -
