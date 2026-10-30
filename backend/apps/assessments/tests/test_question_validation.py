from django.test import SimpleTestCase
from rest_framework.serializers import ValidationError

from apps.assessments.question_validation import (
    normalize_short_answer,
    validate_question_content,
)

MCQ_OPTIONS = [
    {"id": "a", "text": "C6H12"},
    {"id": "b", "text": "C6H6"},
    {"id": "c", "text": "C6H14"},
    {"id": "d", "text": "C5H6"},
]


def make_options(count):
    return [{"id": f"o{i}", "text": f"Option {i}"} for i in range(count)]


class ValidQuestionContentTests(SimpleTestCase):
    def test_valid_cases(self):
        cases = [
            ("mcq", "mcq", MCQ_OPTIONS, "b", MCQ_OPTIONS, "b"),
            (
                "mcq text is stripped",
                "mcq",
                [{"id": "a", "text": "  X "}, {"id": "b", "text": "Y"}],
                "a",
                [{"id": "a", "text": "X"}, {"id": "b", "text": "Y"}],
                "a",
            ),
            ("mcq with 6 options", "mcq", make_options(6), "o5", make_options(6), "o5"),
            ("true_false true", "true_false", None, True, None, True),
            ("true_false false", "true_false", None, False, None, False),
            ("short", "short", None, ["phenol"], None, ["phenol"]),
            ("short is stripped", "short", None, ["  phenol "], None, ["phenol"]),
            ("essay with model answer", "essay", None, "Key points", None, "Key points"),
            ("essay without answer is empty string", "essay", None, None, None, ""),
            ("essay with empty answer", "essay", None, "", None, ""),
        ]
        for name, qtype, options, correct, want_options, want_correct in cases:
            with self.subTest(name):
                self.assertEqual(
                    validate_question_content(qtype, options, correct),
                    (want_options, want_correct),
                )


class InvalidQuestionContentTests(SimpleTestCase):
    def test_invalid_cases(self):
        cases = [
            ("mcq without options", "mcq", None, "a", "options"),
            ("mcq options not a list", "mcq", "abc", "a", "options"),
            ("mcq with 1 option", "mcq", make_options(1), "o0", "options"),
            ("mcq with 7 options", "mcq", make_options(7), "o0", "options"),
            (
                "mcq duplicate option ids",
                "mcq",
                [{"id": "a", "text": "X"}, {"id": "a", "text": "Y"}],
                "a",
                "options",
            ),
            (
                "mcq uppercase id",
                "mcq",
                [{"id": "A", "text": "X"}, {"id": "b", "text": "Y"}],
                "b",
                "options",
            ),
            (
                "mcq id too long",
                "mcq",
                [{"id": "abcdefghijk", "text": "X"}, {"id": "b", "text": "Y"}],
                "b",
                "options",
            ),
            (
                "mcq empty text",
                "mcq",
                [{"id": "a", "text": "   "}, {"id": "b", "text": "Y"}],
                "b",
                "options",
            ),
            (
                "mcq text too long",
                "mcq",
                [{"id": "a", "text": "x" * 501}, {"id": "b", "text": "Y"}],
                "b",
                "options",
            ),
            (
                "mcq is_correct flag inside options",
                "mcq",
                [
                    {"id": "a", "text": "X", "is_correct": True},
                    {"id": "b", "text": "Y"},
                ],
                "a",
                "options",
            ),
            ("mcq option is not an object", "mcq", ["a", "b"], "a", "options"),
            ("mcq correct id not in options", "mcq", MCQ_OPTIONS, "z", "correct_answer"),
            ("mcq missing correct answer", "mcq", MCQ_OPTIONS, None, "correct_answer"),
            ("mcq correct answer is a list", "mcq", MCQ_OPTIONS, ["a"], "correct_answer"),
            ("true_false with options", "true_false", MCQ_OPTIONS, True, "options"),
            ("true_false string answer", "true_false", None, "true", "correct_answer"),
            ("true_false integer answer", "true_false", None, 1, "correct_answer"),
            ("true_false missing answer", "true_false", None, None, "correct_answer"),
            ("short empty list", "short", None, [], "correct_answer"),
            (
                "short with 11 answers",
                "short",
                None,
                [f"a{i}" for i in range(11)],
                "correct_answer",
            ),
            ("short empty answer", "short", None, ["  "], "correct_answer"),
            ("short answer too long", "short", None, ["x" * 201], "correct_answer"),
            ("short answer is a string", "short", None, "phenol", "correct_answer"),
            ("short with options", "short", MCQ_OPTIONS, ["phenol"], "options"),
            ("essay with options", "essay", MCQ_OPTIONS, "text", "options"),
            ("essay answer not a string", "essay", None, 5, "correct_answer"),
            ("unknown question type", "matching", None, "x", "question_type"),
        ]
        for name, qtype, options, correct, field in cases:
            with self.subTest(name):
                with self.assertRaises(ValidationError) as ctx:
                    validate_question_content(qtype, options, correct)
                self.assertIn(field, ctx.exception.detail)


class NormalizeShortAnswerTests(SimpleTestCase):
    def test_strips_collapses_whitespace_and_lowercases(self):
        self.assertEqual(normalize_short_answer("  Hello   World \n"), "hello world")

    def test_same_answer_with_different_spacing_and_case_matches(self):
        self.assertEqual(
            normalize_short_answer("Phenol"), normalize_short_answer("  PHENOL ")
        )