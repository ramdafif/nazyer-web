"""Minimal Schema.org facts from configured identity and published real events."""

from flask import current_app, url_for

from app.services.content import SOCIALS, profile, safe_url, settings


def absolute_url(path):
    return current_app.config["PUBLIC_BASE_URL"].rstrip("/") + path


def media_url(asset):
    if asset and not asset.is_demo:
        return absolute_url(url_for("public.uploaded_file", filename=asset.filename))
    return None


def homepage_data():
    artist = profile()
    name = (artist.display_name or "").strip()
    if artist.is_demo or not name:
        return None
    site = settings()
    home = absolute_url(url_for("public.home"))
    person = {
        "@type": "Person",
        "@id": home + "#artist",
        "name": name,
        "url": home,
    }
    socials = list(dict.fromkeys(safe_url(site.get(key, "")) for key in SOCIALS))
    socials = [value for value in socials if value]
    if socials:
        person["sameAs"] = socials
    image = media_url(artist.portrait_media) or media_url(artist.hero_media)
    if image:
        person["image"] = image
    website = {
        "@type": "WebSite",
        "@id": home + "#website",
        "name": (site.get("site_title") or "").strip() or name,
        "url": home,
        "about": {"@id": person["@id"]},
    }
    return {"@context": "https://schema.org", "@graph": [website, person]}


def event_data(event):
    name = (event.title or "").strip()
    venue = (event.venue or "").strip()
    location = (event.location or "").strip()
    if (
        event.is_demo
        or event.status != "published"
        or not (name and event.date and (venue or location))
    ):
        return None
    place = {"@type": "Place", "name": venue or location}
    if location:
        # Location is free text: do not invent city, postal code or street fields.
        place["address"] = location
    data = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": name,
        "url": absolute_url(url_for("public.event_detail", slug=event.slug)),
        # The CMS stores a date only. Never infer midnight, a timezone or end time.
        "startDate": event.date.isoformat(),
        "location": place,
    }
    if event.description:
        data["description"] = event.description
    image = media_url(event.cover)
    if image:
        data["image"] = image
    return data
