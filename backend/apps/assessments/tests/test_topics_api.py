from django.urls import reverse

from apps.assessments.models import Topic
from apps.assessments.tests.content_base import ContentApiBase
from apps.assessments.tests.helpers import create_topic


class TopicApiBase(ContentApiBase):
    def list_url(self, slug="alpha"):
        return reverse("topic-list-create", kwargs={"slug": slug})

    def detail_url(self, topic_id, slug="alpha"):
        return reverse("topic-detail", kwargs={"slug": slug, "topic_id": topic_id})


class TopicCreateTests(TopicApiBase):
    def setUp(self):
        self.login(self.alpha_teacher)

    def test_create_generates_slug_from_name(self):
        response = self.client.post(self.list_url(), {"name": "Benzene Structure"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["slug"], "benzene-structure")
        self.assertIsNone(response.data["course"])
        topic = Topic.objects.get(pk=response.data["id"])
        self.assertEqual(topic.workspace, self.alpha)

    def test_generated_slug_gets_suffix_on_collision(self):
        slugs = []
        for _ in range(3):
            response = self.client.post(self.list_url(), {"name": "Alkanes"}, format="json")
            self.assertEqual(response.status_code, 201)
            slugs.append(response.data["slug"])
        self.assertEqual(slugs, ["alkanes", "alkanes-2", "alkanes-3"])

    def test_name_without_letters_falls_back_to_topic(self):
        response = self.client.post(self.list_url(), {"name": "!!!"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["slug"], "topic")

    def test_explicit_slug_is_used(self):
        response = self.client.post(
            self.list_url(), {"name": "Alkenes", "slug": "my-alkenes"}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["slug"], "my-alkenes")

    def test_duplicate_explicit_slug_is_400(self):
        create_topic(self.alpha, name="Existing", slug="taken")
        response = self.client.post(
            self.list_url(), {"name": "Other", "slug": "taken"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Topic.objects.filter(workspace=self.alpha, slug="taken").count(), 1)

    def test_same_slug_allowed_in_another_workspace(self):
        create_topic(self.beta, name="Existing", slug="shared")
        response = self.client.post(
            self.list_url(), {"name": "Shared", "slug": "shared"}, format="json"
        )
        self.assertEqual(response.status_code, 201)

    def test_create_with_own_workspace_course(self):
        response = self.client.post(
            self.list_url(),
            {"name": "With course", "course": self.alpha_course.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["course"], self.alpha_course.pk)

    def test_course_from_another_workspace_is_rejected(self):
        response = self.client.post(
            self.list_url(),
            {"name": "Bad course", "course": self.beta_course.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("course", response.data)
        self.assertFalse(Topic.objects.filter(name="Bad course").exists())

    def test_workspace_in_body_is_ignored(self):
        response = self.client.post(
            self.list_url(),
            {"name": "Sneaky", "workspace": self.beta.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Topic.objects.get(pk=response.data["id"]).workspace, self.alpha)

    def test_name_is_required(self):
        response = self.client.post(self.list_url(), {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.data)

    def test_name_max_length_is_150(self):
        ok = self.client.post(self.list_url(), {"name": "a" * 150}, format="json")
        self.assertEqual(ok.status_code, 201)
        too_long = self.client.post(self.list_url(), {"name": "a" * 151}, format="json")
        self.assertEqual(too_long.status_code, 400)
        self.assertIn("name", too_long.data)


class TopicListTests(TopicApiBase):
    def setUp(self):
        self.login(self.alpha_teacher)

    def test_list_is_paginated(self):
        for i in range(25):
            create_topic(self.alpha, name=f"Topic {i}", slug=f"topic-{i}")
        response = self.client.get(self.list_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(len(response.data["results"]), 20)
        page_two = self.client.get(self.list_url(), {"page": 2})
        self.assertEqual(len(page_two.data["results"]), 5)

    def test_list_only_returns_own_workspace(self):
        create_topic(self.alpha, name="Mine", slug="mine")
        create_topic(self.beta, name="Theirs", slug="theirs")
        response = self.client.get(self.list_url())
        names = [row["name"] for row in response.data["results"]]
        self.assertEqual(names, ["Mine"])

    def test_filter_by_course(self):
        create_topic(self.alpha, course=self.alpha_course, name="In course", slug="in-course")
        create_topic(self.alpha, name="No course", slug="no-course")
        response = self.client.get(self.list_url(), {"course": self.alpha_course.pk})
        self.assertEqual(response.status_code, 200)
        names = [row["name"] for row in response.data["results"]]
        self.assertEqual(names, ["In course"])

    def test_invalid_course_filter_is_400(self):
        response = self.client.get(self.list_url(), {"course": "abc"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("course", response.data)


class TopicDetailTests(TopicApiBase):
    def setUp(self):
        self.login(self.alpha_teacher)
        self.topic = create_topic(self.alpha, name="Original", slug="original")

    def test_retrieve(self):
        response = self.client.get(self.detail_url(self.topic.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Original")
        self.assertEqual(response.data["slug"], "original")

    def test_patch_name(self):
        response = self.client.patch(
            self.detail_url(self.topic.pk), {"name": "Renamed"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.topic.refresh_from_db()
        self.assertEqual(self.topic.name, "Renamed")
        self.assertEqual(self.topic.slug, "original")

    def test_patch_slug_to_existing_is_400(self):
        create_topic(self.alpha, name="Other", slug="other")
        response = self.client.patch(
            self.detail_url(self.topic.pk), {"slug": "other"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.topic.refresh_from_db()
        self.assertEqual(self.topic.slug, "original")

    def test_patch_keeping_own_slug_is_ok(self):
        response = self.client.patch(
            self.detail_url(self.topic.pk), {"slug": "original"}, format="json"
        )
        self.assertEqual(response.status_code, 200)

    def test_patch_link_and_unlink_course(self):
        linked = self.client.patch(
            self.detail_url(self.topic.pk), {"course": self.alpha_course.pk}, format="json"
        )
        self.assertEqual(linked.status_code, 200)
        self.assertEqual(linked.data["course"], self.alpha_course.pk)
        unlinked = self.client.patch(
            self.detail_url(self.topic.pk), {"course": None}, format="json"
        )
        self.assertEqual(unlinked.status_code, 200)
        self.assertIsNone(unlinked.data["course"])

    def test_patch_course_from_another_workspace_is_400(self):
        response = self.client.patch(
            self.detail_url(self.topic.pk), {"course": self.beta_course.pk}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.topic.refresh_from_db()
        self.assertIsNone(self.topic.course)

    def test_delete_is_not_allowed(self):
        response = self.client.delete(self.detail_url(self.topic.pk))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Topic.objects.filter(pk=self.topic.pk).exists())


class TopicAccessTests(TopicApiBase):
    def setUp(self):
        self.topic = create_topic(self.alpha, name="Guarded", slug="guarded")
        self.beta_topic = create_topic(self.beta, name="Beta topic", slug="beta-topic")

    def assert_denied(self, response):
        self.assertIn(response.status_code, (401, 403))

    def test_anonymous_is_denied(self):
        self.assert_denied(self.client.get(self.list_url()))
        self.assert_denied(self.client.post(self.list_url(), {"name": "x"}, format="json"))
        self.assert_denied(self.client.get(self.detail_url(self.topic.pk)))

    def test_approved_student_is_denied(self):
        self.login(self.approved_student)
        self.assert_denied(self.client.get(self.list_url()))
        self.assert_denied(self.client.post(self.list_url(), {"name": "x"}, format="json"))
        self.assert_denied(self.client.get(self.detail_url(self.topic.pk)))
        self.assert_denied(
            self.client.patch(self.detail_url(self.topic.pk), {"name": "x"}, format="json")
        )

    def test_pending_student_is_denied(self):
        self.login(self.pending_student)
        self.assert_denied(self.client.get(self.list_url()))
        self.assert_denied(self.client.post(self.list_url(), {"name": "x"}, format="json"))

    def test_teacher_of_another_workspace_is_denied_on_this_workspace(self):
        self.login(self.beta_teacher)
        self.assert_denied(self.client.get(self.list_url("alpha")))
        self.assert_denied(self.client.post(self.list_url("alpha"), {"name": "x"}, format="json"))
        self.assert_denied(self.client.get(self.detail_url(self.topic.pk, "alpha")))
        self.assert_denied(
            self.client.patch(self.detail_url(self.topic.pk, "alpha"), {"name": "x"}, format="json")
        )
        self.topic.refresh_from_db()
        self.assertEqual(self.topic.name, "Guarded")

    def test_teacher_cannot_reach_other_workspace_topic_by_id(self):
        self.login(self.alpha_teacher)
        get_response = self.client.get(self.detail_url(self.beta_topic.pk, "alpha"))
        self.assertEqual(get_response.status_code, 404)
        patch_response = self.client.patch(
            self.detail_url(self.beta_topic.pk, "alpha"), {"name": "Hacked"}, format="json"
        )
        self.assertEqual(patch_response.status_code, 404)
        self.beta_topic.refresh_from_db()
        self.assertEqual(self.beta_topic.name, "Beta topic")

    def test_unknown_workspace_is_404(self):
        self.login(self.alpha_teacher)
        self.assertEqual(self.client.get(self.list_url("does-not-exist")).status_code, 404)
        self.assertEqual(
            self.client.get(self.detail_url(self.topic.pk, "does-not-exist")).status_code, 404
        )
