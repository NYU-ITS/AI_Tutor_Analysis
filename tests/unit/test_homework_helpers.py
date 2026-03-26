import pytest

from app.routers import homework as homework_router
from app.routers.homework import pdf_to_images


pytestmark = pytest.mark.unit


class _FakePix:
    def tobytes(self, fmt):
        assert fmt == "png"
        return b"png-bytes"


class _FakePage:
    def get_pixmap(self, dpi=200):
        assert dpi == 200
        return _FakePix()


class _FakeDoc:
    def __init__(self):
        self.closed = False
        self.pages = [_FakePage(), _FakePage()]

    def __iter__(self):
        return iter(self.pages)

    def close(self):
        self.closed = True


def test_pdf_to_images_converts_all_pages(monkeypatch):
    fake_doc = _FakeDoc()
    monkeypatch.setattr(homework_router.fitz, "open", lambda stream=None, filetype=None: fake_doc)

    images = pdf_to_images(b"%PDF-fake")

    assert len(images) == 2
    assert images[0]["type"] == "image_url"
    assert images[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert fake_doc.closed is True
