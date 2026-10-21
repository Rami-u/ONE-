from decimal import Decimal
from io import BytesIO
import os

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.courses.models import Course
from apps.workspaces.models import Workspace


def make_workspace(slug, *, listed=True, status=Workspace.Status.ACTIVE, name=None, headline=None):
    workspace = Workspace.objects.create(
        slug=slug,
        name=name or f"{slug.title()} Academy",
        headline=headline,
        is_listed=listed,
        status=status,
    )
    User.objects.create_user(
        email=f"teacher-{slug}@example.com",
        full_name=f"Teacher {slug.title()}",
        password="valid-test-password",
        role=User.Role.TEACHER,
        workspace=workspace,
    )
    return workspace


def image_upload(*, name="logo.png", image_format="PNG"):
    buffer = BytesIO()
    Image.new("RGB", (2, 2), "blue").save(buffer, format=image_format)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class PublicShowcaseTests(APITestCase):
    def setUp(self):
        self.listed = make_workspace("listed", name="Listed Science", headline="Chemistry")
        self.unlisted = make_workspace("hidden", listed=False, headline="Hidden science")
        self.suspended = make_workspace(
            "stopped", listed=True, status=Workspace.Status.SUSPENDED
        )

    def assert_no_private_fields(self, data):
        def visit(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    field_name = key.lower()
                    self.assertNotIn("email", field_name)
                    self.assertNotIn("password", field_name)
                    self.assertNotIn("login_key", field_name)
                    self.assertNotIn("student_count", field_name)
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(data)

    def test_directory_is_listed_active_paginated_and_searchable(self):
        response = self.client.get("/api/v1/public/teachers/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["teacher_name"], "Teacher Listed")
        self.assert_no_private_fields(response.data)

        response = self.client.get("/api/v1/public/teachers/?search=chem")
        self.assertEqual(response.data["count"], 1)
        response = self.client.get("/api/v1/public/teachers/?search=hidden")
        self.assertEqual(response.data["count"], 0)

        for index in range(21):
            make_workspace(f"teacher-{index:02d}")
        response = self.client.get("/api/v1/public/teachers/")
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIsNotNone(response.data["next"])

    def test_public_profile_safe_fields_courses_and_listing_policy(self):
        self.listed.bio = "Short public biography"
        self.listed.about = "Long public description"
        self.listed.save(update_fields=["bio", "about"])

        Course.objects.create(
            workspace=self.listed,
            title="Published Chemistry",
            description="Intro to organic chemistry",
            price=Decimal("199.99"),
            is_published=True,
        )
        Course.objects.create(
            workspace=self.listed,
            title="Draft Chemistry",
            description="Draft syllabus",
            price=Decimal("50.00"),
            is_published=False,
        )

        response = self.client.get("/api/v1/public/teachers/listed/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["teacher_name"], "Teacher Listed")
        self.assertEqual(response.data["bio"], "Short public biography")
        self.assertEqual(len(response.data["courses"]), 1)
        self.assertEqual(response.data["courses"][0]["title"], "Published Chemistry")
        self.assertEqual(response.data["courses"][0]["description"], "Intro to organic chemistry")
        self.assertEqual(response.data["courses"][0]["price"], "199.99")
        self.assert_no_private_fields(response.data)
        self.assertEqual(
            self.client.get("/api/v1/public/teachers/hidden/").status_code, 404
        )
        self.assertEqual(
            self.client.get("/api/v1/public/teachers/stopped/").status_code, 404
        )

    def test_branding_and_workspace_public_profile_allow_active_unlisted(self):
        Course.objects.create(
            workspace=self.unlisted,
            title="Unlisted Science Course",
            price=Decimal("80.00"),
            is_published=True,
        )
        for endpoint in ("branding", "public-profile"):
            response = self.client.get(f"/api/v1/workspaces/hidden/{endpoint}/")
            self.assertEqual(response.status_code, 200)
            self.assert_no_private_fields(response.data)
        profile = self.client.get("/api/v1/workspaces/hidden/public-profile/")
        self.assertEqual(len(profile.data["courses"]), 1)
        self.assertEqual(profile.data["courses"][0]["title"], "Unlisted Science Course")
        self.assertEqual(profile.data["courses"][0]["price"], "80.00")
        suspended_branding = self.client.get("/api/v1/workspaces/stopped/branding/")
        self.assertEqual(suspended_branding.status_code, 403)
        self.assertEqual(suspended_branding.data["detail"], "Workspace is unavailable.")
        unavailable = self.client.get("/api/v1/workspaces/stopped/public-profile/")
        self.assertEqual(unavailable.status_code, 403)
        self.assertEqual(unavailable.data["detail"], "Workspace is unavailable.")
        unknown_branding = self.client.get("/api/v1/workspaces/missing/branding/")
        unknown_profile = self.client.get("/api/v1/workspaces/missing/public-profile/")
        self.assertEqual(unknown_branding.status_code, 404)
        self.assertEqual(unknown_branding.data["detail"], "Workspace not found.")
        self.assertEqual(unknown_profile.status_code, 404)
        self.assertEqual(unknown_profile.data["detail"], "Workspace not found.")
        self.assertNotEqual(suspended_branding.status_code, unknown_branding.status_code)

    def test_suspended_workspace_settings_are_forbidden_without_changes(self):
        teacher = self.suspended.users.get(role=User.Role.TEACHER)
        self.client.force_authenticate(teacher)
        original_name = self.suspended.name

        get_response = self.client.get("/api/v1/workspaces/stopped/")
        patch_response = self.client.patch(
            "/api/v1/workspaces/stopped/", {"name": "Must Not Change"}, format="json"
        )
        self.assertEqual(get_response.status_code, 403)
        self.assertEqual(get_response.data["detail"], "Workspace is unavailable.")
        self.assertEqual(patch_response.status_code, 403)
        self.assertEqual(patch_response.data["detail"], "Workspace is unavailable.")
        self.suspended.refresh_from_db()
        self.assertEqual(self.suspended.name, original_name)

    def test_workspace_settings_require_authentication_for_get_and_patch(self):
        get_response = self.client.get("/api/v1/workspaces/listed/")
        patch_response = self.client.patch(
            "/api/v1/workspaces/listed/", {"name": "Must Not Change"}, format="json"
        )
        self.assertEqual(get_response.status_code, 403)
        self.assertEqual(patch_response.status_code, 403)
        self.listed.refresh_from_db()
        self.assertEqual(self.listed.name, "Listed Science")

    def test_existing_logo_url_references_remain_publicly_usable(self):
        self.listed.logo = "https://cdn.example.com/legacy-logo.png"
        self.listed.save(update_fields=["logo"])
        response = self.client.get("/api/v1/workspaces/listed/branding/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["logo"], self.listed.logo.name)

    def test_uploaded_logo_url_is_identical_across_public_endpoints(self):
        from apps.workspaces.storage import public_logo_storage

        teacher = self.listed.users.get(role=User.Role.TEACHER)
        self.client.force_authenticate(teacher)
        settings_response = self.client.patch(
            "/api/v1/workspaces/listed/",
            {"logo": image_upload()},
            format="multipart",
        )
        self.assertEqual(settings_response.status_code, 200, settings_response.data)
        self.listed.refresh_from_db()
        logo_path = self.listed.logo.name
        self.addCleanup(public_logo_storage.delete, logo_path)

        endpoint_values = [
            settings_response.data["logo"],
            self.client.get("/api/v1/workspaces/listed/branding/").data["logo"],
            self.client.get("/api/v1/workspaces/listed/public-profile/").data["logo"],
            self.client.get("/api/v1/public/teachers/listed/").data["logo"],
            next(
                item["logo"]
                for item in self.client.get("/api/v1/public/teachers/").data["results"]
                if item["slug"] == "listed"
            ),
        ]
        self.assertTrue(endpoint_values[0].startswith("http://testserver/media/"))
        self.assertTrue(endpoint_values[0].endswith(logo_path))
        self.assertEqual(endpoint_values, [endpoint_values[0]] * 5)

    def test_settings_patch_is_scoped_teacher_only_and_slug_is_immutable(self):
        teacher = self.listed.users.get(role=User.Role.TEACHER)
        self.client.force_authenticate(teacher)
        response = self.client.patch(
            "/api/v1/workspaces/listed/",
            {
                "name": "Updated Academy",
                "headline": "New headline",
                "bio": "Bio",
                "about": "About",
                "is_listed": False,
                "payment_instructions": "Transfer details",
                "slug": "new-slug",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.listed.refresh_from_db()
        self.assertEqual(self.listed.slug, "listed")
        self.assertEqual(self.listed.name, "Updated Academy")
        self.assertFalse(self.listed.is_listed)

        other_teacher = self.unlisted.users.get(role=User.Role.TEACHER)
        self.client.force_authenticate(other_teacher)
        self.assertEqual(
            self.client.patch(
                "/api/v1/workspaces/listed/", {"name": "Wrong tenant"}, format="json"
            ).status_code,
            403,
        )
        student = User.objects.create_user(
            email="student@example.com",
            full_name="Student",
            password="valid-test-password",
            role=User.Role.STUDENT,
            workspace=self.listed,
        )
        self.client.force_authenticate(student)
        self.assertEqual(self.client.get("/api/v1/workspaces/listed/").status_code, 403)

    def test_logo_upload_validation_and_public_storage(self):
        from apps.workspaces.storage import public_logo_storage

        teacher = self.listed.users.get(role=User.Role.TEACHER)
        self.client.force_authenticate(teacher)
        url = "/api/v1/workspaces/listed/"
        valid = self.client.patch(url, {"logo": image_upload()}, format="multipart")
        self.assertEqual(valid.status_code, 200, valid.data)
        self.listed.refresh_from_db()
        self.assertTrue(valid.data["logo"].startswith("http://testserver/media/"))
        self.assertTrue(valid.data["logo"].endswith(self.listed.logo.name))
        self.assertTrue(public_logo_storage.exists(self.listed.logo.name))
        self.addCleanup(public_logo_storage.delete, self.listed.logo.name)

        webp = self.client.patch(
            url,
            {"logo": image_upload(name="logo.webp", image_format="WEBP")},
            format="multipart",
        )
        self.assertEqual(webp.status_code, 200, webp.data)
        self.listed.refresh_from_db()
        self.addCleanup(public_logo_storage.delete, self.listed.logo.name)

        invalid = self.client.patch(
            url,
            {"logo": image_upload(name="logo.gif", image_format="GIF")},
            format="multipart",
        )
        self.assertEqual(invalid.status_code, 400)

    def test_valid_logo_larger_than_two_megabytes_is_rejected(self):
        teacher = self.listed.users.get(role=User.Role.TEACHER)
        self.client.force_authenticate(teacher)
        image_bytes = BytesIO()
        image = Image.frombytes("RGB", (1200, 1200), os.urandom(1200 * 1200 * 3))
        image.save(image_bytes, format="PNG")
        content = image_bytes.getvalue()
        self.assertGreater(len(content), 2 * 1024 * 1024)
        with Image.open(BytesIO(content)) as decoded:
            self.assertEqual(decoded.format, "PNG")
            decoded.verify()

        upload = SimpleUploadedFile("large.png", content, content_type="image/png")
        response = self.client.patch(
            "/api/v1/workspaces/listed/", {"logo": upload}, format="multipart"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("2 MB", str(response.data["logo"]))

    def test_non_image_named_png_is_rejected(self):
        teacher = self.listed.users.get(role=User.Role.TEACHER)
        self.client.force_authenticate(teacher)
        fake_png = SimpleUploadedFile(
            "logo.png", b"not an image", content_type="image/png"
        )
        response = self.client.patch(
            "/api/v1/workspaces/listed/", {"logo": fake_png}, format="multipart"
        )
        self.assertEqual(response.status_code, 400)
