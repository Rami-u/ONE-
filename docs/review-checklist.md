# Review Checklist

The reviewer is one of the three backend developers and is never the reviewer of the previous stage.
The reviewer does the mutation checks and probes by hand and does not rely on the agent's report.

## Before you start

- [ ] The branch is named `stage-<n>-<short-name>` and has no commits on `main`.
- [ ] Commits are small and clearly named.
- [ ] Earlier stages are untouched (no changes to committed migrations).
- [ ] `requirements.txt` has no new dependency that was not approved.
- [ ] Nothing from a later stage is included.

## Run it

Run from `backend/` on a clean PostgreSQL database:

- [ ] `python manage.py check`
- [ ] `python manage.py makemigrations --check --dry-run`
- [ ] `python manage.py spectacular --validate` (no warnings)
- [ ] `python manage.py test`

## Try to break it by hand

- [ ] Mutation check every security or business rule added in the stage (remove the rule temporarily, a test must fail, restore it, end with a clean git diff).
- [ ] Each validation check needs its own test case, and values exactly at the limits must be tested as accepted.
- [ ] Rules hidden behind another layer (for example a mixin) need a direct test of the permission class with a stub view.
- [ ] Probes with an unknown email, a logged-in user, a user from another workspace (including guessed IDs), and invalid input (must be 400, never 500).
- [ ] Email failure does not break the request.

## In the browser

- [ ] Open `/api/docs/`, confirm it loads, and try the new endpoints, including an unsafe request that needs CSRF (for example approve) which must return 200. Tests cannot catch JavaScript problems.

## Docs and memory

- [ ] `README.md` is updated for the stage.
- [ ] `backend/.env.example` lists any new variable.
- [ ] The `memory.md` diff updates the stage row, the repository map, the building blocks and the decisions list, and matches the code.
- [ ] `memory.md` contains no machine-specific paths.
- [ ] `memory.md` is still under about 200 lines.
- [ ] No secrets and no `.env` are committed.
- [ ] Any new folder the app writes to is in `.gitignore`.

## Merge

- [ ] Use a merge commit (not squash).
- [ ] Record your name in the Reviewer column of the status table in `memory.md`.
