from django.urls import reverse

from apps.assessments.models import Question, QuestionTopic
from apps.assessments.tests.content_base import ContentApiBase
from apps.assessments.tests.helpers import create_question, create_topic
from apps.courses.tests.helpers import create_course


def mcq_payload(**overrides):
    payload = {
        "question_type": "mcq",
        "stem": "Which formula is benzene?",
        "options": [
            {"id": "a", "text": "C6H12"},
            {"id": "b", "text": "C6H6"},
        ],
        "correct_answer": "b",
        "points": "1.00",
    }
    payload.update(overrides)
    return payload


class QuestionApiBase(ContentApiBase):
    def list_url(self, slug="alpha"):
        return reverse("question-list-create", kwargs={"slug": slug})

    def detail_url(self, question_id, slug="alpha"):
        return reverse("question-detail", kwargs={"slug": slug, "question_id": question_id})


class QuestionCreateTests(QuestionApiBase):
    def setUp(self):
        self.login(self.alpha_teacher)

    def test_create_mcq_defaults_to_approved_manual(self):
        response = self.client.post(self.list_url(), mcq_payload(), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "approved")
        self.assertEqual(response.data["source_type"], "manual")
        question = Question.objects.get(pk=response.data["id"])
        self.assertEqual(question.workspace, self.alpha)

    def test_create_as_draft(self):
        response = self.client.post(self.list_url(), mcq_payload(status="draft"), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "draft")

    def test_status_rejected_on_create_is_400(self):
        response = self.client.post(self.list_url(), mcq_payload(status="rejected"), format="json")
        self.assertEqual(response.status_code, 400)

    def test_true_false_with_false_answer(self):
        response = self.client.post(
            self.list_url(),
            {"question_type": "true_false", "stem": "Sky is green", "correct_answer": False, "points": "1"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIs(response.data["correct_answer"], False)

    def test_short_answer(self):
        response = self.client.post(
            self.list_url(),
            {"question_type": "short", "stem": "Name C6H5OH", "correct_answer": ["phenol"], "points": "2"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)

    def test_essay_without_answer_stores_empty_string(self):
        response = self.client.post(
            self.list_url(),
            {"question_type": "essay", "stem": "Explain benzene", "points": "5"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Question.objects.get(pk=response.data["id"]).correct_answer, "")

    def test_invalid_mcq_content_is_400(self):
        response = self.client.post(
            self.list_url(), mcq_payload(correct_answer="zzz"), format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("correct_answer", response.data)

    def test_points_must_be_positive(self):
        response = self.client.post(self.list_url(), mcq_payload(points="0"), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("points", response.data)

    def test_stem_is_required(self):
        payload = mcq_payload()
        del payload["stem"]
        response = self.client.post(self.list_url(), payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("stem", response.data)

    def test_body_workspace_source_and_reviewer_are_ignored(self):
        response = self.client.post(
            self.list_url(),
            mcq_payload(
                workspace=self.beta.pk,
                source_type="ai_generated",
                reviewed_by=self.beta_teacher.pk,
            ),
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        question = Question.objects.get(pk=response.data["id"])
        self.assertEqual(question.workspace, self.alpha)
        self.assertEqual(question.source_type, "manual")
        self.assertIsNone(question.reviewed_by)

    def test_topic_ids_create_links(self):
        topic = create_topic(self.alpha, name="T", slug="t")
        response = self.client.post(self.list_url(), mcq_payload(topic_ids=[topic.pk]), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["topics"], [{"id": topic.pk, "name": "T"}])
        self.assertEqual(QuestionTopic.objects.filter(question_id=response.data["id"]).count(), 1)

    def test_topic_from_another_workspace_is_400(self):
        other = create_topic(self.beta, name="B", slug="b")
        response = self.client.post(self.list_url(), mcq_payload(topic_ids=[other.pk]), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("topic_ids", response.data)
        self.assertFalse(Question.objects.filter(workspace=self.alpha).exists())

    def test_course_from_another_workspace_is_400(self):
        response = self.client.post(
            self.list_url(), mcq_payload(course=self.beta_course.pk), format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("course", response.data)


class QuestionListTests(QuestionApiBase):
    def setUp(self):
        self.login(self.alpha_teacher)

    def test_list_only_own_workspace_and_paginated(self):
        for i in range(21):
            create_question(self.alpha, stem=f"Q{i}", correct_answer="x")
        create_question(self.beta, stem="Other", correct_answer="x")
        response = self.client.get(self.list_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 21)
        self.assertEqual(len(response.data["results"]), 20)

    def test_filters(self):
        create_question(self.alpha, stem="Benzene ring", question_type="mcq", status="approved")
        create_question(self.alpha, stem="Alkane chain", question_type="essay", status="draft")
        by_status = self.client.get(self.list_url(), {"status": "draft"})
        self.assertEqual([r["stem"] for r in by_status.data["results"]], ["Alkane chain"])
        by_type = self.client.get(self.list_url(), {"question_type": "mcq"})
        self.assertEqual([r["stem"] for r in by_type.data["results"]], ["Benzene ring"])
        by_search = self.client.get(self.list_url(), {"search": "BENZENE"})
        self.assertEqual([r["stem"] for r in by_search.data["results"]], ["Benzene ring"])

    def test_filter_by_topic(self):
        topic = create_topic(self.alpha, name="T", slug="t")
        linked = create_question(self.alpha, stem="Linked")
        create_question(self.alpha, stem="Unlinked")
        QuestionTopic.objects.create(workspace=self.alpha, question=linked, topic=topic)
        response = self.client.get(self.list_url(), {"topic": topic.pk})
        self.assertEqual([r["stem"] for r in response.data["results"]], ["Linked"])

    def test_invalid_filters_are_400(self):
        self.assertEqual(self.client.get(self.list_url(), {"course": "abc"}).status_code, 400)
        self.assertEqual(self.client.get(self.list_url(), {"status": "bogus"}).status_code, 400)


class QuestionUpdateTests(QuestionApiBase):
    def setUp(self):
        self.login(self.alpha_teacher)
        created = self.client.post(self.list_url(), mcq_payload(), format="json")
        self.question_id = created.data["id"]

    def test_patch_stem_and_difficulty(self):
        response = self.client.patch(
            self.detail_url(self.question_id), {"stem": "New stem", "difficulty": "hard"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["stem"], "New stem")
        self.assertEqual(response.data["difficulty"], "hard")

    def test_patch_correct_answer_is_revalidated(self):
        bad = self.client.patch(self.detail_url(self.question_id), {"correct_answer": "zzz"}, format="json")
        self.assertEqual(bad.status_code, 400)
        good = self.client.patch(self.detail_url(self.question_id), {"correct_answer": "a"}, format="json")
        self.assertEqual(good.status_code, 200, good.data)

    def test_patch_question_type_or_status_is_400(self):
        for body in ({"question_type": "essay"}, {"status": "draft"}):
            response = self.client.patch(self.detail_url(self.question_id), body, format="json")
            self.assertEqual(response.status_code, 400, body)
        question = Question.objects.get(pk=self.question_id)
        self.assertEqual(question.question_type, "mcq")
        self.assertEqual(question.status, "approved")

    def test_patch_replaces_topics(self):
        t1 = create_topic(self.alpha, name="T1", slug="t1")
        t2 = create_topic(self.alpha, name="T2", slug="t2")
        self.client.patch(self.detail_url(self.question_id), {"topic_ids": [t1.pk]}, format="json")
        response = self.client.patch(self.detail_url(self.question_id), {"topic_ids": [t2.pk]}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([t["id"] for t in response.data["topics"]], [t2.pk])
        cleared = self.client.patch(self.detail_url(self.question_id), {"topic_ids": []}, format="json")
        self.assertEqual(cleared.data["topics"], [])

    def test_patch_without_topic_ids_keeps_topics(self):
        topic = create_topic(self.alpha, name="T", slug="t")
        self.client.patch(self.detail_url(self.question_id), {"topic_ids": [topic.pk]}, format="json")
        response = self.client.patch(self.detail_url(self.question_id), {"stem": "Changed"}, format="json")
        self.assertEqual(len(response.data["topics"]), 1)

    def test_patch_lesson_sets_course_from_lesson_mismatch_is_400(self):
        other_course = create_course(self.alpha, title="Other")
        response = self.client.patch(
            self.detail_url(self.question_id),
            {"course": other_course.pk, "lesson": 999999},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_is_not_allowed(self):
        response = self.client.delete(self.detail_url(self.question_id))
        self.assertEqual(response.status_code, 405)