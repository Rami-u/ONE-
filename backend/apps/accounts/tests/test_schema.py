from django.test import TestCase, override_settings
from rest_framework.test import APIClient


class SchemaEndpointTests(TestCase):
    @override_settings(ENABLE_API_DOCS=True)
    def test_schema_endpoint_returns_200_when_enabled(self):
        response = APIClient().get("/api/schema/")
        self.assertEqual(response.status_code, 200)

    @override_settings(ENABLE_API_DOCS=False)
    def test_schema_endpoint_is_hidden_when_disabled(self):
        response = APIClient().get("/api/schema/")
        self.assertEqual(response.status_code, 404)

    @override_settings(ENABLE_API_DOCS=True)
    def test_swagger_docs_endpoint_returns_200_when_enabled(self):
        response = APIClient().get("/api/docs/")
        self.assertEqual(response.status_code, 200)
