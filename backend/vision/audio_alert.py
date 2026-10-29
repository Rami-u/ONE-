"""Generate short, non-blocking warning tones for the local proctoring preview."""

from __future__ import annotations

import numpy as np

SAMPLE_RATE = 24_000


def _alarm_samples(audio_cue: str) -> np.ndarray:
    """Build a compact warning pattern without needing a hosted audio file."""
    if audio_cue == "critical_alarm":
        pattern = ((660, 0.16), (990, 0.16), (660, 0.16), (990, 0.16))
    elif audio_cue == "phone_alarm":
        pattern = ((1_180, 0.18), (1_180, 0.18), (1_180, 0.18))
    else:
        pattern = ((880, 0.18), (880, 0.18))

    chunks: list[np.ndarray] = []
    for index, (frequency, duration_s) in enumerate(pattern):
        sample_count = int(SAMPLE_RATE * duration_s)
        t = np.arange(sample_count, dtype=np.float32) / SAMPLE_RATE
        tone = 0.24 * np.sin(2 * np.pi * frequency * t)
        ramp = min(int(SAMPLE_RATE * 0.012), sample_count // 2)
        if ramp:
            envelope = np.ones(sample_count, dtype=np.float32)
            envelope[:ramp] = np.linspace(0, 1, ramp, dtype=np.float32)
            envelope[-ramp:] = np.linspace(1, 0, ramp, dtype=np.float32)
            tone *= envelope
        chunks.append(tone)
        if index != len(pattern) - 1:
            chunks.append(np.zeros(int(SAMPLE_RATE * 0.09), dtype=np.float32))
    return np.concatenate(chunks)


def play_alarm(audio_cue: str) -> bool:
    """Play the supplied alarm on the machine running the local camera preview.

    The cue name is also carried in backend notifications so a future browser UI
    can play the same warning on the student's device.
    """
    try:
        import sounddevice as sd

        sd.play(_alarm_samples(audio_cue), SAMPLE_RATE, blocking=False)
        return True
    except Exception:
        # A missing or unavailable speaker must not stop exam frame processing.
        return False
