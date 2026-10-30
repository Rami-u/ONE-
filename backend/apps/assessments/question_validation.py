"""Validation of question content (options and correct answer) by question type.

This is the single place that decides what a valid question looks like. The
API serializers use it now; bulk import and AI generation will use it later.
"""

import re

from rest_framework import serializers

from .models import Question

QuestionType = Question.QuestionType

OPTION_ID_PATTERN = re.compile(r"[a-z0-9_-]{1,10}")
MCQ_MIN_OPTIONS = 2
MCQ_MAX_OPTIONS = 6
OPTION_TEXT_MAX_LENGTH = 500
SHORT_MIN_ANSWERS = 1
SHORT_MAX_ANSWERS = 10
SHORT_ANSWER_MAX_LENGTH = 200


def normalize_short_answer(text):
    """Strip, collapse inner whitespace and lowercase (reused by grading later)."""
    return " ".join(str(text).split()).lower()


def _fail(field, message):
    raise serializers.ValidationError({field: [message]})


def _validate_mcq(options, correct_answer):
    if not isinstance(options, list):
        _fail("options", "Options must be a list of {id, text} objects.")
    if not MCQ_MIN_OPTIONS <= len(options) <= MCQ_MAX_OPTIONS:
        _fail(
            "options",
            f"A multiple choice question needs {MCQ_MIN_OPTIONS} to "
            f"{MCQ_MAX_OPTIONS} options.",
        )

    clean_options = []
    seen_ids = set()
    for option in options:
        if not isinstance(option, dict) or set(option) != {"id", "text"}:
            _fail("options", "Each option must be an object with only 'id' and 'text'.")
        option_id = option["id"]
        text = option["text"]
        if not isinstance(option_id, str) or not OPTION_ID_PATTERN.fullmatch(option_id):
            _fail(
                "options",
                "Option ids must be 1 to 10 characters from a-z, 0-9, '_' and '-'.",
            )
        if option_id in seen_ids:
            _fail("options", "Option ids must be unique.")
        seen_ids.add(option_id)
        if not isinstance(text, str) or not text.strip():
            _fail("options", "Option text must be a non-empty string.")
        text = text.strip()
        if len(text) > OPTION_TEXT_MAX_LENGTH:
            _fail(
                "options",
                f"Option text must be at most {OPTION_TEXT_MAX_LENGTH} characters.",
            )
        clean_options.append({"id": option_id, "text": text})

    if not isinstance(correct_answer, str) or correct_answer not in seen_ids:
        _fail("correct_answer", "The correct answer must be the id of exactly one option.")
    return clean_options, correct_answer


def _validate_true_false(correct_answer):
    if not isinstance(correct_answer, bool):
        _fail("correct_answer", "The correct answer must be true or false.")
    return None, correct_answer


def _validate_short(correct_answer):
    if not isinstance(correct_answer, list) or not (
        SHORT_MIN_ANSWERS <= len(correct_answer) <= SHORT_MAX_ANSWERS
    ):
        _fail(
            "correct_answer",
            f"Provide a list of {SHORT_MIN_ANSWERS} to {SHORT_MAX_ANSWERS} accepted answers.",
        )
    clean_answers = []
    for answer in correct_answer:
        if not isinstance(answer, str) or not answer.strip():
            _fail("correct_answer", "Each accepted answer must be a non-empty string.")
        answer = answer.strip()
        if len(answer) > SHORT_ANSWER_MAX_LENGTH:
            _fail(
                "correct_answer",
                f"Each accepted answer must be at most {SHORT_ANSWER_MAX_LENGTH} characters.",
            )
        clean_answers.append(answer)
    return None, clean_answers


def _validate_essay(correct_answer):
    if correct_answer is None:
        return None, ""
    if not isinstance(correct_answer, str):
        _fail("correct_answer", "The model answer must be a string.")
    return None, correct_answer.strip()


def validate_question_content(question_type, options, correct_answer):
    """Return (clean_options, clean_correct_answer) or raise serializers.ValidationError.

    "options" absent from the request must be passed as None.
    """
    if question_type == QuestionType.MCQ:
        return _validate_mcq(options, correct_answer)

    if question_type not in (
        QuestionType.TRUE_FALSE,
        QuestionType.SHORT,
        QuestionType.ESSAY,
    ):
        _fail("question_type", "Unknown question type.")
    if options is not None:
        _fail("options", "Options are only used by multiple choice questions.")

    if question_type == QuestionType.TRUE_FALSE:
        return _validate_true_false(correct_answer)
    if question_type == QuestionType.SHORT:
        return _validate_short(correct_answer)
    return _validate_essay(correct_answer)