from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.accounts.tests.helpers import create_teacher, create_workspace
from apps.assessments.models import LessonTopic, Question, QuestionTopic, Topic
from apps.assessments.tests.helpers import create_question, create_topic
from apps.courses.tests.helpers import create_course, create_lesson


class QuestionBankModelTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.workspace = create_workspace("question-bank")
        cls.other_workspace = create_workspace("other-question-bank")
        cls.course = create_course(cls.workspace)
        cls.other_course = create_course(cls.workspace, title="Another course")
        cls.foreign_course = create_course(cls.other_workspace)
        cls.lesson = create_lesson(cls.workspace, cls.course)
        cls.other_lesson = create_lesson(cls.workspace, cls.other_course)
        cls.foreign_lesson = create_lesson(cls.other_workspace, cls.foreign_course)
        cls.teacher = create_teacher(cls.workspace)
        cls.foreign_teacher = create_teacher(cls.other_workspace)
        cls.topic = create_topic(cls.workspace, course=cls.course)
        cls.foreign_topic = create_topic(cls.other_workspace, course=cls.foreign_course)
        cls.question = create_question(cls.workspace, course=cls.course, lesson=cls.lesson)
        cls.foreign_question = create_question(cls.other_workspace)

    def test_topic_rejects_cross_workspace_course(self):
        topic = Topic(workspace=self.workspace, course=self.foreign_course, name="Topic", slug="topic")
        with self.assertRaises(ValidationError) as caught:
            topic.clean()
        self.assertEqual(set(caught.exception.message_dict), {"course"})

    def test_topic_accepts_same_workspace_course(self):
        topic = Topic(workspace=self.workspace, course=self.course, name="Topic", slug="new-topic")
        topic.full_clean()

    def test_topic_accepts_no_course(self):
        topic = Topic(workspace=self.workspace, name="Workspace topic", slug="workspace-topic")
        topic.full_clean()

    def test_topic_slug_is_unique_within_workspace(self):
        self.assertEqual(
            [(constraint.name, constraint.fields) for constraint in Topic._meta.constraints],
            [("unique_topic_slug_per_workspace", ("workspace", "slug"))],
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                create_topic(self.workspace, slug=self.topic.slug)

    def test_topic_slug_can_repeat_in_another_workspace(self):
        topic = create_topic(self.other_workspace, slug="another-slug")
        same_slug = create_topic(self.workspace, slug=topic.slug)
        self.assertNotEqual(same_slug.workspace_id, topic.workspace_id)

    def test_topic_defaults_and_field_types(self):
        topic = Topic(workspace=self.workspace, name="Unscoped topic", slug="unscoped")
        self.assertIsNone(topic.course_id)
        self.assertTrue(Topic._meta.get_field("created_at").auto_now_add)
        self.assertIsInstance(Topic._meta.get_field("slug"), models.SlugField)
        self.assertEqual(Topic._meta.get_field("slug").max_length, 150)
        self.assertEqual(Topic._meta.ordering, ["id"])
        self.assertEqual(Topic._meta.db_table, "topics")

    def test_lesson_topic_rejects_cross_workspace_lesson(self):
        link = LessonTopic(workspace=self.workspace, lesson=self.foreign_lesson, topic=self.topic)
        with self.assertRaises(ValidationError) as caught:
            link.clean()
        self.assertEqual(set(caught.exception.message_dict), {"lesson"})

    def test_lesson_topic_rejects_cross_workspace_topic(self):
        link = LessonTopic(workspace=self.workspace, lesson=self.lesson, topic=self.foreign_topic)
        with self.assertRaises(ValidationError) as caught:
            link.clean()
        self.assertEqual(set(caught.exception.message_dict), {"topic"})

    def test_lesson_topic_accepts_same_workspace_relations(self):
        link = LessonTopic(workspace=self.workspace, lesson=self.lesson, topic=self.topic)
        link.full_clean()

    def test_lesson_topic_pair_is_unique(self):
        self.assertEqual(
            [(constraint.name, constraint.fields) for constraint in LessonTopic._meta.constraints],
            [("unique_topic_per_lesson", ("lesson", "topic"))],
        )
        LessonTopic.objects.create(workspace=self.workspace, lesson=self.lesson, topic=self.topic)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LessonTopic.objects.create(workspace=self.workspace, lesson=self.lesson, topic=self.topic)

    def test_lesson_topic_allows_same_topic_in_another_lesson(self):
        first = LessonTopic.objects.create(workspace=self.workspace, lesson=self.lesson, topic=self.topic)
        second = LessonTopic.objects.create(workspace=self.workspace, lesson=self.other_lesson, topic=self.topic)
        self.assertNotEqual(first.lesson_id, second.lesson_id)

    def test_lesson_topic_defaults(self):
        link = LessonTopic(workspace=self.workspace, lesson=self.lesson, topic=self.topic)
        self.assertEqual(link.workspace_id, self.workspace.pk)
        self.assertEqual(LessonTopic._meta.ordering, ["id"])
        self.assertEqual(LessonTopic._meta.db_table, "lesson_topics")

    def test_question_rejects_cross_workspace_course(self):
        question = Question(workspace=self.workspace, course=self.foreign_course)
        with self.assertRaises(ValidationError) as caught:
            question.clean()
        self.assertEqual(set(caught.exception.message_dict), {"course"})

    def test_question_rejects_cross_workspace_lesson(self):
        question = Question(workspace=self.workspace, lesson=self.foreign_lesson)
        with self.assertRaises(ValidationError) as caught:
            question.clean()
        self.assertEqual(set(caught.exception.message_dict), {"lesson"})

    def test_question_rejects_cross_workspace_reviewer(self):
        question = Question(workspace=self.workspace, reviewed_by=self.foreign_teacher)
        with self.assertRaises(ValidationError) as caught:
            question.clean()
        self.assertEqual(set(caught.exception.message_dict), {"reviewed_by"})

    def test_question_rejects_reviewer_without_workspace(self):
        admin_user = User.objects.create_superuser(email="reviewer@example.com", password="Admin-password-123!")
        question = Question(workspace=self.workspace, reviewed_by=admin_user)
        with self.assertRaises(ValidationError) as caught:
            question.clean()
        self.assertEqual(set(caught.exception.message_dict), {"reviewed_by"})

    def test_question_rejects_lesson_from_another_course(self):
        question = Question(workspace=self.workspace, course=self.course, lesson=self.other_lesson)
        with self.assertRaises(ValidationError) as caught:
            question.clean()
        self.assertEqual(set(caught.exception.message_dict), {"lesson"})

    def test_question_accepts_same_workspace_and_course_relations(self):
        question = create_question(
            self.workspace, course=self.course, lesson=self.lesson, reviewed_by=self.teacher,
        )
        question.full_clean()

    def test_question_accepts_no_optional_relations(self):
        question = create_question(self.workspace)
        question.full_clean()

    def test_question_accepts_lesson_without_explicit_course(self):
        question = create_question(self.workspace, lesson=self.lesson)
        question.full_clean()

    def test_question_accepts_course_without_lesson(self):
        question = create_question(self.workspace, course=self.course)
        question.full_clean()

    def test_question_defaults_choices_and_field_types(self):
        question = Question()
        self.assertEqual(question.source_type, "manual")
        self.assertEqual(question.status, "draft")
        self.assertEqual(question.difficulty, "medium")
        self.assertFalse(Question._meta.get_field("points").has_default())
        self.assertFalse(Question._meta.get_field("question_type").has_default())
        self.assertEqual(Question.SourceType.values, ["manual", "ai_generated"])
        self.assertEqual(Question.Status.values, ["draft", "approved", "rejected", "archived"])
        self.assertEqual(Question.QuestionType.values, ["mcq", "true_false", "short", "essay"])
        self.assertEqual(Question.Difficulty.values, ["easy", "medium", "hard"])
        self.assertIsInstance(Question._meta.get_field("correct_answer"), models.JSONField)
        self.assertIsInstance(Question._meta.get_field("options"), models.JSONField)
        self.assertTrue(Question._meta.get_field("created_at").auto_now_add)
        self.assertEqual(Question._meta.ordering, ["-created_at", "id"])
        self.assertEqual(Question._meta.db_table, "questions")

    def test_question_rejects_invalid_choice_values(self):
        for field_name in ("source_type", "status", "question_type", "difficulty"):
            with self.subTest(field=field_name):
                question = create_question(self.workspace)
                setattr(question, field_name, "invalid")
                with self.assertRaises(ValidationError) as caught:
                    question.full_clean()
                self.assertIn(field_name, caught.exception.message_dict)

    def test_question_rejects_negative_points(self):
        question = create_question(self.workspace, points="-0.01")
        with self.assertRaises(ValidationError) as caught:
            question.full_clean()
        self.assertIn("points", caught.exception.message_dict)

    def test_question_accepts_zero_points(self):
        question = create_question(self.workspace, points="0.00")
        question.full_clean()
        self.assertEqual(question.points, Decimal("0.00"))

    def test_question_requires_points(self):
        question = Question(workspace=self.workspace, stem="Prompt", question_type="mcq", correct_answer="A")
        with self.assertRaises(ValidationError) as caught:
            question.full_clean()
        self.assertIn("points", caught.exception.message_dict)

    def test_question_requires_question_type(self):
        question = Question(workspace=self.workspace, stem="Prompt", points=1, correct_answer="A")
        with self.assertRaises(ValidationError) as caught:
            question.full_clean()
        self.assertIn("question_type", caught.exception.message_dict)

    def test_question_topic_rejects_cross_workspace_question(self):
        link = QuestionTopic(workspace=self.workspace, question=self.foreign_question, topic=self.topic)
        with self.assertRaises(ValidationError) as caught:
            link.clean()
        self.assertEqual(set(caught.exception.message_dict), {"question"})

    def test_question_topic_rejects_cross_workspace_topic(self):
        link = QuestionTopic(workspace=self.workspace, question=self.question, topic=self.foreign_topic)
        with self.assertRaises(ValidationError) as caught:
            link.clean()
        self.assertEqual(set(caught.exception.message_dict), {"topic"})

    def test_question_topic_accepts_same_workspace_relations(self):
        link = QuestionTopic(workspace=self.workspace, question=self.question, topic=self.topic)
        link.full_clean()

    def test_question_topic_pair_is_unique(self):
        self.assertEqual(
            [(constraint.name, constraint.fields) for constraint in QuestionTopic._meta.constraints],
            [("unique_topic_per_question", ("question", "topic"))],
        )
        QuestionTopic.objects.create(workspace=self.workspace, question=self.question, topic=self.topic)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                QuestionTopic.objects.create(workspace=self.workspace, question=self.question, topic=self.topic)

    def test_question_topic_allows_same_topic_for_another_question(self):
        second_question = create_question(self.workspace)
        first = QuestionTopic.objects.create(workspace=self.workspace, question=self.question, topic=self.topic)
        second = QuestionTopic.objects.create(workspace=self.workspace, question=second_question, topic=self.topic)
        self.assertNotEqual(first.question_id, second.question_id)

    def test_question_topic_defaults(self):
        link = QuestionTopic(workspace=self.workspace, question=self.question, topic=self.topic)
        self.assertEqual(link.workspace_id, self.workspace.pk)
        self.assertEqual(QuestionTopic._meta.ordering, ["id"])
        self.assertEqual(QuestionTopic._meta.db_table, "question_topics")

    def test_question_bank_foreign_keys_are_protected_and_named(self):
        for model in (Topic, LessonTopic, Question, QuestionTopic):
            for field in model._meta.fields:
                if isinstance(field, models.ForeignKey):
                    with self.subTest(model=model.__name__, field=field.name):
                        self.assertIs(field.remote_field.on_delete, models.PROTECT)
                        expected = "reviewed_questions" if field.name == "reviewed_by" else model._meta.db_table
                        self.assertEqual(field.remote_field.related_name, expected)
