import json

from django.test import override_settings
from rest_framework.test import APIClient, APITestCase
from drf_spectacular.settings import spectacular_settings


class SchemaEndpointTests(APITestCase):
    @override_settings(ENABLE_API_DOCS=True)
    def test_schema_endpoint_returns_200_when_enabled(self):
        response = APIClient().get(
            "/api/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json"
        )
        self.assertEqual(response.status_code, 200)
        schema = json.loads(response.content)
        login = schema["paths"][
            "/api/v1/workspaces/{slug}/staff/auth/login/"
        ]["post"]
        request_schema = login["requestBody"]["content"]["application/json"]["schema"]
        if "$ref" in request_schema:
            schema_name = request_schema["$ref"].rsplit("/", 1)[-1]
            request_schema = schema["components"]["schemas"][schema_name]
        self.assertEqual(
            set(request_schema["properties"]), {"email", "password"}
        )

        profile = schema["paths"]["/api/v1/public/teachers/{slug}/"]["get"]
        profile_schema = profile["responses"]["200"]["content"]["application/json"]["schema"]
        profile_schema = schema["components"]["schemas"][
            profile_schema["$ref"].rsplit("/", 1)[-1]
        ]
        self.assertEqual(
            set(profile_schema["properties"]),
            {"slug", "name", "teacher_name", "logo", "headline", "bio", "about", "courses"},
        )

        settings_patch = schema["paths"]["/api/v1/workspaces/{slug}/"]["patch"]
        self.assertIn(
            "multipart/form-data", settings_patch["requestBody"]["content"]
        )
        settings_request = settings_patch["requestBody"]["content"]["multipart/form-data"]["schema"]
        settings_request = schema["components"]["schemas"][
            settings_request["$ref"].rsplit("/", 1)[-1]
        ]
        self.assertEqual(settings_request["properties"]["logo"]["format"], "binary")

    @override_settings(ENABLE_API_DOCS=False)
    def test_schema_endpoint_is_hidden_when_disabled(self):
        response = APIClient().get("/api/schema/")
        self.assertEqual(response.status_code, 404)

    @override_settings(ENABLE_API_DOCS=True)
    def test_swagger_docs_endpoint_returns_200_when_enabled(self):
        response = APIClient().get("/api/docs/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("requestInterceptor", spectacular_settings.SWAGGER_UI_SETTINGS)

    @override_settings(ENABLE_API_DOCS=True)
    def test_student_auth_and_review_endpoints_have_explicit_shapes(self):
        response = APIClient().get(
            "/api/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json"
        )
        self.assertEqual(response.status_code, 200)
        schema = json.loads(response.content)
        paths = schema["paths"]

        required_paths = {
            "/api/v1/workspaces/{slug}/auth/csrf/": "get",
            "/api/v1/workspaces/{slug}/auth/register/": "post",
            "/api/v1/workspaces/{slug}/auth/login/": "post",
            "/api/v1/workspaces/{slug}/auth/logout/": "post",
            "/api/v1/workspaces/{slug}/auth/me/": "get",
            "/api/v1/workspaces/{slug}/auth/password-reset/": "post",
            "/api/v1/workspaces/{slug}/auth/password-reset/confirm/": "post",
            "/api/v1/workspaces/{slug}/students/": "get",
            "/api/v1/workspaces/{slug}/students/{student_id}/approve/": "post",
            "/api/v1/workspaces/{slug}/students/{student_id}/reject/": "post",
        }
        for path, method in required_paths.items():
            self.assertIn(path, paths)
            self.assertIn(method, paths[path])

        register = paths["/api/v1/workspaces/{slug}/auth/register/"]["post"]
        register_request = register["requestBody"]["content"]["application/json"]["schema"]
        register_request = schema["components"]["schemas"][register_request["$ref"].rsplit("/", 1)[-1]]
        self.assertEqual(
            set(register_request["properties"]),
            {"email", "password", "full_name", "phone"},
        )

        me = paths["/api/v1/workspaces/{slug}/auth/me/"]["get"]
        me_response = me["responses"]["200"]["content"]["application/json"]["schema"]
        me_response = schema["components"]["schemas"][me_response["$ref"].rsplit("/", 1)[-1]]
        self.assertEqual(
            set(me_response["properties"]),
            {
                "id",
                "email",
                "full_name",
                "phone",
                "role",
                "approval_status",
                "workspace",
            },
        )

        approve = paths["/api/v1/workspaces/{slug}/students/{student_id}/approve/"]["post"]
        self.assertNotIn("requestBody", approve)
        reject = paths["/api/v1/workspaces/{slug}/students/{student_id}/reject/"]["post"]
        reject_request = reject["requestBody"]["content"]["application/json"]["schema"]
        reject_request = schema["components"]["schemas"][reject_request["$ref"].rsplit("/", 1)[-1]]
        self.assertEqual(set(reject_request["properties"]), {"rejection_reason"})
