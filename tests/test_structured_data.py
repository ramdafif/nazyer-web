import json
from datetime import date
from html.parser import HTMLParser
from types import SimpleNamespace

import pytest

from app.extensions import db
from app.models import ArtistProfile, Event, SiteSetting
from app.models import Testimonial as Review
from app.services.media import upload_image
from app.services.seo import event_data
from tests.test_cms import image_bytes


class JSONBlocks(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.blocks = []
        self.recording = False
        self.buffer = ""
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("type") == "application/ld+json":
            self.recording = True
            self.buffer = ""

    def handle_data(self, data):
        if self.recording:
            self.buffer += data

    def handle_endtag(self, tag):
        if tag == "script" and self.recording:
            self.blocks.append(json.loads(self.buffer))
            self.recording = False


def graph(response):
    blocks = JSONBlocks(response.text).blocks
    assert len(blocks) == 1
    return {node["@type"]: node for node in blocks[0]["@graph"]}


def test_home_schema_uses_configured_origin_without_invented_fields(app, client):
    app.config["PUBLIC_BASE_URL"] = "https://artist.example"
    response = client.get("/", base_url="http://untrusted.example")
    nodes = graph(response)
    assert set(nodes) == {"WebSite", "Person"}
    assert nodes["Person"]["name"] == "DJ NAZYER"
    assert nodes["WebSite"]["url"] == nodes["Person"]["url"] == "https://artist.example/"
    assert "sameAs" not in nodes["Person"] and "image" not in nodes["Person"]
    assert nodes["WebSite"]["about"]["@id"] == nodes["Person"]["@id"]
    assert "aggregateRating" not in response.text and '"review"' not in response.text
    assert "unsafe-inline" not in response.headers["Content-Security-Policy"]


def test_profile_schema_serializes_configured_name_socials_and_real_image(app, client):
    from werkzeug.datastructures import FileStorage

    name = 'DJ "Nama" </script><script>alert(1)</script> & Musik'
    with app.app_context():
        photo = upload_image(FileStorage(stream=image_bytes(), filename="artist.jpg"), {})
        db.session.add(ArtistProfile(display_name=name, portrait_media=photo))
        db.session.add_all(
            [
                SiteSetting(key="instagram", value="https://instagram.com/real-artist"),
                SiteSetting(key="youtube", value="https://youtube.com/@real-artist"),
                SiteSetting(key="spotify", value="javascript:alert(1)"),
                SiteSetting(key="tiktok", value=""),
                SiteSetting(key="site_title", value="Judul Situs Asli"),
            ]
        )
        db.session.commit()
        filename = photo.filename
    response = client.get("/")
    nodes = graph(response)
    assert nodes["Person"]["name"] == name
    assert nodes["WebSite"]["name"] == "Judul Situs Asli"
    assert nodes["Person"]["sameAs"] == [
        "https://instagram.com/real-artist",
        "https://youtube.com/@real-artist",
    ]
    assert nodes["Person"]["image"] == f"http://localhost:5000/uploads/{filename}"
    assert "</script><script>alert(1)</script>" not in response.text
    assert "\\u003c/script\\u003e" in response.text


def test_demo_profile_and_media_are_not_real_person_facts(app, client):
    from werkzeug.datastructures import FileStorage

    with app.app_context():
        photo = upload_image(
            FileStorage(stream=image_bytes(), filename="demo.jpg"), {"is_demo": True}
        )
        artist = ArtistProfile(portrait_media=photo)
        db.session.add(artist)
        db.session.commit()
    assert "image" not in graph(client.get("/"))["Person"]
    with app.app_context():
        db.session.scalar(db.select(ArtistProfile)).is_demo = True
        db.session.commit()
    assert not JSONBlocks(client.get("/").text).blocks


@pytest.mark.parametrize(
    "venue,location", [("Ruang Musik", "Jakarta"), ("Ruang Musik", ""), ("", "Jakarta")]
)
def test_recap_schema_uses_date_only_and_available_place(app, client, venue, location):
    with app.app_context():
        db.session.add(
            Event(
                title="Malam Musik",
                slug="malam-musik",
                date=date(2026, 3, 12),
                venue=venue,
                location=location,
                status="published",
                description="Catatan acara asli.",
            )
        )
        db.session.commit()
    response = client.get("/recap/malam-musik")
    (data,) = JSONBlocks(response.text).blocks
    assert data["@type"] == "Event" and data["name"] == "Malam Musik"
    assert data["startDate"] == "2026-03-12"
    assert data["location"] == {
        "@type": "Place",
        "name": venue or location,
        **({"address": location} if location else {}),
    }
    assert data["url"] == "http://localhost:5000/recap/malam-musik"
    assert data["description"] == "Catatan acara asli."
    for field in ["endDate", "eventStatus", "offers", "image", "aggregateRating", "review"]:
        assert field not in data


def test_recap_schema_cover_is_real_and_optional(app, client):
    from werkzeug.datastructures import FileStorage

    with app.app_context():
        photo = upload_image(FileStorage(stream=image_bytes(), filename="event.jpg"), {})
        db.session.add(
            Event(
                title="Event",
                slug="event",
                date=date(2026, 1, 1),
                venue="Venue",
                status="published",
                cover=photo,
            )
        )
        db.session.commit()
        filename = photo.filename
    (data,) = JSONBlocks(client.get("/recap/event").text).blocks
    assert data["image"].endswith("/uploads/" + filename)


@pytest.mark.parametrize("missing", ["title", "date", "place", "draft", "demo"])
def test_event_schema_requires_real_published_complete_facts(app, missing):
    values = dict(
        title="Event",
        date=date(2026, 1, 1),
        venue="Venue",
        location="",
        status="published",
        is_demo=False,
    )
    if missing == "place":
        values["venue"] = " "
    elif missing == "draft":
        values["status"] = "draft"
    elif missing == "demo":
        values["is_demo"] = True
    else:
        values[missing] = None if missing == "date" else " "
    with app.test_request_context():
        assert event_data(SimpleNamespace(**values)) is None


@pytest.mark.parametrize("demo", [True, False])
def test_incomplete_or_demo_recap_has_no_event_markup(app, client, demo):
    with app.app_context():
        db.session.add(
            Event(
                title="Event",
                slug="event",
                date=date(2026, 1, 1),
                venue="Venue" if demo else "",
                status="published",
                is_demo=demo,
            )
        )
        db.session.commit()
    assert not JSONBlocks(client.get("/recap/event").text).blocks
    assert not JSONBlocks(client.get("/recap/missing").text).blocks


@pytest.mark.parametrize(
    "path", ["/tentang", "/recap", "/galeri", "/pricelist", "/kontak", "/admin/login"]
)
def test_unrelated_pages_do_not_receive_home_or_event_schema(client, path):
    assert not JSONBlocks(client.get(path).text).blocks


def test_testimonial_navigation_tracks_publication_on_every_public_page(app, client):
    paths = ["/", "/tentang", "/recap", "/galeri", "/pricelist", "/kontak"]
    with app.app_context():
        db.session.add(Review(name="Klien Uji", quote="Kutipan uji.", published=False))
        db.session.commit()
    for published in [False, True, False]:
        with app.app_context():
            db.session.scalar(db.select(Review)).published = published
            db.session.commit()
        for path in paths:
            html = client.get(path).text
            assert html.count('href="/#testimoni"') == (2 if published else 0)
            if path == "/":
                assert ('<section id="testimoni"' in html) == published
                for block in JSONBlocks(html).blocks:
                    serialized = json.dumps(block)
                    assert "aggregateRating" not in serialized and '"review"' not in serialized


def test_blank_profile_name_does_not_publish_an_empty_identity(app, client):
    with app.app_context():
        db.session.add(ArtistProfile(display_name="  "))
        db.session.commit()
    assert not JSONBlocks(client.get("/").text).blocks
