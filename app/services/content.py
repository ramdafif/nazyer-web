import re
from urllib.parse import urlencode, urlsplit

from flask import g
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models import ArtistProfile, ServiceType, SiteSetting, Testimonial

SOCIALS = {"instagram": "Instagram", "spotify": "Spotify", "youtube": "YouTube", "tiktok": "TikTok"}


def settings():
    if "site_settings" not in g:
        rows = db.session.scalars(
            db.select(SiteSetting).options(joinedload(SiteSetting.media))
        ).all()
        g.site_settings = {row.key: row.value for row in rows}
        g.site_media = {row.key: row.media for row in rows if row.media}
    return g.site_settings


def profile():
    if "artist_profile" not in g:
        statement = db.select(ArtistProfile).options(
            joinedload(ArtistProfile.hero_media),
            joinedload(ArtistProfile.portrait_media),
            selectinload(ArtistProfile.highlights),
        )
        g.artist_profile = db.session.scalar(statement) or ArtistProfile()
        for name, default in {
            "display_name": "DJ NAZYER",
            "hero_line_one": "Feel The Beat.",
            "hero_line_two": "Own The Night.",
            "decorative_tagline": "Music. People. Better days.",
        }.items():
            if getattr(g.artist_profile, name) is None:
                setattr(g.artist_profile, name, default)
    return g.artist_profile


def safe_url(value, hosts=None):
    if not value or any(c in value for c in "\r\n\t"):
        return ""
    try:
        parts = urlsplit(value)
        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.port not in (None, 443)
        ):
            return ""
        if hosts and not any(
            parts.hostname == host or parts.hostname.endswith("." + host) for host in hosts
        ):
            return ""
        return value
    except ValueError:
        return ""


def whatsapp_url(package=None):
    number = re.sub(r"[^0-9]", "", settings().get("whatsapp", ""))
    if number.startswith("0"):
        number = "62" + number[1:]
    if not (8 <= len(number) <= 15):
        return ""
    text = "Halo, saya ingin bertanya tentang booking DJ NAZYER."
    if package:
        text += f" Saya tertarik dengan paket {package.name}."
    return "https://wa.me/" + number + "?" + urlencode({"text": text})


def public_context():
    site = settings()
    if "has_testimonials" not in g:
        g.has_testimonials = db.session.scalar(
            db.select(db.select(Testimonial.id).where(Testimonial.published.is_(True)).exists())
        )
    return {
        "artist": profile(),
        "site": site,
        "site_media": g.site_media,
        "whatsapp_url": whatsapp_url,
        "has_testimonials": g.has_testimonials,
        "socials": {
            name: (label, safe_url(site.get(name, "")))
            for name, label in SOCIALS.items()
            if safe_url(site.get(name, ""))
        },
        "service_types": db.session.scalars(
            db.select(ServiceType)
            .where(ServiceType.active.is_(True))
            .order_by(ServiceType.sort_order, ServiceType.id)
        ).all(),
    }
