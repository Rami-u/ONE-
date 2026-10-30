"""One-off sanity check of the FRONTEND_DIST SPA serving (run from backend/)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["FRONTEND_DIST"] = "frontend/dist"

import django  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from config.settings import FRONTEND_DIST  # noqa: E402
from django.test import Client  # noqa: E402

print("FRONTEND_DIST resolves to:", FRONTEND_DIST)

client = Client()
r_index = client.get("/")
r_route = client.get("/teachers")
r_api = client.get("/api/v1/public/teachers/")
r_api_unknown = client.get("/api/unknown/path")
r_admin = client.get("/platform-admin/login/")
r_asset = client.get("/assets/index-EhAVz1kX.js")
r_index_post = client.post("/", {})

print("SPA /:            ", r_index.status_code, r_index.headers.get("Content-Type"), repr(r_index.headers.get("Cache-Control")))
print("SPA /teachers:    ", r_route.status_code)
print("API public:       ", r_api.status_code)
print("API unknown:      ", r_api_unknown.status_code)
print("admin login page: ", r_admin.status_code)
print("hashed asset:     ", r_asset.status_code, repr(r_asset.headers.get("Cache-Control")))
print("POST /:           ", r_index_post.status_code)

body = r_index.content if not hasattr(r_index, "streaming_content") else b"".join(r_index.streaming_content)
print("index.html real:  ", b'<div id="root">' in body)
