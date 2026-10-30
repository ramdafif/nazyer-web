import io
from datetime import date

from flask import current_app
from PIL import Image, ImageDraw
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import (
    ArtistProfile,
    Event,
    EventCategory,
    EventMedia,
    GalleryCategory,
    PricingFeature,
    PricingPackage,
    ServiceType,
)


def seed():
    if current_app.config["APP_ENV"] == "production":
        raise RuntimeError("Demo data is forbidden in production")
    if not db.session.scalar(db.select(ArtistProfile)):
        db.session.add(
            ArtistProfile(is_demo=True, bio_summary="DEMO — Isi biografi asli melalui CMS.")
        )
    for i, (name, slug) in enumerate(
        [
            ("Live Performance", "live-performance"),
            ("Event Recap", "event-recap"),
            ("Personal Photos", "personal-photos"),
            ("Behind the Scenes", "behind-the-scenes"),
        ]
    ):
        if not db.session.scalar(db.select(GalleryCategory).where(GalleryCategory.slug == slug)):
            db.session.add(GalleryCategory(name=name, slug=slug, sort_order=i, is_demo=True))
    for i, (name, slug, icon) in enumerate(
        [
            ("Clubs & Nightlife", "clubs", "music"),
            ("Private Events", "private-events", "users"),
            ("Weddings", "weddings", "heart"),
            ("Corporate Events", "corporate-events", "building-2"),
        ]
    ):
        if not db.session.scalar(db.select(ServiceType).where(ServiceType.slug == slug)):
            db.session.add(ServiceType(name=name, slug=slug, icon=icon, sort_order=i, is_demo=True))
    if not db.session.scalar(db.select(Event).where(Event.slug == "demo-visual-session")):
        from app.services.media import paths, upload_image

        created = []
        try:
            category = EventCategory(
                name="DEMO — Sesi Visual", slug="demo-sesi-visual", is_demo=True
            )
            db.session.add(category)
            db.session.flush()
            event = Event(
                title="DEMO — Visual Session",
                slug="demo-visual-session",
                date=date(2026, 1, 1),
                description="DEMO — Contoh alur recap, bukan riwayat performance DJ NAZYER.",
                status="published",
                featured=True,
                category_id=category.id,
                is_demo=True,
            )
            db.session.add(event)
            db.session.flush()
            for i in range(6):
                im = Image.new("RGB", (800, 1000), (15, 8, 24))
                draw = ImageDraw.Draw(im)
                for j in range(14):
                    draw.ellipse(
                        (50 - j * 25 + i * 14, 200 - j * 22, 750 + j * 20, 900 + j * 12),
                        outline=(45 + j * 7, 23 + j * 3, 75 + j * 9),
                        width=2,
                    )
                draw.text((40, 40), "DEMO / ABSTRACT PLACEHOLDER", fill=(215, 190, 245))
                buffer = io.BytesIO()
                im.save(buffer, "PNG")
                buffer.seek(0)
                asset = upload_image(
                    FileStorage(stream=buffer, filename="demo-abstract.png"),
                    {
                        "alt_text": f"DEMO — komposisi abstrak {i + 1}",
                        "caption": "DEMO — bukan foto performance asli.",
                        "is_public": True,
                        "is_featured": True,
                        "sort_order": i,
                        "is_demo": True,
                    },
                )
                created.append(asset)
                db.session.add(
                    EventMedia(event_id=event.id, media_id=asset.id, sort_order=i, is_demo=True)
                )
            event.cover_id = created[0].id
        except Exception:
            db.session.rollback()
            for asset in created:
                for path in paths(asset):
                    path.unlink(missing_ok=True)
            raise
    for i, name in enumerate(
        ["Private Party", "Wedding / Special Event", "Club / Corporate Event"]
    ):
        slug = f"demo-paket-{i + 1}"
        if not db.session.scalar(db.select(PricingPackage).where(PricingPackage.slug == slug)):
            package = PricingPackage(
                name="DEMO — " + name,
                slug=slug,
                published=True,
                featured=i == 1,
                sort_order=i,
                is_demo=True,
                description="DEMO — Detail dan harga asli ditentukan melalui CMS.",
            )
            package.features = [
                PricingFeature(label="DEMO — Fitur paket contoh", sort_order=0, is_demo=True)
            ]
            db.session.add(package)
    db.session.commit()
