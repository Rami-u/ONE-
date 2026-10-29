"""Face count extraction, bounding box calculation, and secondary face blurring."""

from pathlib import Path
from typing import Any, Optional, Sequence, TypedDict
import cv2
import numpy as np

from .config import DEFAULT_CONFIG

NORMALIZED_IMAGE_CENTER: float = 0.5
AREA_PRECISION_DECIMALS: int = 12
BBOX_PADDING_RATIO: float = 0.12


class FaceBBox(TypedDict):
    index: int
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    area: float
    is_main: bool


class FaceCountResult(TypedDict):
    face_count: int
    face_missing: bool
    multiple_faces: bool


def select_main_face_index(face_landmarks: Optional[Sequence[Sequence[Any]]]) -> Optional[int]:
    """Choose the largest face box, breaking equal-area ties by distance to image center."""
    if not face_landmarks:
        return None

    ranked: list[tuple[float, float, int]] = []
    for index, landmarks in enumerate(face_landmarks):
        x_coords = [float(point.x) for point in landmarks]
        y_coords = [float(point.y) for point in landmarks]
        if not x_coords or not y_coords:
            continue

        width = max(x_coords) - min(x_coords)
        height = max(y_coords) - min(y_coords)
        area = width * height

        center_x = (min(x_coords) + max(x_coords)) / 2.0
        center_y = (min(y_coords) + max(y_coords)) / 2.0
        center_distance = (
            (center_x - NORMALIZED_IMAGE_CENTER) ** 2
            + (center_y - NORMALIZED_IMAGE_CENTER) ** 2
        )

        # Quantize area to absorb floating-point ULP differences in landmark coordinates,
        # allowing mathematically equal boxes to reach the deterministic center tie-break.
        quantized_negative_area = -round(area, AREA_PRECISION_DECIMALS)
        ranked.append((quantized_negative_area, center_distance, index))

    return min(ranked)[2] if ranked else None


def extract_face_counts(detection_result: Any) -> FaceCountResult:
    """Extract the number of detected faces from a MediaPipe FaceLandmarkerResult."""
    landmarks = getattr(detection_result, "face_landmarks", None)
    face_count = len(landmarks) if landmarks else 0

    return {
        "face_count": face_count,
        "face_missing": face_count == 0,
        "multiple_faces": face_count >= 2,
    }


def extract_face_bboxes(
    face_landmarks: Optional[Sequence[Sequence[Any]]],
    image_width: int,
    image_height: int,
    padding_ratio: float = BBOX_PADDING_RATIO,
) -> list[FaceBBox]:
    """Convert normalized MediaPipe landmarks into pixel bounding boxes and tag the main student face."""
    if not face_landmarks or image_width <= 0 or image_height <= 0:
        return []

    main_idx = select_main_face_index(face_landmarks)
    boxes: list[FaceBBox] = []

    for index, landmarks in enumerate(face_landmarks):
        x_coords = [float(point.x) for point in landmarks]
        y_coords = [float(point.y) for point in landmarks]
        if not x_coords or not y_coords:
            continue

        norm_w = max(x_coords) - min(x_coords)
        norm_h = max(y_coords) - min(y_coords)
        pad_x = norm_w * padding_ratio
        pad_y = norm_h * padding_ratio

        x_min = max(0, int(round((min(x_coords) - pad_x) * image_width)))
        y_min = max(0, int(round((min(y_coords) - pad_y) * image_height)))
        x_max = min(image_width, int(round((max(x_coords) + pad_x) * image_width)))
        y_max = min(image_height, int(round((max(y_coords) + pad_y) * image_height)))

        boxes.append(
            {
                "index": index,
                "x_min": x_min,
                "y_min": y_min,
                "x_max": x_max,
                "y_max": y_max,
                "area": round(norm_w * norm_h, 6),
                "is_main": index == main_idx,
            }
        )

    return boxes


def blur_secondary_faces(
    frame_bgr: np.ndarray,
    face_landmarks: Optional[Sequence[Sequence[Any]]],
    kernel_size: int = DEFAULT_CONFIG.blur_kernel_size,
) -> tuple[np.ndarray, int]:
    """Blur all faces except the primary student face (largest/center face).

    Returns a tuple of (processed_frame_bgr, blurred_faces_count).
    """
    if frame_bgr is None or frame_bgr.size == 0 or not face_landmarks or len(face_landmarks) < 2:
        return frame_bgr, 0

    height, width = frame_bgr.shape[:2]
    boxes = extract_face_bboxes(face_landmarks, width, height)
    secondary_boxes = [box for box in boxes if not box["is_main"]]
    if not secondary_boxes:
        return frame_bgr, 0

    output = frame_bgr.copy()
    k = max(3, int(kernel_size))
    if k % 2 == 0:
        k += 1

    blurred_count = 0
    for box in secondary_boxes:
        x1, y1, x2, y2 = box["x_min"], box["y_min"], box["x_max"], box["y_max"]
        if x2 > x1 and y2 > y1:
            roi = output[y1:y2, x1:x2]
            output[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (k, k), 0)
            blurred_count += 1

    return output, blurred_count


def blur_secondary_faces_in_video(
    input_video_path: str | Path,
    output_video_path: str | Path,
    detector_fn: Optional[Any] = None,
    kernel_size: int = DEFAULT_CONFIG.blur_kernel_size,
) -> dict[str, int | float | str]:
    """Process a video clip to blur any secondary faces while keeping the primary student sharp."""
    in_path = Path(input_video_path)
    out_path = Path(output_video_path)
    if not in_path.is_file():
        raise FileNotFoundError(f"Input video not found: {in_path}")

    cap = cv2.VideoCapture(str(in_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video for blurring: {in_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 20.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"Could not open output video writer: {out_path}")

    if detector_fn is None:
        import mediapipe as mp
        from .pipeline import get_landmarker

        def _default_detect(frame_bgr: np.ndarray) -> Any:
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            return get_landmarker().detect(mp_img)

        detector_fn = _default_detect

    frames_processed = 0
    frames_with_secondary_blurred = 0

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            detection = detector_fn(frame)
            landmarks = getattr(detection, "face_landmarks", None)
            processed_frame, blurred_count = blur_secondary_faces(
                frame, landmarks, kernel_size=kernel_size
            )
            if blurred_count > 0:
                frames_with_secondary_blurred += 1
            writer.write(processed_frame)
            frames_processed += 1
    finally:
        cap.release()
        writer.release()

    return {
        "input_video": str(in_path),
        "output_video": str(out_path),
        "frames_processed": frames_processed,
        "frames_with_secondary_blurred": frames_with_secondary_blurred,
    }
