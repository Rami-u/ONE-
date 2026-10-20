from django.conf import settings
from django.core.files.storage import FileSystemStorage
from urllib.parse import urlparse


class PublicLogoStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(
            location=settings.BASE_DIR / "public_media",
            base_url=settings.MEDIA_URL,
        )

    def url(self, name):
        if urlparse(str(name)).scheme in {"http", "https"}:
            return str(name)
        return super().url(name)


public_logo_storage = PublicLogoStorage()
