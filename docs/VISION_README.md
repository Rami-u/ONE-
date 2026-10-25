# Cheat Vision: Beginner’s Handbook

> **Project status:** experimental vision-proctoring component. This guide describes the code and evidence currently present in the workspace; it is not a claim that the system is production-ready.
>
> **How to read status labels:** ✅ Confirmed means visible in the repository or supported by a recorded run. 🧪 Assistant sandbox means an exploratory test result, not a production benchmark. ❓ Unconfirmed means it still needs a deliberate check.

## 0. Who this guide is for

This handbook is for someone new to Python, computer vision, and this repository. You can follow it from setup through a webcam experiment, then use the glossary and exercises as a reference. Commands use Windows PowerShell and assume the project folder is `D:\cheat-vision`.

The current vision demo runs Python inference on the server-side process. A longer-term product could move some inference into a browser, but that is a separate architecture decision. This guide documents the code that exists now, not a promised delivery schedule.

The supplied planning files describe different scopes. The project plan discusses a broader platform and browser-side direction; the one-month plan describes a server-side Python demo. This handbook follows the current Python vision repository and does not attempt to reconcile or enforce the plans’ timelines.

This project can produce signals such as face count, head pose, and whether the configured pose threshold is crossed. Those signals are not proof of cheating, intent, or misconduct. They require human interpretation and careful validation.

## 1. The project in ten lines

1. A client or test script provides a compressed image frame.
2. The backend checks the input size and decodes the image.
3. MediaPipe Face Landmarker estimates face landmarks.
4. The code selects a main face and estimates head yaw and pitch.
5. Thresholds turn pose into a `looking_away` signal.
6. `phone_detected` currently always returns `False`; phone detection is a stub.
7. `EventBuilder` turns repeated frame signals into event intervals.
8. Evaluation compares those intervals with manually entered time labels.
9. Reports show counts and metrics for the small set of available clips.
10. Current results are experiments, not validated production accuracy or capacity.

## 2. Big picture

### 2.1 The data path

```mermaid
flowchart LR
    A[Webcam or video] --> B[Frame as JPEG bytes]
    B --> C[Input validation and decode]
    C --> D[Face landmarks]
    D --> E[Main face selection]
    E --> F[Yaw and pitch estimate]
    F --> G[Per-frame signals]
    G --> H[EventBuilder]
    H --> I[Event intervals]
    I --> J[Compare with labels]
    J --> K[JSON and Markdown report]
```

### 2.2 A simple picture

```text
camera/video
    |
    v
JPEG frame -> validate/decode -> face landmarks -> pose -> signals
                                                       |
                                                       v
labels.csv <- compare <- report <- event intervals <- EventBuilder
```

The webcam/video is the source. The pipeline measures one frame at a time. The event builder adds time and persistence: a single noisy frame should not automatically become a long event. The evaluator then compares predicted intervals with reference intervals that a person entered in `evaluation/labels.csv`.

### 2.3 Two different kinds of truth

The vision output is a **prediction**. A label is a **human reference annotation** for an interval in a clip. Agreement between them on a small clip set is useful for finding bugs, but it does not establish general accuracy. Labels can also be wrong or incomplete, so record what was actually visible and how the clip was staged.

## 3. Learning path

You do not need to learn all of computer vision before trying the demo. Work in small steps and keep each run reproducible.

### Level 0 — Navigate the project

Learn PowerShell basics: `cd`, `dir`, `Get-ChildItem`, and running `python -m ...` from the repository root. Know which Python environment is active before installing packages.

### Level 1 — Python basics

Learn variables, dictionaries, functions, imports, exceptions, and virtual environments. Signals are ordinary Python dictionary values. A function such as `analyze_frame(...)` accepts an input and returns a dictionary.

### Level 2 — Images and video

An image is an array of pixel values. Video is a sequence of frames plus timing information. A JPEG is a compressed representation of an image; OpenCV decodes it into a NumPy array for processing.

### Level 3 — Learn the output contract

Run a probe and inspect `face_count`, `head_yaw`, `head_pitch`, `looking_away`, and `phone_detected`. A `None` pose generally means the pipeline did not produce a usable face pose for that frame.

### Level 4 — Understand thresholds and time

Read `backend/vision/config.py` and `backend/vision/event_builder.py`. A frame-level threshold and an event-duration threshold are different: the first says a frame crossed a boundary; the second says the condition persisted long enough to count as an event.

### Level 5 — Record and label clips

Record a normal baseline and one staged behavior at a time. Then annotate time intervals in `evaluation/labels.csv`. Use a fresh filename because the recording tool may remove an existing file with the same output name.

### Level 6 — Evaluate and inspect errors

Run the evaluator. Inspect per-clip results and the saved report, not just the summary. A false positive may be caused by a bad label, an unexpected face loss, a threshold, or a code defect; the summary alone cannot tell which.

### Level 7 — Change one thing at a time

Make a change, rerun the relevant checks, compare reports, and document what changed. Do not tune on a clip and then describe that same clip as an independent validation set.

### Minimum viable path

1. Open PowerShell in `D:\cheat-vision`.
2. Activate `.venv`.
3. Run the automated test suite.
4. Run the webcam probe and verify the camera and pose display.
5. Record a fresh, short normal clip.
6. Add a label row for that clip.
7. Run evaluation and inspect the generated report.
8. Record one staged event and repeat, keeping the normal clip as a baseline.

## 4. Glossary

1. **Array:** Ordered values; an image is commonly represented as a height-by-width-by-channel array.
2. **Backend:** Server-side code that handles requests or performs processing.
3. **Bounding box:** Rectangle around a detected object or face.
4. **Camera frame:** One image captured from a video stream.
5. **Channel:** One component of a pixel, such as blue, green, or red.
6. **Cold start:** First run after initialization, when models and workers may need loading.
7. **Confidence:** A score indicating model certainty. In this project, an event’s confidence is a signal-match proportion, not a calibrated probability that misconduct occurred.
8. **Contract:** Agreed input/output shape between components.
9. **Decode:** Convert compressed image bytes into an image array.
10. **Event:** A time-bounded condition inferred from a sequence of frame signals.
11. **Event interval:** The start and end times for an event.
12. **False alarm:** A predicted event without a corresponding reference label under the evaluator’s matching rules.
13. **False negative (FN):** A reference event that the system did not match.
14. **False positive (FP):** A predicted event not matched to a reference event.
15. **Face landmark:** A point estimated on a face, such as a point near an eye or mouth.
16. **Face count:** Number of faces detected in a frame, as returned by the pipeline.
17. **Frame interval:** Time between adjacent video frames. In a 20 FPS recording, the nominal interval is 0.05 seconds.
18. **Frame rate (FPS):** Frames per second.
19. **Ground truth/reference label:** Human annotation used for comparison; it is not automatically perfect.
20. **Head pitch:** Approximate up/down head rotation.
21. **Head yaw:** Approximate left/right head rotation.
22. **Inference:** Applying a trained model to data to obtain an estimate.
23. **Integration test:** A test that checks multiple components working together, sometimes with an external service.
24. **JPEG:** A common compressed image format.
25. **Latency:** Time taken for an operation to finish.
26. **Landmarker:** A model or component that estimates key points on an object.
27. **Label:** A manually entered event category and time interval for a clip.
28. **Main face:** The face chosen for pose estimation when multiple faces are present.
29. **MediaPipe:** Google’s framework used here for face landmark inference.
30. **Metric:** A number summarizing model or system behavior.
31. **Model:** Learned parameters plus associated inference logic.
32. **NumPy:** Python library used for numerical arrays.
33. **OpenCV:** Library used here for image/video I/O and image operations.
34. **Precision:** Of predicted events, the fraction that matched a reference event: TP / (TP + FP).
35. **Process pool:** A group of worker processes that can handle jobs concurrently.
36. **Recall:** Of reference events, the fraction that were detected: TP / (TP + FN).
37. **Redis:** Optional external data store that can share session state across processes or machines.
38. **Signal:** A per-frame output such as `face_count` or `looking_away`.
39. **Singleton:** One shared instance created and reused inside a process.
40. **Stale frame:** A frame too old to be useful when it reaches a worker.
41. **Threshold:** Boundary used to turn a numeric measurement into a decision.
42. **True positive (TP):** A predicted event matched to a reference event.
43. **TTL:** Time to live; duration after which stored data may expire.
44. **Virtual environment:** A project-specific Python package environment.
45. **Warm-up:** Initial work that loads and exercises a model before measuring steady-state behavior.

## 5. How the pipeline works

### 5.1 From JPEG bytes to signals

The pipeline receives bytes, checks configured limits, decodes them with OpenCV, and may resize an oversized frame to a maximum side length. MediaPipe estimates face landmarks. The face selector chooses a main face using face size and a center-based tie-break. The pose code derives yaw and pitch from selected landmark geometry. Configuration thresholds then determine whether the pose counts as looking away.

The returned dictionary follows this contract:

```python
{
    "face_count": 1,
    "head_yaw": 4.2,
    "head_pitch": -3.1,
    "looking_away": False,
    "phone_detected": False,
}
```

Those numbers are only an illustration of the shape, not a benchmark or a promise about a particular camera. If the pose cannot be estimated, yaw and pitch can be `None`.

### 5.2 Why separate frames and events?

Think of a frame signal as a thermometer reading. `EventBuilder` is a rule that asks whether the reading stayed above a boundary long enough to matter. It handles brief gaps and produces an `opened` record and a later `closed` record. The current configuration includes minimum durations for event categories and a maximum tolerated gap. A gap larger than the configured maximum closes a run using the last known evidence.

Event timestamps must move forward. Duplicate or older timestamps are ignored. `finish_session`/flush closes any still-open event at the end of the clip or session.

### 5.3 Why?

This separation makes noisy frame-by-frame estimates easier to reason about. It also lets the evaluator compare meaningful intervals rather than count every frame as a separate incident.

### 5.4 Common mistake

Treating a single `looking_away=True` frame as proof of a sustained event. Also, a missing face is not the same as a detected face looking away. A strong head turn may cause face detection to fail; inspect the actual `face_count` and pose sequence.

### 5.5 Check yourself

If a pose is unavailable for one frame, should you invent yaw and pitch values? **Answer:** No. Preserve the missing/unknown state and let the event logic handle missing evidence according to its configured gap behavior.

## 6. Technology choices and model training

### 6.1 Why these tools?

- **Python** lets the demo connect image processing, inference, session logic, and evaluation in one codebase.
- **OpenCV** handles webcam/video capture, image decoding, resizing, and encoding.
- **MediaPipe Face Landmarker** supplies face landmarks used for approximate pose estimation.
- **NumPy** supports the numerical operations around images and geometry.
- **pytest** runs automated checks.
- **CSV and Markdown/JSON** make labels and reports easy to inspect.
- **Redis (optional)** can share session state outside a single Python process; the repository’s in-memory mode is easier for local experiments.
- **ProcessPoolExecutor** gives workers separate processes for inference isolation and concurrency experiments.

These are implementation choices visible in the repository, not a statement that they are the only or best choices for every deployment.

### 6.2 Why no fine-tuning yet?

The current face model is used as an existing landmark model. The project does not currently have a representative, consented, well-annotated training set for phone detection or for proving any behavioral interpretation. Fine-tuning without suitable data and a clear evaluation split risks creating a model that memorizes the recordings rather than working in new conditions.

The `phone_detector.py` implementation is explicitly a stub: it returns `False`. A phone-related metric with zero events therefore says nothing about detector quality. Selecting a detector, verifying its license and provenance, collecting data, and defining an evaluation plan remain work to do.

### 6.3 Human checks still needed

Head-pose signs and thresholds depend on camera placement, subject position, and lighting. Verify them with a controlled probe on the actual webcam. The code’s angle signs are not a universal coordinate convention. Do not rely on a guessed yaw/pitch direction without observing it.

## 7. The baseline files

The prompt’s original baseline list covers the core vision path. The workspace now includes more files than that list, so this section explains the core files first and then the additions. “Baseline” here means the project’s working foundation, not a guarantee that every feature is complete.

### 7.1 Ten core files

1. **`backend/vision/__init__.py`** — Exposes the public vision functions and event/session helpers so callers can import a stable package interface.
2. **`backend/vision/probe.py`** — Opens a webcam or video for a human-facing live probe, showing the image and pose information. Use it to inspect behavior, not to establish accuracy by itself.
3. **`backend/vision/face_detector.py`** — Selects the main face from detected faces. It uses face area and a center-based tie-break; a prior floating-point tie issue was fixed by quantizing area comparisons.
4. **`backend/vision/head_pose.py`** — Estimates yaw and pitch from landmarks and applies the configured pose boundaries. Webcam direction/sign behavior still needs explicit human verification.
5. **`backend/vision/pipeline.py`** — Validates and decodes frames, calls the face landmarker and pose logic, and returns the fixed signal contract. It verifies the model asset hash during setup.
6. **`backend/vision/phone_detector.py`** — Placeholder interface for phone detection. It currently always returns `False` and must not be treated as a working detector.
7. **`backend/vision/config.py`** — Loads and validates thresholds and limits, including environment overrides such as `VISION_*` values. Defaults include yaw 30°, pitch up 25°, pitch down −25°, a 5-second maximum frame gap, and image size limits.
8. **`backend/vision/event_builder.py`** — Converts ordered frame signals into event open/close intervals, tolerating configured sample gaps and flushing remaining events at session end.
9. **`backend/vision/session_store.py`** — Provides in-memory session state and optional Redis-backed state, including TTL and session locking support. Live Redis behavior has not been confirmed here.
10. **`backend/vision/worker.py`** — Runs inference in a process pool with child initialization/warm-up, a bounded submission queue, and stale-frame dropping.

### 7.2 Evaluation, tests, and operations files

- **`evaluation/labels.csv`** — Human event intervals. A row associates a clip with a category and start/end seconds. This file needs consistent annotations; missing labels mean the evaluator cannot treat a clip as a complete reference.
- **`evaluation/evaluate.py`** — Runs labeled clips through the pipeline and event logic, then reports TP/FP/FN, precision, recall, and false alarms per video-hour. It writes JSON and Markdown reports.
- **`evaluation/record_and_benchmark.py`** — Captures webcam video and samples inference timing/signals. It can delete/replace an existing output path, so always choose a unique output filename.
- **`evaluation/bench_concurrency.py`** — Exercises concurrent worker behavior for capacity exploration.
- **`evaluation/load_test.py`** — Runs a load scenario and records completion/drop/latency behavior.
- **`evaluation/sensitivity_sweep.py`** — Explores threshold combinations against the current evaluation data; it does not automatically make a chosen threshold correct.
- **`evaluation/gates.yaml`** — Holds evaluation gate settings used by the evaluation workflow.
- **`scripts/fetch_model.py`** — Fetches the model asset used by the pipeline. The code verifies a SHA value, but independently re-check the source and provenance before production.
- **`requirements.txt`** — Python package declarations. It currently contains both `opencv-python` and `opencv-contrib-python` declarations, which is a packaging cleanup item; avoid separately layering both into a new environment without resolving that conflict.
- **`pytest.ini`** — Pytest configuration, including the integration marker.
- **`tests/`** — Unit and integration checks for event logic, pipeline hardening, session storage, and evaluation behavior. One Redis-related test is skipped when its external service is not available.
- **`docs/CONTRACT.md`** — Human-readable contract documentation.
- **`docs/PRODUCTION_PLAN.md`** — Planning and remaining production-oriented work.

### 7.3 Why?

Reading the pipeline from input to output is easier than opening files at random. Start with the contract, then `pipeline.py`, `head_pose.py`, `event_builder.py`, and evaluation code.

### 7.4 Common mistake

Assuming that a file named `phone_detector.py` means phone detection works. The current implementation returns `False` for every frame.

### 7.5 Check yourself

Which file converts frame signals into time intervals? **Answer:** `backend/vision/event_builder.py`.

## 8. Windows setup

### 8.1 Open the project and activate the environment

```powershell
cd D:\cheat-vision
.\.venv\Scripts\Activate.ps1
```

The prompt should show `(.venv)`. If PowerShell blocks activation, use the organization’s approved PowerShell policy or run the environment’s Python directly; do not change machine-wide security settings just to activate a project environment.

### 8.2 Confirm Python and dependencies

```powershell
python --version
python -m pip show opencv-python opencv-contrib-python mediapipe numpy pytest
```

Python 3.11.9 was observed in the user’s recent terminal output. Your machine may differ. The project has an existing `.venv`; for a fresh setup, first resolve the duplicate OpenCV package declarations in `requirements.txt`, then create a new environment and install the chosen dependency set.

### 8.3 Run automated checks

```powershell
python -m pytest -q
```

The most recent pasted run showed **23 passed, 1 skipped** after the main-face tie-break fix. The skipped test was the Redis integration test. Your run is the current source of truth; if it differs, use the traceback to diagnose before proceeding.

### 8.4 Start a webcam probe

```powershell
python -m backend.vision.probe
```

If the probe supports a video path or options, inspect its `--help` output or the module’s argument parser before guessing flags:

```powershell
python -m backend.vision.probe --help
```

Press `q` or `Esc` in the probe window to stop if that is the key behavior shown by the current script. Confirm the camera preview opens and that yaw/pitch update when you gently move your head. Keep the movement modest and record what direction each sign corresponds to.

### 8.5 Why?

Using `python -m` from the project root makes package imports resolve consistently and helps ensure commands use the active virtual environment.

### 8.6 Common mistake

Running `python` from a different directory or with the system interpreter, then believing a missing-package error describes the project environment.

### 8.7 Check yourself

What should the prompt show after activation? **Answer:** `(.venv)` (or the environment’s configured name), and `python --version` should report the interpreter you intend to use.

## 9. Record, label, and evaluate a real clip

### 9.1 Record a unique clip

From the repository root with `.venv` active:

```powershell
python -m evaluation.record_and_benchmark manual_normal_20261022_a.mp4
```

The tool opens the webcam, writes to `evaluation\clips`, and displays a preview. Use `q` or `Esc` in the camera window to stop. Choose a new filename each time: reusing a name may overwrite or delete the previous output.

First record a short normal baseline. Keep your face visible, look toward the camera, and keep other people/phones out of frame. Then record one behavior per clip. Avoid combining face loss, a second person, and looking away in the same first experiment because it becomes difficult to interpret a mismatch.

### 9.2 Label the observed interval

Open `evaluation/labels.csv` in a text editor or spreadsheet and add one row that matches its existing header and delimiter. A format example only—adapt it to the exact header already in your file:

```csv
clip,event_type,start_sec,end_sec
manual_looking_away_20261022_a.mp4,looking_away,7.0,12.0
```

Do not copy the example row blindly if the current CSV header or naming convention differs. Use the exact video filename, seconds relative to the start of the video, and the event interval you actually staged. Label normal intervals according to the evaluator’s existing convention. Keep labels honest: if you were looking down rather than turning sideways, describe that in your notes because pitch-down and yaw-sideways can behave differently.

### 9.3 Run evaluation

```powershell
python -m evaluation.evaluate --interval 1
```

The evaluator processes the clips it can find and skips missing files. It writes timestamped JSON and Markdown reports under `evaluation/reports`. Read the skipped-file messages, processed count, evaluated duration, per-event metrics, and per-clip details. A “processed 5/8” result means only five of eight configured video entries were available for that run; it does not mean the system detected five events.

### 9.4 Interpreting the metrics

- **TP**: predicted event matched to a reference interval.
- **FP**: predicted event did not match a reference interval.
- **FN**: a reference event did not get a matched prediction.
- **Precision**: TP / (TP + FP). Lower precision means more unmatched predictions among those made.
- **Recall**: TP / (TP + FN). Lower recall means more labeled events were missed.
- **False alarms/hour**: unmatched predicted events normalized by the evaluated clip duration in hours.

If there are no predicted or reference events for a category, precision/recall can show `0.00%` because the denominator is zero. That is **not evidence of zero accuracy**. For example, phone detection returns `False` for every frame right now, so its all-zero event row is not a detector validation result.

### 9.5 What the latest pasted evaluation says

✅ Confirmed from the user’s latest terminal output on 2026-10-22: the evaluator processed 5 of 8 configured videos and reported about 0.021472 video-hours (about 77 seconds). It counted:

| Event | TP | FP | FN | Precision | Recall | False alarms/hour |
|---|---:|---:|---:|---:|---:|---:|
| `face_missing` | 1 | 1 | 0 | 50% | 100% | 46.572 |
| `multiple_faces` | 1 | 0 | 0 | 100% | 100% | 0 |
| `looking_away` | 1 | 0 | 0 | 100% | 100% | 0 |
| `phone_detected` | 0 | 0 | 0 | 0% | 0% | 0 |

These are counts from a tiny set of hand-staged clips. The single `face_missing` FP dominates its precision and hourly false-alarm rate because the total evaluation duration is very short. Inspect the report’s per-clip section to find which prediction was unmatched. It might be a label gap or a genuine false alarm; the summary alone cannot establish which. The `looking_away` success occurred during a head-pitch-down interval in the user’s recording; it does not yet prove reliable sideways-gaze detection.

✅ Confirmed from pasted benchmark logs: webcam steady-state samples were roughly 6.7–14.2 ms/frame across several short runs, with cold starts around 2.7–2.8 seconds in some runs (one warmed run began at about 60 ms). Sample counts were small and camera/runtime conditions varied. Do not use these as stable latency guarantees or capacity planning numbers.

🧪 Assistant sandbox exploration previously reported synthetic throughput/load values in project benchmark notes. Those tests used limited repeated frame data and are not user-confirmed production capacity results. Treat them as exploratory only; do not use them to promise supported concurrent students.

### 9.6 Why?

The same recorded clip can be replayed after code changes, so it helps make comparisons more repeatable. Separate clips and clear labels make it easier to find the cause of an error.

### 9.7 Common mistake

Calling 100% precision and recall on one true positive “100% accurate.” With one event, a single additional case changes the score dramatically. Also, video duration is not the same as the number of independent people, cameras, rooms, or lighting conditions.

### 9.8 Check yourself

What does `phone_detected: 0 TP, 0 FP, 0 FN` mean while the detector is a stub? **Answer:** No phone events were predicted or labeled/matched in that run; the row does not measure whether the system can detect phones.

## 10. Known issues and current limits

1. **Phone detection is not implemented.** The stub returns `False` for every image.
2. **The user’s first `looking_away` attempt did not turn into usable pose data.** In one run the face count became zero during the intended interval. A later run did trigger while pitch was around −37° to −41°. This is evidence that the threshold path can trigger for that pose, not proof of robust sideways gaze detection.
3. **The face-missing metric has one unmatched prediction.** Review the per-clip report and label coverage to determine the cause.
4. **The dataset is tiny.** Five processed videos and roughly 77 seconds of total video are not enough to estimate general reliability.
5. **The three legacy clips are missing.** The latest evaluator skipped `clip_02_look_away.mp4`, `clip_03_face_missing.mp4`, and `clip_04_two_faces.mp4`.
6. **The OpenCV requirements need cleanup.** Both `opencv-python` and `opencv-contrib-python` appear in requirements; resolve the package choice for reproducible clean installs.
7. **Redis integration is not verified live.** One related test was skipped when Redis was unavailable.
8. **Pose axes and thresholds need camera-specific checks.** The sign convention depends on implementation and camera conditions.
9. **The recording helper can replace existing output.** Give each run a new name.
10. **Model asset provenance should be independently checked before distribution.** The pipeline verifies its hash, which establishes file identity relative to the expected hash, not the legal or distribution rights of the source.
11. **The project is experimental.** No claim here establishes that it is suitable for high-stakes decisions, remote exam enforcement, or automatic accusations.

### EventBuilder behaviors to understand

`EventBuilder` uses minimum durations and tolerates some missing samples. It ignores non-increasing timestamps, closes an interval when the signal ends or the timestamp gap becomes too large, and flushes open intervals when a session ends. A common apparent “bug” is actually a mismatch between seconds in the label and timestamps used by the evaluator. Another is expecting a one-frame condition to pass a multi-second minimum duration. Check the configured event duration and the actual sample timestamps before changing code.

## 11. Troubleshooting

1. **`ModuleNotFoundError`** — Confirm `(.venv)` is active and run from `D:\cheat-vision`; use `python -m ...`.
2. **Wrong Python version** — Run `python --version` and confirm the active interpreter path with `python -c "import sys; print(sys.executable)"`.
3. **Camera does not open** — Close other camera applications, check Windows camera permissions, and inspect the probe’s reported camera index/backend.
4. **Black camera preview** — Try the supported camera index or backend options in the current script; verify the webcam works in another application.
5. **No face found** — Improve lighting, move into frame, face the camera more directly, and check that the camera is not too far away.
6. **Yaw/pitch sign seems reversed** — Record a brief controlled turn and inspect the numeric change. Do not “fix” a sign by guessing.
7. **Pose jumps or vanishes on a strong turn** — Face landmark estimation may fail when too little of the face is visible; the pipeline may then report no face/pose rather than a large angle.
8. **`looking_away` remains false** — Compare measured angles with thresholds and event duration. A short pose may not persist long enough to open an event.
9. **`face_count` unexpectedly becomes 0** — Review lighting, occlusion, image framing, and exact clip timestamps; distinguish detector failure from intended gaze behavior.
10. **`phone_detected` always false** — Expected with the current stub. This is not fixed by changing labels.
11. **Evaluator skips clips** — Put the clip in `evaluation/clips` and ensure the configured filename exactly matches, including extension.
12. **TP/FP/FN all zero** — Check whether labels loaded, whether the clip was processed, and whether that category has any reference interval. Zero counts are not proof of correctness.
13. **Huge false alarms/hour** — The evaluated duration may be very short. Inspect the raw false-positive count and the clip that generated it.
14. **A label never matches** — Check exact filename, event name, start/end seconds, and whether the event duration is long enough for the configured minimum.
15. **`pytest` integration test skips** — The skipped Redis test likely needs a live Redis service and its configured connection settings.
16. **OpenCV import or DLL error** — The duplicate OpenCV package declarations may be involved. Use a clean environment after the requirements are corrected rather than stacking packages.
17. **Slow first frame** — Model loading and graph initialization can make cold start much slower than later frames; report cold-start and steady-state latency separately.
18. **Queue reports stale frames dropped** — The worker may discard old jobs to keep current frames useful. Check queue size and max frame age; do not assume every submitted frame was analyzed.
19. **Output video unexpectedly changed** — The recorder may overwrite a matching output name. Use a unique filename and preserve important clips elsewhere before repeating a run.
20. **Model file missing or hash error** — Use the repository’s fetch helper and verify the downloaded file against the expected hash. Independently verify official provenance before relying on distribution rights.

## 12. Checkpoint: where the project is now

### 12.1 Current checkpoint

✅ Confirmed: the Python vision pipeline, face count, face pose estimates, event aggregation, session storage options, worker, recording/evaluation workflow, and automated tests exist in the repository. The user has run webcam recordings and the evaluator.

✅ Confirmed: one recorded face-missing event, one multiple-face event, and one looking-away event matched labels in the most recent pasted report. There was also one unmatched face-missing prediction.

❓ Unconfirmed: robust behavior across varied people, cameras, lighting, webcam placement, and long sessions; production reliability; live Redis; camera-specific pose sign calibration; a phone detector; and validated deployment capacity.

The project is not production-ready. Phases beyond the implemented experimental vision/evaluation foundation still require design and verification. The user's earlier `APPROVED: phase-9` authorized moving toward the phone-detection phase, but a detector/model choice was still awaiting selection in the conversation context; this handbook does not imply that a phone model was selected or installed.

### 12.2 Check where YOU are

Mark each item yes/no:

1. Can you tell which Python interpreter the activated terminal uses?
2. Can you explain the five signal keys returned by the pipeline?
3. Can you tell the difference between a frame-level signal and an event interval?
4. Have you verified yaw and pitch directions with your webcam?
5. Do you know the current minimum duration for each event type?
6. Can you record a fresh clip without replacing an earlier one?
7. Does every evaluation clip you intend to use have a matching label or an explicit normal annotation?
8. Can you find which clip produced the face-missing false positive?
9. Can you explain why the phone metrics do not validate phone detection?
10. Have you run `python -m pytest -q` in the active environment?
11. Do you know why missing legacy videos are skipped?
12. Can you separate cold-start latency from steady-state latency?
13. Have you kept a clip aside that was not used while tuning thresholds?
14. Can you explain why a small clip set does not establish production accuracy?
15. Do you know how to stop the probe/recording window and where the output is saved?

If any answer is “no,” use the matching section above before making a larger change. Do not use a checklist score as a certification of the system.

## 13. Limitations, privacy, and responsible use

This system estimates visual signals from camera frames. Lighting, camera angle, face appearance, occlusion, device quality, and model limitations can affect results. A missing face can have many causes. A pose threshold cannot tell why a person moved their head. A phone detector, when implemented, would also need testing across phones, backgrounds, camera views, and false-positive objects.

Do not treat a signal or event as proof of cheating or intent. Keep a human review step and provide a way to challenge or correct an interpretation. Do not make high-stakes decisions from this prototype.

Camera frames can contain sensitive personal information. Before collecting or retaining video, define who can access it, why it is collected, how long it is kept, how it is protected, and how deletion works. Collect only what is needed for a clear evaluation purpose. Use consenting participants and controlled test clips. **This is not legal advice; ask a lawyer** about applicable privacy, education, employment, biometric, and recording requirements before real-world deployment.

## 14. Roadmap as work areas, not a schedule

The user asked to disregard timeline comparisons, so this section lists work areas without dates or promised order.

1. **Reproducible setup:** resolve the duplicate OpenCV dependencies and document a clean environment install.
2. **Evaluation data quality:** restore/replace missing clips, ensure labels cover all intended periods, inspect unmatched events, and reserve separate clips for evaluation.
3. **Pose validation:** establish camera-specific axis directions, test yaw and pitch separately, and document threshold behavior.
4. **Phone detection:** select a model only after reviewing provenance, license, runtime, and data needs; replace the stub and add suitable labeled evaluations.
5. **Worker/session integration:** verify queue behavior, frame age, session identity, and Redis across the intended deployment setup.
6. **Operational safety:** define access control, retention, deletion, monitoring, and human review.
7. **Scale testing:** use representative frames and realistic duration/traffic, measure dropped frames and tail latency, and state limits narrowly.
8. **Product architecture:** decide which work belongs in the browser and which belongs on the server, based on privacy, latency, device support, and deployment constraints.

Each item needs its own acceptance criteria and evidence. A timeline document by itself is not evidence that a feature is complete.

## 15. Exercises and answer key

Try the exercises before reading the answers. Use short, reversible experiments and preserve original clips.

### Exercises

1. Explain the path from JPEG bytes to the output dictionary.
2. List the five keys in the signal contract.
3. Explain why a missing face differs from a face looking away.
4. Change your head yaw slightly and observe the sign; write down what you learned.
5. Repeat with pitch, keeping yaw near neutral.
6. Record a short normal clip with a unique filename.
7. Add one valid event row using the CSV’s actual header.
8. Run evaluation and find its JSON and Markdown report filenames.
9. Identify which clip caused the unmatched `face_missing` event.
10. Calculate precision when TP=3 and FP=1.
11. Calculate recall when TP=3 and FN=2.
12. Explain why an event row with all zeros can be uninformative.
13. Find the phone detector function and state what it currently returns.
14. Find one configured event duration and explain how it changes event output.
15. Explain why reusing a recording filename is risky.
16. Describe one way a label can be wrong even when the CSV parses correctly.
17. Separate cold-start latency from steady-state latency in a short benchmark.
18. Propose a held-out clip procedure so thresholds are not evaluated only on the clips used to tune them.

### Answer key

1. The pipeline validates and decodes bytes, runs face landmark inference, selects a face, estimates pose, applies thresholds, and returns signals.
2. `face_count`, `head_yaw`, `head_pitch`, `looking_away`, `phone_detected`.
3. A strong turn can make landmarks disappear; then no pose is available. Looking away requires usable evidence and a threshold decision.
4. There is no universal expected sign: report the observed sign for this implementation and camera.
5. Same: report the observed direction and check whether pitch changes independently.
6. Use `python -m evaluation.record_and_benchmark <new-name>.mp4` and stop in the capture window.
7. Match the existing CSV header, exact clip filename, event category, and clip-relative seconds.
8. Under `evaluation/reports`, using the timestamp printed by the command.
9. Read the per-clip section in the latest report; the aggregate alone does not identify it.
10. Precision = 3/(3+1) = 75%.
11. Recall = 3/(3+2) = 60%.
12. It can mean no examples were predicted or labeled; it does not show that the feature works, especially when the detector is a stub.
13. `backend/vision/phone_detector.py`; it currently returns `False`.
14. Read `backend/vision/config.py` and relate the configured minimum persistence to the time signal remains active.
15. The recorder may replace or delete an existing output at that path.
16. The interval may be shifted, truncated, use the wrong event category, or describe a different behavior than what happened.
17. Report first-frame initialization separately from later warmed frames; do not average them together without saying so.
18. Keep people/scenes/clips out of threshold tuning, freeze the configuration, then evaluate once on the held-out set.

## 16. Frequently asked questions

1. **Is the system finished?** No. It is an experimental vision component with incomplete features and limited validation.
2. **Does phone detection work?** No. The current function always returns `False`.
3. **Why did phone metrics show all zeroes?** No events were counted; with a stub this does not measure detector performance.
4. **Does 100% recall mean it is reliable?** Not with one matched event. The sample is too small for a broad reliability claim.
5. **What does the face-missing false positive mean?** One predicted event did not match a label under the current evaluator rules. Inspect its clip and labels to find out why.
6. **Why did the evaluator skip videos?** The configured filenames were not present in `evaluation/clips` at run time.
7. **Why can face count become zero while turning sideways?** The face landmark model may not have enough visible facial features to detect the face.
8. **Does `looking_away` mean the eyes looked away?** No. The current path infers from head pose, not precise eye gaze or intent.
9. **Does `looking_away` prove cheating?** No. It is only a thresholded visual signal.
10. **Why is the first frame slow?** Model loading and graph initialization add startup cost.
11. **Does a 10 ms steady frame time mean 100 students are supported?** No. End-to-end throughput depends on workers, queueing, frame frequency, hardware, and dropped frames.
12. **Why are some frames dropped?** The worker can discard stale frames when its bounded queue or age limit is reached.
13. **Can I use the same webcam clip repeatedly?** Yes for repeatable debugging, but do not treat repeated analysis as independent evaluation evidence.
14. **Should I fine-tune the face model?** Not without a well-defined task, appropriate data, consent, split strategy, and evaluation plan.
15. **How do I validate a threshold?** Use separate, representative clips, one behavior at a time, inspect false positives and misses, and keep a held-out set.
16. **Why does my event not open immediately?** Event duration/minimum sample rules may require persistence.
17. **Can Redis be assumed to work?** No. The option exists, but live Redis behavior still needs an environment-specific test.
18. **Can I deploy this for real exams now?** The repository evidence does not establish production readiness; privacy, reliability, security, fairness, and human-review requirements remain.
19. **Should I follow the one-month plan timeline?** This handbook does not impose that timeline; it documents work areas and current evidence.
20. **Where do I start after reading?** Run tests, inspect the webcam probe, record a unique normal clip, label it, and inspect the evaluation report.

## 17. References

These references are for the underlying tools and APIs. The project-specific descriptions above are based on the workspace files and user-provided run output.

- [MediaPipe Face Landmarker for Python](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker/python)
- [MediaPipe Face Landmarker for Web](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker/web_js)
- [OpenCV VideoCapture](https://docs.opencv.org/4.13.0/d8/dfe/classcv_1_1VideoCapture.html)
- [Python documentation](https://docs.python.org/3/)
- [PEP 8 — Python style guide](https://peps.python.org/pep-0008/)
- [NumPy documentation](https://numpy.org/doc/)

## Appendix A. Command quick reference

```powershell
cd D:\cheat-vision
.\.venv\Scripts\Activate.ps1
python --version
python -m pytest -q
python -m backend.vision.probe
python -m backend.vision.probe --help
python -m evaluation.record_and_benchmark manual_unique_name.mp4
python -m evaluation.evaluate --interval 1
```

Use a fresh clip filename for each recording. Check the actual command’s `--help` output before relying on optional arguments not shown here.

## Appendix B. Signal contract v1 and v1.1

The contract is the shape callers should expect. The repository’s own `docs/CONTRACT.md` is the detailed source; check it before changing an API.

### v1 — Per-frame output

```json
{
  "face_count": 1,
  "head_yaw": 4.2,
  "head_pitch": -3.1,
  "looking_away": false,
  "phone_detected": false
}
```

This is a format example, not a claim that these values came from a recorded frame. `head_yaw` and `head_pitch` may be null when unavailable. `phone_detected` is currently hard-coded false by the stub.

### v1.1 — Event records

The event builder emits event lifecycle records with event type, status (`opened` or `closed`), timestamps, and associated metadata such as sample counts/confidence according to the current implementation. Read `docs/CONTRACT.md` and inspect actual report output before integrating another service; do not assume unlisted fields or units.

### Change discipline

If a signal key, unit, timestamp origin, event status, or null behavior changes, update the contract and tests together. Version the change if existing callers could interpret it differently.

## Appendix C. Mental diagram

```text
          ┌───────────────────────┐
          │ Webcam or video clip  │
          └───────────┬───────────┘
                      v
          ┌───────────────────────┐
          │ JPEG bytes and checks │
          └───────────┬───────────┘
                      v
          ┌───────────────────────┐
          │ Face landmarks/pose   │
          └───────────┬───────────┘
                      v
          ┌───────────────────────┐
          │ Frame-level signals   │
          └───────────┬───────────┘
                      v
          ┌───────────────────────┐       ┌──────────────────────┐
          │ EventBuilder          │<──────│ Human labels in CSV  │
          └───────────┬───────────┘       └──────────────────────┘
                      v                              |
          ┌───────────────────────┐                  v
          │ Event interval report │──────────> Compare and review
          └───────────────────────┘

Phone detector: currently a stub that returns False.
```

---

**End of handbook.** Re-run checks and update the evidence section whenever implementation, labels, or evaluation data change.
