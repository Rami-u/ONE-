from django.core.exceptions import ValidationError
from django.db import models
from rest_framework.test import APITestCase

from apps.accounts.tests.helpers import create_workspace
from apps.courses.models import CourseSection, Lesson, LessonAsset
from apps.courses.tests.helpers import (
    create_course,
    create_lesson,
    create_lesson_asset,
    create_section,
)


class ContentModelTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.workspace = create_workspace("content-one")
        cls.other_workspace = create_workspace("content-two")
        cls.course = create_course(cls.workspace)
        cls.other_course = create_course(cls.other_workspace)
        cls.section = create_section(cls.workspace, cls.course)
        cls.lesson = create_lesson(cls.workspace, cls.course, section=cls.section)
        cls.other_lesson = create_lesson(cls.other_workspace, cls.other_course)

    def test_section_accepts_its_courses_workspace(self):
        section = create_section(self.workspace, self.course)
        section.full_clean()

    def test_section_rejects_a_course_from_another_workspace(self):
        section = CourseSection(
            workspace=self.workspace, course=self.other_course, title="Invalid section"
        )
        with self.assertRaises(ValidationError) as error:
            section.full_clean()
        self.assertEqual(set(error.exception.message_dict), {"course"})

    def test_section_defaults(self):
        section = create_section(self.workspace, self.course)
        self.assertEqual(section.position, 1)
        self.assertIsNotNone(section.created_at)
        self.assertTrue(CourseSection._meta.get_field("created_at").auto_now_add)
        self.assertEqual(CourseSection._meta.ordering, ["position", "id"])

    def test_lesson_accepts_relations_in_the_same_workspace_and_course(self):
        self.lesson.full_clean()

    def test_lesson_rejects_a_course_from_another_workspace(self):
        lesson = Lesson(
            workspace=self.workspace, course=self.other_course, title="Invalid lesson"
        )
        with self.assertRaises(ValidationError) as error:
            lesson.full_clean()
        self.assertEqual(set(error.exception.message_dict), {"course"})

    def test_lesson_rejects_a_section_from_another_workspace(self):
        # Keep the course equal so only the section's workspace is invalid.
        section = create_section(self.other_workspace, self.course)
        lesson = Lesson(
            workspace=self.workspace,
            course=self.course,
            section=section,
            title="Invalid lesson",
        )
        with self.assertRaises(ValidationError) as error:
            lesson.full_clean()
        self.assertEqual(set(error.exception.message_dict), {"section"})

    def test_lesson_rejects_a_section_in_another_course_of_the_same_workspace(self):
        course = create_course(self.workspace, title="Another course")
        section = create_section(self.workspace, course)
        lesson = Lesson(
            workspace=self.workspace,
            course=self.course,
            section=section,
            title="Invalid lesson",
        )
        with self.assertRaises(ValidationError) as error:
            lesson.full_clean()
        self.assertEqual(set(error.exception.message_dict), {"section"})

    def test_lesson_accepts_an_unset_section(self):
        lesson = create_lesson(self.workspace, self.course)
        lesson.full_clean()
        self.assertIsNone(lesson.section_id)

    def test_lesson_defaults(self):
        lesson = create_lesson(self.workspace, self.course)
        self.assertEqual(lesson.position, 1)
        self.assertTrue(lesson.is_published)
        self.assertIsNone(lesson.content)
        self.assertIsNotNone(lesson.created_at)
        self.assertTrue(Lesson._meta.get_field("created_at").auto_now_add)
        self.assertEqual(Lesson._meta.ordering, ["position", "id"])

    def test_asset_accepts_its_lessons_workspace(self):
        asset = create_lesson_asset(self.workspace, self.lesson)
        asset.full_clean()

    def test_asset_rejects_a_lesson_from_another_workspace(self):
        asset = LessonAsset(
            workspace=self.workspace,
            lesson=self.other_lesson,
            title="Invalid asset",
            asset_type=LessonAsset.AssetType.PDF,
            storage_key="lessons/example.pdf",
        )
        with self.assertRaises(ValidationError) as error:
            asset.full_clean()
        self.assertEqual(set(error.exception.message_dict), {"lesson"})

    def test_asset_defaults_and_choices(self):
        asset = create_lesson_asset(self.workspace, self.lesson)
        self.assertEqual(asset.extraction_status, "pending")
        self.assertEqual(
            LessonAsset.AssetType.values, ["pdf", "video", "slide", "doc", "audio"]
        )
        self.assertEqual(
            LessonAsset.ExtractionStatus.values, ["pending", "running", "done", "failed"]
        )
        self.assertEqual(
            LessonAsset._meta.get_field("asset_type").choices,
            LessonAsset.AssetType.choices,
        )
        self.assertEqual(
            LessonAsset._meta.get_field("extraction_status").choices,
            LessonAsset.ExtractionStatus.choices,
        )
        self.assertIsNone(asset.mime_type)
        self.assertIsNone(asset.file_size)
        self.assertIsNone(asset.extracted_text)
        self.assertIsNotNone(asset.created_at)
        self.assertTrue(LessonAsset._meta.get_field("created_at").auto_now_add)
        self.assertEqual(LessonAsset._meta.ordering, ["id"])

    def test_asset_choice_fields_reject_unknown_values(self):
        for field in ("asset_type", "extraction_status"):
            with self.subTest(field=field):
                asset = create_lesson_asset(self.workspace, self.lesson)
                setattr(asset, field, "unknown")
                with self.assertRaises(ValidationError) as error:
                    asset.full_clean()
                self.assertEqual(set(error.exception.message_dict), {field})

    def test_asset_storage_key_is_a_plain_string(self):
        field = LessonAsset._meta.get_field("storage_key")
        self.assertIs(type(field), models.CharField)
        self.assertEqual(field.max_length, 500)
        self.assertFalse(any(isinstance(field, models.FileField) for field in LessonAsset._meta.fields))
