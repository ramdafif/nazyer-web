import re
import unicodedata

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.forms.cms import (
    CategoryForm,
    EventForm,
    HighlightForm,
    MediaForm,
    PricingForm,
    ServiceForm,
    TestimonialForm,
)
from app.models import (
    ArtistProfile,
    Event,
    EventCategory,
    EventMedia,
    GalleryCategory,
    MediaAsset,
    PricingFeature,
    PricingPackage,
    ProfileHighlight,
    ServiceType,
    Testimonial,
)

ENTITIES = {
    "events": (Event, EventForm, "Event", "title"),
    "pricing": (PricingPackage, PricingForm, "Pricelist", "name"),
    "services": (ServiceType, ServiceForm, "Jenis Event", "name"),
    "testimonials": (Testimonial, TestimonialForm, "Testimoni", "name"),
    "event-categories": (EventCategory, CategoryForm, "Kategori Event", "name"),
    "gallery-categories": (GalleryCategory, CategoryForm, "Kategori Galeri", "name"),
    "highlights": (ProfileHighlight, HighlightForm, "Highlight Profil", "label"),
    "media": (MediaAsset, MediaForm, "Media Library", "original_name"),
}
MEDIA_FIELDS = {
    "cover_id",
    "portrait_id",
    "hero_media_id",
    "portrait_media_id",
    "logo_id",
    "favicon_id",
    "share_image_id",
}
NULLABLE_IDS = MEDIA_FIELDS | {"category_id"}


def slugify(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-") or "konten"


def choices(form):
    media = None
    for name in MEDIA_FIELDS | {"media_ids"}:
        if hasattr(form, name):
            if media is None:
                media = [
                    (m.id, f"{m.id} · {m.alt_text or m.original_name}")
                    for m in db.session.scalars(
                        db.select(MediaAsset).order_by(MediaAsset.id.desc())
                    )
                ]
            getattr(form, name).choices = (
                [(0, "Tidak ada")] if name != "media_ids" else []
            ) + media
    if hasattr(form, "category_id"):
        model = EventCategory if isinstance(form, EventForm) else GalleryCategory
        form.category_id.choices = [(0, "Tanpa kategori")] + [
            (x.id, x.name) for x in db.session.scalars(db.select(model).order_by(model.sort_order))
        ]
    if hasattr(form, "event_id"):
        form.event_id.choices = [(0, "Tidak ditambahkan ke event")] + [
            (x.id, x.title)
            for x in db.session.scalars(db.select(Event).order_by(Event.date.desc()))
        ]


def apply_form(obj, form):
    for field in form:
        key = field.name
        if key in {
            "csrf_token",
            "submit",
            "media_ids",
            "media_order",
            "features_text",
            "image",
            "event_id",
        } or not hasattr(type(obj), key):
            continue
        value = field.data
        if key in NULLABLE_IDS or key == "rating":
            value = value or None
        if isinstance(value, str):
            value = value.strip()
        setattr(obj, key, value)
    if hasattr(obj, "slug"):
        obj.slug = obj.slug or slugify(getattr(obj, "title", None) or obj.name)
    if isinstance(obj, ProfileHighlight) and not obj.profile_id:
        profile = db.session.scalar(db.select(ArtistProfile))
        if not profile:
            profile = ArtistProfile()
            db.session.add(profile)
            db.session.flush()
        obj.profile_id = profile.id
    if isinstance(obj, PricingPackage):
        obj.features[:] = [
            PricingFeature(label=line.strip(), sort_order=i)
            for i, line in enumerate((form.features_text.data or "").splitlines())
            if line.strip()
        ]
    if isinstance(obj, Event):
        selected = list(dict.fromkeys(form.media_ids.data or []))
        ordered = [
            int(x)
            for x in (form.media_order.data or "").split(",")
            if x.isdigit() and int(x) in selected
        ]
        selected = list(dict.fromkeys(ordered + selected))
        # Keep existing links to avoid unique constraint conflicts on a flush.
        links = {link.media_id: link for link in obj.media}
        obj.media[:] = [links.get(mid) or EventMedia(media_id=mid) for mid in selected]
        for i, link in enumerate(obj.media):
            link.sort_order = i


def persist(obj, form):
    try:
        apply_form(obj, form)
        db.session.add(obj)
        db.session.commit()
        return True
    except IntegrityError:
        db.session.rollback()
        field = getattr(form, "slug", None) or next(iter(form))
        field.errors.append("Slug sudah digunakan atau ada relasi data yang tidak valid.")
        return False
