from types import SimpleNamespace

import numpy as np

from backend.vision import phone_detector
from backend.vision.audio_alert import SAMPLE_RATE, _alarm_samples


def test_phone_detector_accepts_confident_cell_phone(monkeypatch):
    category = SimpleNamespace(category_name="cell phone", score=0.8)
    detector = SimpleNamespace(
        detect=lambda image: SimpleNamespace(
            detections=[
                SimpleNamespace(
                    categories=[category],
                    bounding_box=SimpleNamespace(
                        origin_x=4, origin_y=5, width=20, height=30
                    ),
                )
            ]
        )
    )
    monkeypatch.setattr(phone_detector, "get_phone_detector", lambda: detector)

    assert phone_detector.detect_phone(np.zeros((64, 64, 3), dtype=np.uint8)) is True
    detected, score, bbox = phone_detector.detect_phone_details(
        np.zeros((64, 64, 3), dtype=np.uint8)
    )
    assert detected is True
    assert score == 0.8
    assert bbox == (4, 5, 20, 30)


def test_phone_detector_rejects_low_confidence_and_non_phone(monkeypatch):
    categories = [
        SimpleNamespace(category_name="cell phone", score=0.45),
        SimpleNamespace(category_name="remote", score=0.95),
    ]
    detector = SimpleNamespace(
        detect=lambda image: SimpleNamespace(
            detections=[
                SimpleNamespace(
                    categories=categories,
                    bounding_box=SimpleNamespace(
                        origin_x=0, origin_y=0, width=10, height=10
                    ),
                )
            ]
        )
    )
    monkeypatch.setattr(phone_detector, "get_phone_detector", lambda: detector)

    assert phone_detector.detect_phone(np.zeros((64, 64, 3), dtype=np.uint8)) is False
    detected, score, _ = phone_detector.detect_phone_details(
        np.zeros((64, 64, 3), dtype=np.uint8)
    )
    assert detected is False
    assert score == 0.45


def test_alarm_tone_patterns_are_nonempty_audio():
    warning = _alarm_samples("warning_alarm")
    phone = _alarm_samples("phone_alarm")

    assert warning.ndim == 1 and warning.size > 0
    assert phone.ndim == 1 and phone.size > warning.size
    assert SAMPLE_RATE == 24_000
