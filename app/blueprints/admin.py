from types import SimpleNamespace

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.forms.cms import (
    INQUIRY_STATUSES,
    DeleteForm,
    InquiryAdminForm,
    ProfileForm,
    SettingsForm,
    UploadForm,
)
from app.models import (
    ArtistProfile,
    BookingInquiry,
    Event,
    EventMedia,
    MediaAsset,
    PricingPackage,
    SiteSetting,
)
from app.services.cms import ENTITIES, MEDIA_FIELDS, choices, persist
from app.services.content import public_context
from app.services.media import MediaError, delete_asset, paths, upload_image

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
@login_required
def require_admin():
    return None


@bp.get("/")
def dashboard():
    published_events = db.select(func.count(Event.id)).where(Event.status == "published")
    photos = db.select(func.count(MediaAsset.id))
    active_packages = db.select(func.count(PricingPackage.id)).where(
        PricingPackage.published.is_(True)
    )
    new_inquiries = db.select(func.count(BookingInquiry.id)).where(BookingInquiry.status == "baru")
    metrics = {
        "Event terbit": db.session.scalar(published_events),
        "Foto": db.session.scalar(photos),
        "Paket aktif": db.session.scalar(active_packages),
        "Inquiry baru": db.session.scalar(new_inquiries),
    }
    inquiry_statement = (
        db.select(BookingInquiry).order_by(BookingInquiry.created_at.desc()).limit(5)
    )
    inquiries = db.session.scalars(inquiry_statement).all()
    event_statement = db.select(Event).order_by(Event.updated_at.desc()).limit(5)
    events = db.session.scalars(event_statement).all()
    return render_template(
        "admin/dashboard.html",
        title="Dashboard",
        metrics=metrics,
        inquiries=inquiries,
        events=events,
    )


def entity_config(kind):
    if kind not in ENTITIES:
        abort(404)
    return ENTITIES[kind]


@bp.get("/<kind>")
def entity_list(kind):
    model, _, label, title_field = entity_config(kind)
    search = request.args.get("q", "").strip()[:120]
    status = request.args.get("status", "")
    stmt = db.select(model)
    if search:
        stmt = stmt.where(getattr(model, title_field).contains(search, autoescape=True))
    if kind == "events" and status in {"draft", "published"}:
        stmt = stmt.where(Event.status == status)
    if kind == "media":
        if search:
            stmt = db.select(model).where(
                or_(
                    model.original_name.contains(search, autoescape=True),
                    model.alt_text.contains(search, autoescape=True),
                    model.caption.contains(search, autoescape=True),
                )
            )
        stmt = stmt.options(joinedload(MediaAsset.category))
    page = db.paginate(
        stmt.order_by(model.updated_at.desc(), model.id.desc()),
        per_page=20,
        max_per_page=20,
        error_out=False,
    )
    return render_template(
        "admin/list.html",
        title=label,
        kind=kind,
        pagination=page,
        search=search,
        status=status,
        title_field=title_field,
    )


@bp.route("/<kind>/new", methods=["GET", "POST"])
@bp.route("/<kind>/<int:entity_id>/edit", methods=["GET", "POST"])
def entity_edit(kind, entity_id=None):
    model, form_type, label, _ = entity_config(kind)
    if kind == "media" and entity_id is None:
        return redirect(url_for("admin.media_upload"))
    obj = db.get_or_404(model, entity_id) if entity_id is not None else model()
    form = form_type(obj=obj if entity_id else None)
    choices(form)
    if request.method == "GET":
        for name in MEDIA_FIELDS | {"category_id", "rating"}:
            if hasattr(form, name):
                getattr(form, name).data = getattr(obj, name, None) or 0
        if kind == "pricing":
            form.features_text.data = "\n".join(x.label for x in obj.features)
        if kind == "events":
            form.media_ids.data = [x.media_id for x in obj.media]
            form.media_order.data = ",".join(str(x.media_id) for x in obj.media)
    if form.validate_on_submit() and persist(obj, form):
        flash("Perubahan berhasil disimpan.", "success")
        return redirect(url_for("admin.entity_edit", kind=kind, entity_id=obj.id))
    return render_template(
        "admin/edit.html",
        title=("Edit " if entity_id else "Tambah ") + label,
        kind=kind,
        form=form,
        obj=obj,
    ), 422 if request.method == "POST" else 200


@bp.route("/<kind>/<int:entity_id>/delete", methods=["GET", "POST"])
def entity_delete(kind, entity_id):
    model, _, label, title_field = entity_config(kind)
    obj = db.get_or_404(model, entity_id)
    form = DeleteForm()
    if form.validate_on_submit():
        try:
            if kind == "media":
                delete_asset(obj)
            else:
                db.session.delete(obj)
                db.session.commit()
            flash("Data berhasil dihapus.", "success")
            return redirect(url_for("admin.entity_list", kind=kind))
        except (IntegrityError, MediaError):
            db.session.rollback()
            flash("Data masih digunakan. Lepaskan relasinya sebelum menghapus.", "error")
    return render_template(
        "admin/delete.html",
        title="Hapus " + label,
        form=form,
        label=getattr(obj, title_field),
        back=url_for("admin.entity_list", kind=kind),
    ), 422 if request.method == "POST" else 200


@bp.route("/media/upload", methods=["GET", "POST"])
def media_upload():
    form = UploadForm()
    choices(form)
    wants_json = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if request.method == "GET":
        form.event_id.data = request.args.get("event", 0, type=int)
    if form.validate_on_submit():
        asset = None
        try:
            if len(request.files.getlist("image")) > 1:
                raise MediaError(
                    (
                        "Aktifkan JavaScript untuk mengunggah beberapa gambar, atau pilih "
                        "satu gambar per unggahan."
                    )
                )
            metadata = {
                key: getattr(form, key).data
                for key in [
                    "alt_text",
                    "caption",
                    "category_id",
                    "is_public",
                    "is_featured",
                    "sort_order",
                ]
            }
            metadata["category_id"] = metadata["category_id"] or None
            asset = upload_image(form.image.data, metadata)
            if form.event_id.data:
                event = db.get_or_404(Event, form.event_id.data)
                order = db.session.scalar(
                    db.select(func.max(EventMedia.sort_order)).where(
                        EventMedia.event_id == event.id
                    )
                )
                db.session.add(
                    EventMedia(
                        event_id=event.id,
                        media_id=asset.id,
                        sort_order=(order + 1 if order is not None else 0),
                    )
                )
            db.session.commit()
            if wants_json:
                return jsonify(ok=True, id=asset.id)
            flash("Foto berhasil diunggah dan dioptimalkan.", "success")
            return redirect(url_for("admin.entity_list", kind="media"))
        except (MediaError, IntegrityError):
            db.session.rollback()
            if asset:
                for path in paths(asset):
                    path.unlink(missing_ok=True)
            form.image.errors.append(
                (
                    "Unggahan ditolak. Gunakan JPEG/PNG/WebP valid, maks. 8 MB, 8 juta "
                    "piksel dan sisi 6000 px; coba lagi jika gambar lain sedang "
                    "diproses."
                )
            )
    if wants_json:
        return jsonify(ok=False, errors=form.errors), 422
    return render_template(
        "admin/upload.html", title="Unggah Foto", form=form
    ), 422 if request.method == "POST" else 200


@bp.route("/profile", methods=["GET", "POST"])
def profile_edit():
    obj = db.session.scalar(db.select(ArtistProfile)) or ArtistProfile(
        display_name="DJ NAZYER",
        hero_line_one="Feel The Beat.",
        hero_line_two="Own The Night.",
        decorative_tagline="Music. People. Better days.",
    )
    form = ProfileForm(obj=obj)
    choices(form)
    if request.method == "GET":
        form.hero_media_id.data = obj.hero_media_id or 0
        form.portrait_media_id.data = obj.portrait_media_id or 0
    if form.validate_on_submit() and persist(obj, form):
        flash("Profil berhasil disimpan.", "success")
        return redirect(url_for("admin.profile_edit"))
    return render_template(
        "admin/edit.html", title="Profil Artis", kind="profile", form=form, obj=obj
    ), 422 if request.method == "POST" else 200


@bp.route("/settings", methods=["GET", "POST"])
def settings_edit():
    rows = {x.key: x for x in db.session.scalars(db.select(SiteSetting))}
    data = {key: (row.media_id if key in MEDIA_FIELDS else row.value) for key, row in rows.items()}
    data.setdefault("site_title", "DJ NAZYER")
    data.setdefault("wordmark", "DJ NAZYER")
    form = SettingsForm(obj=SimpleNamespace(**data))
    choices(form)
    if request.method == "GET":
        for key in MEDIA_FIELDS:
            if hasattr(form, key):
                getattr(form, key).data = data.get(key) or 0
    if form.validate_on_submit():
        for field in form:
            if field.name in {"csrf_token", "submit"}:
                continue
            row = rows.get(field.name) or SiteSetting(key=field.name)
            if field.name in MEDIA_FIELDS:
                row.media_id = field.data or None
                row.value = ""
            else:
                row.value = (field.data or "").strip()
            db.session.add(row)
        db.session.commit()
        flash("Pengaturan berhasil disimpan.", "success")
        return redirect(url_for("admin.settings_edit"))
    return render_template(
        "admin/edit.html", title="Pengaturan Situs", kind="settings", form=form, obj=None
    ), 422 if request.method == "POST" else 200


@bp.get("/inquiries")
def inquiries():
    stmt = db.select(BookingInquiry).options(
        joinedload(BookingInquiry.service_type), joinedload(BookingInquiry.package)
    )
    status = request.args.get("status", "")
    search = request.args.get("q", "").strip()[:120]
    if status in dict(INQUIRY_STATUSES):
        stmt = stmt.where(BookingInquiry.status == status)
    if search:
        stmt = stmt.where(
            or_(
                BookingInquiry.name.contains(search, autoescape=True),
                BookingInquiry.contact.contains(search, autoescape=True),
                BookingInquiry.location.contains(search, autoescape=True),
            )
        )
    page = db.paginate(
        stmt.order_by(BookingInquiry.created_at.desc()),
        per_page=20,
        max_per_page=20,
        error_out=False,
    )
    return render_template(
        "admin/inquiries.html",
        title="Booking Inquiry",
        pagination=page,
        statuses=INQUIRY_STATUSES,
        status=status,
        search=search,
    )


@bp.route("/inquiries/<int:inquiry_id>", methods=["GET", "POST"])
def inquiry_detail(inquiry_id):
    inquiry = db.get_or_404(BookingInquiry, inquiry_id)
    form = InquiryAdminForm(obj=inquiry)
    if form.validate_on_submit():
        inquiry.status = form.status.data
        inquiry.internal_notes = form.internal_notes.data or ""
        db.session.commit()
        flash("Tindak lanjut inquiry disimpan.", "success")
        return redirect(url_for("admin.inquiry_detail", inquiry_id=inquiry.id))
    return render_template(
        "admin/inquiry.html", title="Detail Inquiry", inquiry=inquiry, form=form
    ), 422 if request.method == "POST" else 200


@bp.route("/inquiries/<int:inquiry_id>/delete", methods=["GET", "POST"])
def inquiry_delete(inquiry_id):
    inquiry = db.get_or_404(BookingInquiry, inquiry_id)
    form = DeleteForm()
    if form.validate_on_submit():
        db.session.delete(inquiry)
        db.session.commit()
        flash("Inquiry dihapus.", "success")
        return redirect(url_for("admin.inquiries"))
    return render_template(
        "admin/delete.html",
        title="Hapus Inquiry",
        label=inquiry.name,
        form=form,
        back=url_for("admin.inquiries"),
    )


@bp.get("/pricing/<int:entity_id>/preview")
def pricing_preview(entity_id):
    package = db.get_or_404(PricingPackage, entity_id)
    return render_template(
        "public/pricing.html",
        title="Pratinjau Paket (Admin)",
        page="pricing",
        packages=[package],
        preview=True,
        **public_context(),
    )
