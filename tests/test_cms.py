import io

import pytest
from PIL import Image

from app.extensions import db
from app.models import Event, MediaAsset, PricingPackage


def image_bytes(fmt="JPEG", size=(160, 120)):
    buffer = io.BytesIO()
    Image.new("RGB", size, "purple").save(buffer, fmt)
    buffer.seek(0)
    return buffer


@pytest.mark.parametrize(
    "path",
    [
        "/admin/",
        "/admin/events",
        "/admin/events/new",
        "/admin/media",
        "/admin/media/upload",
        "/admin/pricing",
        "/admin/pricing/new",
        "/admin/profile",
        "/admin/services",
        "/admin/testimonials",
        "/admin/inquiries",
        "/admin/settings",
        "/admin/highlights",
        "/admin/event-categories",
        "/admin/gallery-categories",
    ],
)
def test_admin_screens(admin, path):
    assert admin.get(path).status_code == 200


def test_event_crud(app, admin):
    data = {
        "title": "Malam Musik",
        "slug": "malam-musik",
        "date": "2026-10-01",
        "venue": "Venue asli",
        "location": "Jakarta",
        "category_id": 0,
        "cover_id": 0,
        "status": "draft",
        "description": "Catatan event",
        "media_ids": [],
    }
    assert admin.post("/admin/events/new", data=data).status_code == 302
    with app.app_context():
        event_id = db.session.scalar(db.select(Event.id))
    assert admin.get(f"/admin/events/{event_id}/edit").status_code == 200
    data["status"] = "published"
    assert admin.post(f"/admin/events/{event_id}/edit", data=data).status_code == 302
    assert admin.get("/recap/malam-musik").status_code == 200
    assert admin.post(f"/admin/events/{event_id}/delete", data={}).status_code == 422
    assert admin.post(f"/admin/events/{event_id}/delete", data={"confirm": "y"}).status_code == 302
    assert admin.get("/recap/malam-musik").status_code == 404


def test_pricing_crud(app, admin):
    data = {
        "name": "Paket Asli",
        "slug": "paket-asli",
        "price": "1234567",
        "duration": "2 jam",
        "features_text": "Fitur satu\nFitur dua",
        "sort_order": 0,
        "published": "y",
    }
    response = admin.post("/admin/pricing/new", data=data)
    assert response.status_code == 302
    with app.app_context():
        package = db.session.scalar(db.select(PricingPackage))
        pid = package.id
        assert len(package.features) == 2
    assert "Rp 1.234.567" in admin.get("/pricelist").text
    assert admin.get(f"/admin/pricing/{pid}/preview").status_code == 200
    assert admin.get("/admin/pricing").status_code == 200
    data["price"] = ""
    data["features_text"] = "Fitur pengganti"
    assert admin.post(f"/admin/pricing/{pid}/edit", data=data).status_code == 302
    assert "Hubungi untuk Penawaran" in admin.get("/pricelist").text
    assert admin.post(f"/admin/pricing/{pid}/delete", data={"confirm": "y"}).status_code == 302


def test_media_upload_edit_delete(app, admin):
    response = admin.post(
        "/admin/media/upload",
        data={
            "image": (image_bytes(), "photo.jpg"),
            "alt_text": "Panggung",
            "category_id": 0,
            "event_id": 0,
            "sort_order": 0,
            "is_public": "y",
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 302
    with app.app_context():
        asset = db.session.scalar(db.select(MediaAsset))
        mid = asset.id
        from app.services.media import paths

        files = paths(asset)
        assert all(path.exists() for path in files)
        assert Image.open(files[0]).format == "WEBP"
    assert admin.get("/admin/media").status_code == 200
    assert admin.get(f"/admin/media/{mid}/edit").status_code == 200
    assert admin.post(f"/admin/media/{mid}/delete", data={"confirm": "y"}).status_code == 302
    assert all(not path.exists() for path in files)


def test_settings_reject_javascript(admin):
    response = admin.post(
        "/admin/settings",
        data={
            "site_title": "DJ NAZYER",
            "instagram": "javascript:alert(1)",
            "logo_id": 0,
            "favicon_id": 0,
            "share_image_id": 0,
        },
    )
    assert response.status_code == 422


def test_duplicate_slug_validation(admin):
    data = {"name": "Club", "slug": "club", "sort_order": 0, "icon": "music", "active": "y"}
    assert admin.post("/admin/services/new", data=data).status_code == 302
    response = admin.post("/admin/services/new", data=data)
    assert response.status_code == 422
    assert "Slug sudah digunakan" in response.text
