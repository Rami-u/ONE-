"""Face count extraction for missing-face and multiple-faces detection."""

from typing import Any, Optional, Sequence, TypedDict

NORMALIZED_IMAGE_CENTER: float = 0.5
AREA_PRECISION_DECIMALS: int = 12


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


class FaceCountResult(TypedDict):
    face_count: int
    face_missing: bool
    multiple_faces: bool


def extract_face_counts(detection_result: Any) -> FaceCountResult:
    """Extract the number of detected faces from a MediaPipe FaceLandmarkerResult."""
    landmarks = getattr(detection_result, "face_landmarks", None)
    face_count = len(landmarks) if landmarks else 0

    return {
        "face_count": face_count,
        "face_missing": face_count == 0,
        "multiple_faces": face_count >= 2,
    }
