from datetime import date

import pytest

from app.extensions import db
from app.models import Event


@pytest.mark.parametrize("path", ["/", "/tentang", "/recap", "/galeri", "/pricelist", "/kontak"])
def test_public_routes(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert '<main id="main">' in response.text
    assert 'lang="id"' in response.text


def test_empty_home_is_honest(client):
    text = client.get("/").text
    assert "100+" not in text and "Rp 2.500.000" not in text
    assert '<section id="testimoni"' not in text
    assert "Featured Performances." not in text
    assert "Hubungi untuk Penawaran" in text
    assert "/design/reference.png" not in text


def test_event_publication(app, client):
    with app.app_context():
        db.session.add_all(
            [
                Event(title="Draft Rahasia", slug="draft-rahasia", date=date(2026, 1, 1)),
                Event(
                    title="Event Terbit",
                    slug="event-terbit",
                    date=date(2026, 1, 1),
                    status="published",
                ),
            ]
        )
        db.session.commit()
    assert client.get("/recap/draft-rahasia").status_code == 404
    assert client.get("/recap/not-found").status_code == 404
    assert client.get("/recap/event-terbit").status_code == 200
    assert "Draft Rahasia" not in client.get("/recap").text
    assert "Event Terbit" in client.get("/recap").text
