import re

from flask import (
    Blueprint,
    abort,
    current_app,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from sqlalchemy import extract
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db, limiter
from app.forms.booking import InquiryForm
from app.models import (
    BookingInquiry,
    Event,
    EventCategory,
    EventMedia,
    GalleryCategory,
    MediaAsset,
    PricingPackage,
    ServiceType,
    Testimonial,
)
from app.services.content import public_context
from app.services.seo import event_data, homepage_data

bp = Blueprint("public", __name__)


@bp.context_processor
def content_context():
    return public_context()


def visible_events():
    return (
        db.select(Event)
        .where(Event.status == "published")
        .options(joinedload(Event.cover), joinedload(Event.category))
    )


def visible_packages():
    return (
        db.select(PricingPackage)
        .where(PricingPackage.published.is_(True))
        .options(selectinload(PricingPackage.features))
        .order_by(PricingPackage.featured.desc(), PricingPackage.sort_order, PricingPackage.id)
    )


@bp.get("/")
def home():
    recap_statement = (
        db.select(MediaAsset)
        .where(MediaAsset.is_public.is_(True), MediaAsset.is_featured.is_(True))
        .order_by(MediaAsset.sort_order, MediaAsset.id.desc())
        .limit(6)
    )
    recap_photos = db.session.scalars(recap_statement).all()
    featured_statement = (
        visible_events().where(Event.featured.is_(True)).order_by(Event.date.desc()).limit(3)
    )
    events = db.session.scalars(featured_statement).all()
    packages = db.session.scalars(visible_packages().limit(3)).all()
    testimonial_statement = (
        db.select(Testimonial)
        .where(Testimonial.published.is_(True))
        .options(joinedload(Testimonial.portrait))
        .order_by(Testimonial.sort_order, Testimonial.id)
        .limit(3)
    )
    testimonials = db.session.scalars(testimonial_statement).all()
    g.has_testimonials = bool(testimonials)
    return render_template(
        "public/home.html",
        title="Beranda",
        page="home",
        recap_photos=recap_photos,
        events=events,
        packages=packages,
        testimonials=testimonials,
        structured_data=homepage_data(),
    )


@bp.get("/tentang")
def about():
    return render_template(
        "public/about.html",
        title="Tentang",
        page="about",
        description="Kenali DJ NAZYER, pendekatan musik, dan arah performance.",
    )


@bp.get("/recap")
def recap():
    category = request.args.get("kategori", "")
    year = request.args.get("tahun", type=int)
    stmt = visible_events()
    if category:
        stmt = stmt.join(EventCategory).where(EventCategory.slug == category)
    if year:
        stmt = stmt.where(extract("year", Event.date) == year)
    pagination = db.paginate(
        stmt.order_by(Event.date.desc(), Event.id.desc()),
        per_page=9,
        max_per_page=9,
        error_out=False,
    )
    categories = db.session.scalars(
        db.select(EventCategory).order_by(EventCategory.sort_order)
    ).all()
    years = db.session.scalars(
        db.select(extract("year", Event.date))
        .where(Event.status == "published")
        .distinct()
        .order_by(extract("year", Event.date).desc())
    ).all()
    return render_template(
        "public/recap.html",
        title="Recap",
        page="recap",
        pagination=pagination,
        categories=categories,
        years=years,
        selected_category=category,
        selected_year=year,
        description="Arsip momen dan penampilan DJ NAZYER.",
    )


@bp.get("/recap/<slug>")
def event_detail(slug):
    event = db.session.scalar(
        visible_events()
        .where(Event.slug == slug)
        .options(selectinload(Event.media).joinedload(EventMedia.asset))
    )
    if not event:
        abort(404)
    related = db.session.scalars(
        visible_events()
        .where(Event.id != event.id, Event.category_id == event.category_id)
        .order_by(Event.date.desc())
        .limit(3)
    ).all()
    return render_template(
        "public/event.html",
        title=event.title,
        page="recap",
        event=event,
        related=related,
        description=event.description[:155] or f"Recap {event.title} — DJ NAZYER",
        og_image=event.cover,
        structured_data=event_data(event),
    )


@bp.get("/galeri")
def gallery():
    category = request.args.get("kategori", "")
    stmt = db.select(MediaAsset).where(MediaAsset.is_public.is_(True))
    if category:
        stmt = stmt.join(GalleryCategory).where(GalleryCategory.slug == category)
    pagination = db.paginate(
        stmt.order_by(MediaAsset.sort_order, MediaAsset.id.desc()),
        per_page=18,
        max_per_page=18,
        error_out=False,
    )
    categories = db.session.scalars(
        db.select(GalleryCategory).order_by(GalleryCategory.sort_order)
    ).all()
    return render_template(
        "public/gallery.html",
        title="Galeri",
        page="gallery",
        pagination=pagination,
        categories=categories,
        selected_category=category,
        description="Foto live performance, recap, personal, dan behind the scenes DJ NAZYER.",
    )


@bp.get("/pricelist")
def pricing():
    packages = db.session.scalars(visible_packages()).all()
    return render_template(
        "public/pricing.html",
        title="Pricelist",
        page="pricing",
        packages=packages,
        description="Diskusikan paket penampilan DJ NAZYER untuk acara Anda.",
    )


@bp.route("/kontak", methods=["GET", "POST"])
@limiter.limit("3 per minute", methods=["POST"])
@limiter.limit("15 per hour", methods=["POST"])
def contact():
    form = InquiryForm()
    form.service_type_id.choices = [(0, "Pilih jenis event")] + [
        (s.id, s.name)
        for s in db.session.scalars(
            db.select(ServiceType)
            .where(ServiceType.active.is_(True))
            .order_by(ServiceType.sort_order)
        )
    ]
    form.package_id.choices = [(0, "Konsultasi terlebih dahulu")] + [
        (p.id, p.name) for p in db.session.scalars(visible_packages())
    ]
    if request.method == "GET":
        selected = request.args.get("paket", type=int)
        if selected in [id for id, _ in form.package_id.choices]:
            form.package_id.data = selected
    if form.validate_on_submit():
        if form.website.data:
            abort(400)
        inquiry = BookingInquiry(
            name=form.name.data.strip(),
            contact=form.contact.data.strip(),
            service_type_id=form.service_type_id.data or None,
            event_date=form.event_date.data,
            location=form.location.data.strip(),
            package_id=form.package_id.data or None,
            message=form.message.data.strip(),
        )
        db.session.add(inquiry)
        db.session.commit()
        session["inquiry_sent"] = True
        return redirect(url_for("public.contact_success"), code=303)
    return render_template(
        "public/contact.html",
        title="Kontak & Booking",
        page="contact",
        form=form,
        description="Kirim inquiry atau hubungi DJ NAZYER untuk mendiskusikan acara Anda.",
    ), 422 if request.method == "POST" else 200


@bp.get("/kontak/terkirim")
def contact_success():
    if not session.pop("inquiry_sent", False):
        return redirect(url_for("public.contact"))
    return render_template("public/success.html", title="Inquiry terkirim", page="contact")


@bp.get("/uploads/<path:filename>")
def uploaded_file(filename):
    if current_app.config["APP_ENV"] == "production":
        abort(404)
    if not re.fullmatch(r"[a-f0-9]{40}(?:-small|-thumb)?\.webp", filename):
        abort(404)
    return send_from_directory(current_app.config["MEDIA_ROOT"], filename, max_age=31536000)


@bp.get("/sitemap.xml")
def sitemap():
    pages = [
        url_for("public." + name)
        for name in ["home", "about", "recap", "gallery", "pricing", "contact"]
    ]
    events = db.session.execute(
        db.select(Event.slug, Event.updated_at)
        .where(Event.status == "published")
        .order_by(Event.id)
    ).all()
    return current_app.response_class(
        render_template("public/sitemap.xml", pages=pages, events=events),
        mimetype="application/xml",
    )


@bp.get("/robots.txt")
def robots():
    text = (
        "User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /kontak/terkirim\nSitemap: "
        + current_app.config["PUBLIC_BASE_URL"].rstrip("/")
        + "/sitemap.xml\n"
    )
    return current_app.response_class(text, mimetype="text/plain")
