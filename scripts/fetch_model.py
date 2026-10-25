"""Fetch the MediaPipe Face Landmarker model if absent and pin its SHA-256."""

import hashlib
from pathlib import Path
from urllib.request import urlopen

MODEL_URL: str = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)
MODEL_PATH: Path = (
    Path(__file__).resolve().parents[1] / "backend" / "vision" / "face_landmarker.task"
)
HASH_PATH: Path = MODEL_PATH.with_name(MODEL_PATH.name + ".sha256")
DOWNLOAD_TIMEOUT_SECONDS: int = 60


def download_model_file(url: str, destination: Path, timeout_seconds: int = DOWNLOAD_TIMEOUT_SECONDS) -> None:
    """Download model bytes to a temporary file before atomically moving to destination."""
    print(f"Downloading MediaPipe model from {url}")
    with urlopen(url, timeout=timeout_seconds) as response:
        data = response.read()
    temporary = destination.with_suffix(destination.suffix + ".download")
    temporary.write_bytes(data)
    temporary.replace(destination)


def compute_sha256_digest(file_path: Path) -> str:
    """Calculate hex-encoded SHA-256 digest of a file."""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def main() -> None:
    """Ensure the model task asset exists and update its SHA-256 checksum file."""
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not MODEL_PATH.exists():
        download_model_file(MODEL_URL, MODEL_PATH)

    digest = compute_sha256_digest(MODEL_PATH)
    HASH_PATH.write_text(f"{digest}  {MODEL_PATH.name}\n", encoding="ascii")
    print(f"SHA256: {digest}")


if __name__ == "__main__":
    main()
