from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateReceiptStorage(FileSystemStorage):
    """Storage for private receipts. Never serves files directly by public URL."""

    def __init__(self):
        super().__init__(
            base_url=None,
        )

    def url(self, name):
        raise NotImplementedError(
            "Receipts are private and can only be accessed through authorized endpoints."
        )


private_receipt_storage = PrivateReceiptStorage()
