"""Exam and question context evaluation for intelligent proctoring policies."""

from dataclasses import dataclass
from typing import Literal, Mapping, Optional

from .config import DEFAULT_CONFIG

SubjectCategory = Literal["quantitative", "theoretical"]
QuestionType = Literal["problem_solving", "mcq", "essay", "formula_or_law", "equation_completion"]

# Arabic and English subject keywords mapped to quantitative vs theoretical categories
QUANTITATIVE_SUBJECTS: frozenset[str] = frozenset({
    "math",
    "mathematics",
    "physics",
    "chemistry",
    "statistics",
    "calculus",
    "algebra",
    "geometry",
    "mechanics",
    "accounting",
    "engineering",
    "رياضيات",
    "رياضة",
    "فيزياء",
    "كيمياء",
    "إحصاء",
    "احصاء",
    "تفاضل",
    "تكامل",
    "جبر",
    "هندسة",
    "ميكانيكا",
    "محاسبة",
    "استاتيكا",
    "ديناميكا",
})

THEORETICAL_SUBJECTS: frozenset[str] = frozenset({
    "arabic",
    "history",
    "geography",
    "english",
    "french",
    "german",
    "italian",
    "philosophy",
    "psychology",
    "sociology",
    "biology",
    "geology",
    "literature",
    "religion",
    "civics",
    "عربي",
    "لغة عربية",
    "تاريخ",
    "جغرافيا",
    "إنجليزي",
    "انجليزي",
    "فرنساوي",
    "ألماني",
    "الماني",
    "فلسفة",
    "علم نفس",
    "اجتماع",
    "أحياء",
    "احياء",
    "جيولوجيا",
})


def resolve_subject_category(subject: Optional[str]) -> SubjectCategory:
    """Determine whether a teacher's subject involves manual hand calculation or is theoretical."""
    if not subject:
        return "theoretical"
    normalized = subject.strip().lower()
    for kw in QUANTITATIVE_SUBJECTS:
        if kw in normalized:
            return "quantitative"
    for kw in THEORETICAL_SUBJECTS:
        if kw in normalized:
            return "theoretical"
    return "theoretical"


@dataclass(frozen=True)
class ExamContext:
    """Contextual metadata about the exam, teacher's subject, and current question."""

    teacher_subject: str = "general"
    question_type: QuestionType = "mcq"
    requires_hand_solving: bool = False
    is_static_or_formula: bool = False
    teacher_solving_time_limit_s: float = DEFAULT_CONFIG.default_solving_down_limit_s

    @property
    def subject_category(self) -> SubjectCategory:
        return resolve_subject_category(self.teacher_subject)

    def allows_extended_looking_down(self) -> bool:
        """Check whether the student is allowed to look down at scratch paper for solving.

        Rules:
        1. If the exam subject is theoretical (e.g. Arabic, History, Geography), the student
           has no reason to look down repeatedly -> False.
        2. Even in a quantitative subject (e.g. Math, Physics):
           - If the question is static (essay, asking for a law/definition, or completing
             a fixed equation), looking down is NOT needed -> False.
           - If the question is MCQ (`question_type == "mcq"`), the feature ONLY activates
             when `requires_hand_solving=True` (MCQ that requires manual calculation).
           - If `question_type == "problem_solving"` and not static/formula -> True.
        """
        if self.subject_category != "quantitative":
            return False

        if self.is_static_or_formula or self.question_type in (
            "essay",
            "formula_or_law",
            "equation_completion",
        ):
            return False

        if self.question_type == "mcq":
            return bool(self.requires_hand_solving)

        if self.question_type == "problem_solving":
            return True

        return bool(self.requires_hand_solving)

    def effective_looking_down_grace_s(
        self, default_grace_s: float = DEFAULT_CONFIG.looking_away_grace_s
    ) -> float:
        """Return the allowed duration (in seconds) for looking down before warning."""
        if self.allows_extended_looking_down():
            return max(default_grace_s, float(self.teacher_solving_time_limit_s))
        return float(default_grace_s)

    def to_dict(self) -> dict[str, object]:
        return {
            "teacher_subject": self.teacher_subject,
            "question_type": self.question_type,
            "requires_hand_solving": self.requires_hand_solving,
            "is_static_or_formula": self.is_static_or_formula,
            "teacher_solving_time_limit_s": self.teacher_solving_time_limit_s,
        }

    @classmethod
    def from_dict(cls, data: Optional[Mapping[str, object]]) -> "ExamContext":
        if not data:
            return cls()
        return cls(
            teacher_subject=str(data.get("teacher_subject", "general")),
            question_type=str(data.get("question_type", "mcq")),  # type: ignore[arg-type]
            requires_hand_solving=bool(data.get("requires_hand_solving", False)),
            is_static_or_formula=bool(data.get("is_static_or_formula", False)),
            teacher_solving_time_limit_s=float(
                data.get(
                    "teacher_solving_time_limit_s",
                    DEFAULT_CONFIG.default_solving_down_limit_s,
                )
            ),
        )
