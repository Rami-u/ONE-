"""Runtime configuration for the vision pipeline."""

from dataclasses import dataclass
import os
from typing import Any

ENV_PREFIX: str = "VISION_"
TRUE_BOOLEAN_STRINGS: frozenset[str] = frozenset({"1", "true", "yes", "on"})


@dataclass(frozen=True)
class VisionConfig:
    yaw_threshold: float = 30.0
    pitch_up_threshold: float = 25.0
    pitch_down_threshold: float = -25.0
    face_missing_duration_s: float = 3.0
    multiple_faces_duration_s: float = 5.0
    looking_away_duration_s: float = 5.0
    phone_detected_duration_s: float = 5.0
    # New proctoring policy parameters
    looking_away_grace_s: float = 5.0
    looking_away_max_warnings: int = 2
    looking_away_critical_warning_attempt: int = 3
    multiple_faces_exit_deadline_s: float = 10.0
    default_solving_down_limit_s: float = 60.0
    blur_kernel_size: int = 51
    tolerance_samples: int = 1
    min_samples: int = 2
    max_frame_gap_s: float = 5.0
    max_image_bytes: int = 1_000_000
    max_image_side: int = 1920
    num_faces: int = 3
    config_version: str = "2"

    @classmethod
    def from_env(cls) -> "VisionConfig":
        """Build configuration from environment variables, falling back to defaults."""
        defaults = cls()
        values: dict[str, Any] = {}
        for name, default in defaults.__dict__.items():
            env_var = f"{ENV_PREFIX}{name.upper()}"
            raw = os.getenv(env_var)
            if raw is None and name == "looking_away_critical_warning_attempt":
                # Keep honoring the former setting name after the third-strike
                # behavior changed from termination to a critical warning.
                raw = os.getenv("VISION_LOOKING_AWAY_TERMINATE_ATTEMPT")
            if raw is None:
                continue
            if isinstance(default, bool):
                values[name] = raw.strip().lower() in TRUE_BOOLEAN_STRINGS
            elif isinstance(default, int):
                values[name] = int(raw)
            elif isinstance(default, float):
                values[name] = float(raw)
            else:
                values[name] = raw

        config = cls(**values)
        cls._validate(config)
        return config

    @staticmethod
    def _validate(config: "VisionConfig") -> None:
        """Validate bounds and invariants for pipeline configuration."""
        if config.max_image_bytes <= 0 or config.max_image_side <= 0:
            raise ValueError(
                "VISION_MAX_IMAGE_BYTES and VISION_MAX_IMAGE_SIDE must be positive"
            )
        if config.num_faces <= 0 or config.min_samples <= 0 or config.tolerance_samples < 0:
            raise ValueError(
                "VISION_NUM_FACES and VISION_MIN_SAMPLES must be positive; "
                "tolerance cannot be negative"
            )
        if config.max_frame_gap_s <= 0:
            raise ValueError("VISION_MAX_FRAME_GAP_S must be positive")
        if (
            config.looking_away_grace_s <= 0
            or config.multiple_faces_exit_deadline_s <= 0
            or config.phone_detected_duration_s <= 0
        ):
            raise ValueError(
                "VISION_LOOKING_AWAY_GRACE_S, VISION_MULTIPLE_FACES_EXIT_DEADLINE_S, "
                "and VISION_PHONE_DETECTED_DURATION_S must be positive"
            )
        if (
            config.looking_away_max_warnings < 0
            or config.looking_away_critical_warning_attempt <= config.looking_away_max_warnings
        ):
            raise ValueError(
                "VISION_LOOKING_AWAY_CRITICAL_WARNING_ATTEMPT must be greater than "
                "VISION_LOOKING_AWAY_MAX_WARNINGS"
            )
        if config.default_solving_down_limit_s <= 0:
            raise ValueError("VISION_DEFAULT_SOLVING_DOWN_LIMIT_S must be positive")


DEFAULT_CONFIG: VisionConfig = VisionConfig.from_env()
