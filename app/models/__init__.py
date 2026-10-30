from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class DemoMixin:
    is_demo = db.Column(db.Boolean, default=False, nullable=False)


class AdminUser(UserMixin, TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    session_version = db.Column(db.Integer, default=1, nullable=False)

    @property
    def is_active(self):
        return self.active

    def get_id(self):
        return f"{self.id}:{self.session_version}"

    def set_password(self, password):
        if len(password) < 12 or len(password) > 128:
            raise ValueError("Password harus 12–128 karakter.")
        self.password_hash = generate_password_hash(password, method="scrypt:16384:8:1")

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class GalleryCategory(TimestampMixin, DemoMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(120), nullable=False, unique=True)
    sort_order = db.Column(db.Integer, default=0, nullable=False)


class MediaAsset(TimestampMixin, DemoMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), nullable=False, unique=True)
    original_name = db.Column(db.String(200), nullable=False)
    alt_text = db.Column(db.String(250), default="", nullable=False)
    caption = db.Column(db.String(500), default="", nullable=False)
    width = db.Column(db.Integer, nullable=False)
    height = db.Column(db.Integer, nullable=False)
    byte_size = db.Column(db.Integer, nullable=False)
    category_id = db.Column(
        db.Integer, db.ForeignKey("gallery_category.id", ondelete="RESTRICT"), index=True
    )
    category = db.relationship("GalleryCategory")
    is_public = db.Column(db.Boolean, default=False, nullable=False, index=True)
    is_featured = db.Column(db.Boolean, default=False, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)

    @property
    def thumbnail(self):
        return self.filename.replace(".webp", "-thumb.webp")

    @property
    def small(self):
        return self.filename.replace(".webp", "-small.webp")


class ArtistProfile(TimestampMixin, DemoMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    singleton = db.Column(db.Integer, default=1, nullable=False, unique=True)
    __table_args__ = (
        db.CheckConstraint("singleton = 1", name="single_profile"),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )
    display_name = db.Column(db.String(100), default="DJ NAZYER", nullable=False)
    hero_line_one = db.Column(db.String(100), default="Feel The Beat.", nullable=False)
    hero_line_two = db.Column(db.String(100), default="Own The Night.", nullable=False)
    hero_description = db.Column(db.String(500), default="", nullable=False)
    decorative_tagline = db.Column(
        db.String(120), default="Music. People. Better days.", nullable=False
    )
    bio_summary = db.Column(db.Text, default="", nullable=False)
    biography = db.Column(db.Text, default="", nullable=False)
    genres = db.Column(db.String(250), default="", nullable=False)
    philosophy = db.Column(db.Text, default="", nullable=False)
    career_highlights = db.Column(db.Text, default="", nullable=False)
    hero_media_id = db.Column(db.Integer, db.ForeignKey("media_asset.id", ondelete="RESTRICT"))
    portrait_media_id = db.Column(db.Integer, db.ForeignKey("media_asset.id", ondelete="RESTRICT"))
    hero_media = db.relationship("MediaAsset", foreign_keys=[hero_media_id])
    portrait_media = db.relationship("MediaAsset", foreign_keys=[portrait_media_id])
    highlights = db.relationship(
        "ProfileHighlight",
        cascade="all, delete-orphan",
        back_populates="profile",
        order_by="ProfileHighlight.sort_order",
    )


class ProfileHighlight(TimestampMixin, DemoMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(
        db.Integer,
        db.ForeignKey("artist_profile.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label = db.Column(db.String(100), nullable=False)
    value = db.Column(db.String(50), default="", nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    profile = db.relationship("ArtistProfile", back_populates="highlights")


class ServiceType(TimestampMixin, DemoMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(120), nullable=False, unique=True)
    icon = db.Column(db.String(30), default="music", nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)


class EventCategory(TimestampMixin, DemoMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(120), nullable=False, unique=True)
    sort_order = db.Column(db.Integer, default=0, nullable=False)


class Event(TimestampMixin, DemoMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    slug = db.Column(db.String(200), nullable=False, unique=True)
    date = db.Column(db.Date, nullable=False, index=True)
    venue = db.Column(db.String(180), default="", nullable=False)
    location = db.Column(db.String(180), default="", nullable=False)
    description = db.Column(db.Text, default="", nullable=False)
    status = db.Column(db.String(20), default="draft", nullable=False, index=True)
    __table_args__ = (
        db.CheckConstraint("status IN ('draft','published')", name="valid_status"),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )
    featured = db.Column(db.Boolean, default=False, nullable=False)
    video_url = db.Column(db.String(500), default="", nullable=False)
    category_id = db.Column(
        db.Integer, db.ForeignKey("event_category.id", ondelete="RESTRICT"), index=True
    )
    cover_id = db.Column(db.Integer, db.ForeignKey("media_asset.id", ondelete="RESTRICT"))
    category = db.relationship("EventCategory")
    cover = db.relationship("MediaAsset")
    media = db.relationship(
        "EventMedia",
        cascade="all, delete-orphan",
        back_populates="event",
        order_by="EventMedia.sort_order",
    )


class EventMedia(TimestampMixin, DemoMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(
        db.Integer, db.ForeignKey("event.id", ondelete="CASCADE"), nullable=False, index=True
    )
    media_id = db.Column(
        db.Integer, db.ForeignKey("media_asset.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    __table_args__ = (
        db.UniqueConstraint("event_id", "media_id"),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )
    event = db.relationship("Event", back_populates="media")
    asset = db.relationship("MediaAsset")


class PricingPackage(TimestampMixin, DemoMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(150), nullable=False, unique=True)
    price = db.Column(db.Numeric(14, 0))
    duration = db.Column(db.String(100), default="", nullable=False)
    description = db.Column(db.Text, default="", nullable=False)
    notes = db.Column(db.Text, default="", nullable=False)
    published = db.Column(db.Boolean, default=False, nullable=False, index=True)
    featured = db.Column(db.Boolean, default=False, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    __table_args__ = (
        db.CheckConstraint("price IS NULL OR price >= 0", name="nonnegative_price"),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )
    features = db.relationship(
        "PricingFeature", cascade="all, delete-orphan", order_by="PricingFeature.sort_order"
    )


class PricingFeature(TimestampMixin, DemoMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    package_id = db.Column(
        db.Integer,
        db.ForeignKey("pricing_package.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label = db.Column(db.String(250), nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)


class Testimonial(TimestampMixin, DemoMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    context = db.Column(db.String(180), default="", nullable=False)
    quote = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer)
    __table_args__ = (
        db.CheckConstraint("rating IS NULL OR (rating >= 1 AND rating <= 5)", name="rating_range"),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )
    published = db.Column(db.Boolean, default=False, nullable=False, index=True)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    portrait_id = db.Column(db.Integer, db.ForeignKey("media_asset.id", ondelete="RESTRICT"))
    portrait = db.relationship("MediaAsset")


class BookingInquiry(TimestampMixin, DemoMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    contact = db.Column(db.String(80), nullable=False)
    event_date = db.Column(db.Date)
    location = db.Column(db.String(200), nullable=False)
    service_type_id = db.Column(
        db.Integer, db.ForeignKey("service_type.id", ondelete="SET NULL"), index=True
    )
    package_id = db.Column(
        db.Integer, db.ForeignKey("pricing_package.id", ondelete="SET NULL"), index=True
    )
    service_type = db.relationship("ServiceType")
    package = db.relationship("PricingPackage")
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default="baru", nullable=False, index=True)
    internal_notes = db.Column(db.Text, default="", nullable=False)
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('baru','dihubungi','negosiasi','terkonfirmasi','ditutup')",
            name="valid_status",
        ),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )


class SiteSetting(TimestampMixin, DemoMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), nullable=False, unique=True)
    value = db.Column(db.Text, default="", nullable=False)
    media_id = db.Column(db.Integer, db.ForeignKey("media_asset.id", ondelete="RESTRICT"))
    media = db.relationship("MediaAsset")
