# PRODUCTION_PLAN.md — Vision Proctoring: Prototype → Production-Ready

> **Audience:** an AI coding agent (Antigravity) working in this repo, supervised by a human (Omar).
> **Goal:** harden the existing `cheat-vision` pipeline so it is correct, measurable, scalable, observable and privacy-aware.
> **Non-goal:** training/fine-tuning a model. The three core signals use pretrained MediaPipe + rules. Training is only considered in Phase 9 and only after a human gate.

---

## 0. How to run this plan (read first)

- Execute **one phase per task/conversation**. Finish its acceptance checks, summarise, then **stop and wait for human review** before starting the next phase.
- Prefer review-driven autonomy: ask for approval before running destructive commands, installing packages, or touching files outside the paths listed in each phase.
- Commit after each phase with message `phase-N: <title>`. Never rewrite history.
- Never invent numbers. Every latency, precision, recall or capacity figure in a report must come from a command you actually ran. If something cannot be run (no webcam, no clips, no Redis), say so explicitly and mark the item `BLOCKED (reason)` instead of guessing.
- Never change a detection threshold (yaw/pitch/durations) without evaluation output that justifies it. Record the before/after table in `docs/CHANGELOG.md`.

### Suggested first prompt
> Read `PRODUCTION_PLAN.md` fully. Summarise the repo state against Section 1 and list any mismatch. Then execute **Phase 1 only**, run its acceptance checks, and stop.

---

## 1. Context you must respect

**Environment:** Windows, PowerShell, Python 3.11, virtualenv at `.venv`. Activate with `.\.venv\Scripts\Activate.ps1`. Run Python modules from the repo root (`python -m ...`), never `cd` into subfolders.

**Repo layout (existing):**
```
backend/vision/   __init__.py  face_landmarker.task  probe.py  face_detector.py
                  head_pose.py  pipeline.py  phone_detector.py
evaluation/       clips/  labels.csv  evaluate.py  record_and_benchmark.py
```

**Vision Contract v1 (DO NOT BREAK):**
`analyze_frame(image_bytes: bytes, timestamp: float) -> dict` with keys exactly:
`face_count:int, head_yaw:float|None, head_pitch:float|None, looking_away:bool, phone_detected:bool`.
Frames arrive as JPEG every 1–2 s per student via `POST /api/sessions/{id}/frames/`.

**Event rules (defaults):** `face_missing` ≥ 3 s, `multiple_faces` ≥ 2 s, `looking_away` ≥ 3 s, `phone_detected` ≥ 1 s (stub returns False).

**Contract change in this plan (v1 → v1.1):** events become lifecycle records with fields
`type, status("opened"|"closed"), start_time, end_time, duration, confidence, snapshot_path, config_version`.
`confidence` is the share of samples in the run that matched — it is **not** a model probability and must never be described as one. This change must be documented in `docs/CONTRACT.md` (Phase 10) so the Backend owner (Gawish) can adapt.

**Ownership:** do not modify anything outside `backend/vision/`, `evaluation/`, `tests/`, `docs/`, and root packaging files unless a phase explicitly says so. The Django/FastAPI backend code belongs to another teammate: provide an integration doc, do not edit it.

**Hard rules**
1. Do not install both `opencv-python` and `opencv-python-headless` in the same environment. Runtime = headless. Dev tools that call `cv2.imshow` (`probe.py`) use a separate dev requirements file.
2. Do not store raw frames, landmarks, or video on the server. Only the single snapshot attached to an opened event may be persisted (Phase 8).
3. Do not use MediaPipe blendshapes or any signal to infer emotions or "suspicious expressions". Out of scope and legally risky.
4. Do not pick or add Ultralytics/YOLO without the Phase 9 human sign-off (AGPL-3.0 licensing).
5. Timestamps used for event logic must be **server receive time**, never client-provided.

---

## Phase 1 — Integrate EventBuilder v2 (correctness)

**Why:** v1 `EventBuilder` was verified to fail three ways: a flickering face (3 missing, 1 detected, repeating over 12 s) produced zero events; a 60 s network gap produced a phantom 60 s event; and the final duration of a 10 s violation was never delivered after the event was emitted at 3 s.

**Expected inputs:** `event_builder_v2/backend/vision/event_builder.py` and `event_builder_v2/tests/test_event_builder.py` supplied by the human. If they are missing, implement them from the spec below and tell the human.

**EventBuilder v2 spec**
- Table-driven `Rule(min_duration_s, predicate, tolerance_samples=1, min_samples=2)`.
- A run starts at the first matching sample. It tolerates up to `tolerance_samples` consecutive non-matching samples; one more closes it.
- An event is **opened** when `matches >= min_samples` and `last_match - start >= min_duration_s`. Duration = `last_match - start`.
- On close, emit a `closed` record with final duration; runs that never opened are discarded silently.
- If `timestamp - last_ts > max_frame_gap_s` (default 5.0): close all runs at their last evidence, record the gap in `builder.gaps`, and do **not** count the gap as violation time.
- Frames with `timestamp <= last_ts` are ignored.
- `flush()` closes everything (session end). `builder.events` holds closed events only.

**Tasks**
- [ ] Place `event_builder.py` in `backend/vision/` and the tests in `tests/`.
- [ ] In `pipeline.py`: delete the old `EventBuilder` and `ProctoringEvent`; import from `.event_builder`. Keep `analyze_frame` untouched.
- [ ] `process_session_frame(...)` returns `{"signals": ..., "events": [lifecycle records]}`; add `finish_session(session_id) -> list[event]` that calls `flush()`, clears state and returns the closing events. Keep `clear_session_state` as a thin alias that does **not** drop open events silently (it must call `finish_session`).
- [ ] Update `__init__.py` exports accordingly.
- [ ] Update `evaluation/evaluate.py`: call `builder.flush()` at the end of each clip, read `builder.events`, and **sample using timestamps** exactly as before (1 frame/s default). Add a CLI flag `--interval` (default 1.0) so 2 s sampling can be evaluated too.

**Acceptance checks**
```powershell
python -m pytest -q                      # all green, includes the 11 EventBuilder tests
python -c "import backend.vision as v; print(sorted(v.__all__))"
python -m evaluation.evaluate            # runs without error on existing clips (or reports 'no clips')
```

---

## Phase 2 — Pipeline hardening (input safety, config, determinism)

**Tasks**
- [ ] `backend/vision/config.py`: dataclass `VisionConfig` with thresholds (yaw, pitch up/down), event rules, `max_frame_gap_s`, `max_image_bytes` (default 1_000_000), `max_image_side` (default 1920), `num_faces`, `config_version`. Load overrides from env vars prefixed `VISION_`. `head_pose.py` and `EventBuilder` read from it; module-level `DEFAULT_*` constants stay as backward-compatible aliases.
- [ ] `decode_image_bytes`: reject empty, oversize (bytes) and oversize (pixels) input **before** full decode where possible (check size first; check dimensions right after decode and downscale to `max_image_side`). Raise a dedicated `InvalidFrameError(ValueError)`.
- [ ] Thread-safe lazy init of the landmarker (`threading.Lock`, double-checked).
- [ ] Main-face selection: when `face_count >= 2`, compute head pose for the **largest face by landmark bounding box** (tie-break: closest to image center), not `matrices[0]`. Add a unit test with synthetic landmark objects.
- [ ] Model integrity: `scripts/fetch_model.py` downloads `face_landmarker.task`, writes `backend/vision/face_landmarker.task.sha256`, and `get_landmarker()` verifies the hash at startup (fail loudly on mismatch). Tell the human to confirm the download URL against the official MediaPipe Face Landmarker page — you cannot verify provenance yourself.
- [ ] Pose sanity: assert pitch/yaw are normalised to `[-180, 180]` and add a test that a rotation matrix near the ±180° pitch wrap does not produce false `looking_away`. Do not guess axis signs: leave signs as-is and add a `# VERIFIED-ON-WEBCAM` marker that the human fills in after checking with `probe.py`.

**Acceptance checks**
```powershell
python -m pytest -q
python scripts/fetch_model.py            # prints the SHA256 it pinned
python -c "from backend.vision.pipeline import analyze_frame; print(analyze_frame(b'', 0.0))"   # must raise InvalidFrameError, not crash the process
```

---

## Phase 3 — Session state that survives multiple workers

**Problem:** `_session_builders` is an in-process dict. With >1 worker process, frames of one student land on different workers and each starts from zero; restarts lose all state; abandoned sessions leak memory.

**Tasks**
- [ ] `backend/vision/session_store.py` with an abstract `SessionStore` (`load(session_id) -> EventBuilder`, `save(session_id, builder)`, `delete(session_id)`), plus `InMemorySessionStore` (with TTL eviction, default 2 h idle) and `RedisSessionStore` (optional import, TTL via `EXPIRE`).
- [ ] Add `EventBuilder.state_dict()` / `EventBuilder.from_state(state, rules, config)` serialising **only runtime state** (`_runs`, `_last_ts`, `gaps`, `events`) — rules contain lambdas and must not be serialised.
- [ ] Per-session lock so two frames of the same session are never processed concurrently (in Redis: a short `SET NX PX` lock; in memory: `threading.Lock` per id). If the lock cannot be acquired within 500 ms, drop the frame and count it in metrics.
- [ ] Select the store via `VISION_SESSION_STORE=memory|redis` and `VISION_REDIS_URL`.
- [ ] Tests: round-trip serialisation equals original behaviour; TTL eviction; concurrent same-session frames never interleave (use threads). For Redis use `fakeredis` in tests (dev dependency); mark live-Redis tests `@pytest.mark.integration` and skip when unavailable.

**Acceptance checks**
```powershell
python -m pytest -q
python -m pytest -q -m integration       # only if a Redis is reachable; otherwise report BLOCKED
```
**Doc note (docs/CONTRACT.md):** alternative to Redis is sticky routing by `session_id` at the load balancer; describe both, recommend one, let the human decide.

---

## Phase 4 — Concurrency model and load test

**Do not assume thread-safety or thread scaling.** Measure.

**Tasks**
- [ ] `evaluation/bench_concurrency.py`: on a fixed set of N JPEG frames, measure throughput (frames/s) for (a) 1 thread, (b) 4 threads sharing one landmarker, (c) 4 processes each with its own landmarker. Output a table and write it to `docs/benchmarks/concurrency_<date>.md`. State the machine (CPU model, cores) in the report.
- [ ] `backend/vision/worker.py`: a `ProcessPool`-based `FrameWorker` (each worker initialises its own landmarker once, with a warm-up call) exposing `submit(session_id, image_bytes, server_ts) -> Future`. Use whichever model the benchmark supports; justify the choice in the report.
- [ ] Backpressure: bounded queue; if a frame has waited longer than `max_frame_age_s` (default 4 s) when a worker picks it up, **drop it** and increment `frames_dropped_stale`. Stale frames must never reach the EventBuilder.
- [ ] `evaluation/load_test.py`: simulate `--students N --interval 2.0 --duration 120` replaying real clips (or synthetic frames), report p50/p95/p99 end-to-end latency, drop rate, and the maximum N where p95 stays under 2 s on this machine.
- [ ] Add a capacity formula to the report: `required_cores ≈ students / interval × measured_ms / 1000 × safety_factor(2)`, filled with the measured numbers.

**Acceptance:** the three reports exist with real numbers; no figure appears that was not produced by the scripts.

---

## Phase 5 — Evaluation that means something

**Agent tasks**
- [ ] Extend `evaluation/evaluate.py` to output, per event type: TP/FP/FN, precision, recall, **false alarms per student-hour** (FP ÷ total evaluated video hours), and per-clip breakdown to `evaluation/reports/<timestamp>.json` and a readable `.md`.
- [ ] Add optional `group` column support in `labels.csv` (`lighting`, `glasses`, `headscarf`, `camera_angle`, `skin_tone_bucket`, `device`) and report metrics **per group** so weaknesses are visible. If the column is absent, skip silently.
- [ ] `evaluation/gates.yaml` with minimum recall and maximum false-alarms/hour per event type (values left as `TODO_SET_BY_HUMAN`); `python -m evaluation.evaluate --check-gates` exits non-zero when a gate fails or a gate is unset.
- [ ] Add a sensitivity sweep script: re-run evaluation over a grid of `yaw_threshold` and `pitch_down_threshold` values and print the trade-off table (do **not** auto-apply any value).

**Human-only tasks (agent must list them in its final summary, not attempt them)**
- Record at least 20 clips from at least 8 different people covering: normal exam posture, writing on paper, looking at a second screen, leaving the frame, a second person entering, bad/low light, glasses, headscarf, low camera angle, cheap webcam.
- Fill `labels.csv` with ground truth (start/end seconds) and the `group` columns.
- Choose gate values after seeing the sweep output.

---

## Phase 6 — Packaging and deployment

**Tasks**
- [ ] Split dependencies: `requirements.txt` (runtime: `mediapipe`, `opencv-python-headless`, `numpy`, optional `redis`) and `requirements-dev.txt` (`-r requirements.txt` minus headless + `opencv-python`, `pytest`, `fakeredis`, `pyyaml`). Pin exact versions from the currently working environment; document in README that dev and runtime must use separate virtualenvs because of the OpenCV packages.
- [ ] `Dockerfile` (python:3.11-slim, non-root user, runtime requirements only, model fetched and hash-verified at build time) and `.dockerignore` (exclude `.venv`, `evaluation/clips`, `.git`).
- [ ] `backend/vision/health.py`: `healthcheck()` that loads the landmarker, runs one inference on a bundled tiny test image and returns latency; usable as a container HEALTHCHECK and by the backend `/health` route.
- [ ] Warm-up on process start so the cold-start latency is not paid by the first student.
- [ ] CI workflow (`.github/workflows/ci.yml`): install runtime+dev, run `pytest`, run `python -m evaluation.evaluate --check-gates` only if `evaluation/clips` is present in CI (otherwise skip with a visible notice).

**Acceptance checks**
```powershell
docker build -t cheat-vision .           # if Docker unavailable: BLOCKED, do not fake
docker run --rm cheat-vision python -c "from backend.vision.health import healthcheck; print(healthcheck())"
```

---

## Phase 7 — Observability

**Tasks**
- [ ] `backend/vision/metrics.py`: counters/histograms (use `prometheus_client` if present, otherwise a tiny in-process fallback with a `snapshot()` dict): `frames_total`, `frames_invalid`, `frames_dropped_stale`, `frames_dropped_lock`, `inference_ms` (histogram), `face_detect_rate`, `events_opened_total{type}`, `session_gaps_total`.
- [ ] Structured JSON logging with `session_id`, `event_type`, `latency_ms`, `config_version`, `model_sha256_prefix`. **Never log image bytes, landmarks, or filenames containing student names.**
- [ ] `docs/RUNBOOK.md`: what each metric means, suggested alert thresholds as **starting points to tune**, and first-response steps for: high drop rate, spike in `face_missing` (likely a camera/lighting or client bug), spike in `session_gaps_total` (network), latency regression.

**Acceptance:** unit test asserts that processing a frame increments the expected metrics and that logs contain no byte payloads.

---

## Phase 8 — Privacy-by-design implementation

> This phase implements technical controls only. It is **not legal advice**; legal items are listed for the human in Phase 11.

**Tasks**
- [ ] `backend/vision/snapshot_store.py`: save exactly one JPEG snapshot when an event is **opened** (never for ordinary frames), path pattern `snapshots/<session_id>/<event_id>.jpg`, written with restrictive permissions, optional encryption at rest using `cryptography.fernet` when `VISION_SNAPSHOT_KEY` is set (key never committed, never logged).
- [ ] `purge_expired_snapshots(max_age_days)` + CLI `python -m backend.vision.snapshot_store --purge`; default retention is `TODO_SET_BY_HUMAN` and the CLI refuses to run until it is set.
- [ ] Verify by test that no code path writes full frames, landmark arrays, or video files to disk (grep-based test over `backend/vision/` for `imwrite`, `VideoWriter` outside the snapshot store and the dev-only `record_and_benchmark.py`).
- [ ] Add `docs/PRIVACY_NOTES.md`: data inventory (what is processed, what is stored, for how long), data flow diagram in Mermaid, and the list of controls above.

**Acceptance checks**
```powershell
python -m pytest -q
python -m backend.vision.snapshot_store --purge     # must refuse with a clear message while retention is unset
```

---

## Phase 9 — Phone detection (STRETCH, gated)

**Do not start until Phases 1–5 pass and the human writes `APPROVED: phase-9` in the task.**

**Tasks**
1. Baseline first: evaluate a **pretrained** COCO-class detector on the existing clips, `cell phone` class only, no training. Report precision/recall and false alarms/hour for `phone_detected`.
2. **STOP and ask the human to choose the detector family.** Present options with licence implications: Ultralytics YOLO models and any model fine-tuned from them are AGPL-3.0 unless an Enterprise licence is bought (relevant because the product is planned as a commercial SaaS); alternatives with permissive licences must be checked by the agent on their official pages and listed with source links. Do not install anything before the human answers.
3. Only if the baseline is inadequate **and** the human approves: prepare a fine-tuning plan (dataset sources and their licences, labelling tool, train/val/test split by *person* not by frame, evaluation on clips never seen in training) as a document first, and wait for approval before any training.
4. Wire the detector behind `detect_phone(frame_bgr)` keeping the stub as the default when `VISION_PHONE_DETECTOR=off`.

---

## Phase 10 — Documentation and handoff

**Tasks**
- [ ] `docs/CONTRACT.md`: Vision Contract v1.1 — signals, lifecycle event schema with a JSON example for `opened` and `closed`, the server-timestamp requirement, session start/finish calls, error behaviour (`InvalidFrameError` → HTTP 422 suggestion), and a migration note from v1.
- [ ] `docs/INTEGRATION_FOR_BACKEND.md`: exact call sequence for the backend (per frame; on session end call `finish_session`), idempotency advice (insert on `opened`, update on `closed`), and example payloads.
- [ ] `docs/LIMITATIONS.md` (must be shown to customers): head pose is not gaze; a student can look at a second screen without turning the head; no liveness detection (a photo or looped video would pass); virtual cameras are not detected; looking down may be legitimate note-taking; results are indicators for human review, never proof.
- [ ] `README.md`: setup (separate dev/runtime envs), commands for tests, probe, evaluation, load test, Docker.
- [ ] `docs/CHANGELOG.md`: every threshold or behaviour change with its evidence.

---

## Phase 11 — Human gates (the agent must print this checklist at the end and NOT mark items done)

- [ ] Verify head-pose axis signs on a real webcam with `probe.py` and fill the `VERIFIED-ON-WEBCAM` markers.
- [ ] Record and label the diverse clip set (Phase 5) and set `gates.yaml`.
- [ ] Decide retention period and snapshot encryption key management.
- [ ] Legal review before any real exam: Egypt's Personal Data Protection Law (biometric data is sensitive; written explicit consent and licensing from the Personal Data Protection Center are involved, and cross-border transfer needs a licence, so hosting location matters). Check Gulf-country laws for target markets. If EU customers are possible, proctoring falls under high-risk systems in the EU AI Act and emotion inference in education is prohibited; confirm applicable dates.
- [ ] Human-in-the-loop policy: flags go to a teacher who decides; no automatic penalties.
- [ ] Rollout: shadow mode (flags recorded, not shown) → pilot with one class, teacher feedback labelled correct/incorrect → wider release.
- [ ] Phase 9 licence decision.

---

## Definition of Done (production-ready candidate)

1. `python -m pytest -q` is green; EventBuilder v2 scenarios (flicker, 60 s gap, lifecycle, reorder) covered.
2. Contract v1.1 documented and the Backend owner has acknowledged the change.
3. Input validation, size limits, model-hash verification and the thread-safe init are in place.
4. Session state works across multiple workers (Redis or sticky routing decision recorded).
5. Concurrency and load-test reports exist with measured numbers and a stated capacity per machine type.
6. Evaluation report with false alarms per student-hour, per-group metrics, and passing gates set by a human.
7. Docker image builds, health check works, CI runs tests.
8. Metrics and structured logs exist; no frames, landmarks or filenames with PII appear in logs.
9. Only event snapshots are stored, with retention and optional encryption; `LIMITATIONS.md` and `PRIVACY_NOTES.md` exist.
10. All Phase 11 human gates are ticked **by a human**.
