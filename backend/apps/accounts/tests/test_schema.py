import json

from django.test import override_settings
from rest_framework.test import APIClient, APITestCase


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

    @override_settings(ENABLE_API_DOCS=False)
    def test_schema_endpoint_is_hidden_when_disabled(self):
        response = APIClient().get("/api/schema/")
        self.assertEqual(response.status_code, 404)

    @override_settings(ENABLE_API_DOCS=True)
    def test_swagger_docs_endpoint_returns_200_when_enabled(self):
        response = APIClient().get("/api/docs/")
        self.assertEqual(response.status_code, 200)
