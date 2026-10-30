import re

from flask_wtf.file import FileField, FileRequired
from wtforms import (
    BooleanField,
    DateField,
    DecimalField,
    HiddenField,
    IntegerField,
    SelectField,
    SelectMultipleField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional, ValidationError

from app.forms.base import IndonesianForm as FlaskForm
from app.forms.base import select_choices
from app.services.content import safe_url


def required(maximum=180):
    return [
        DataRequired(message="Kolom ini wajib diisi."),
        Length(max=maximum, message=f"Maksimal {maximum} karakter."),
    ]


def optional(maximum=500):
    return [Optional(), Length(max=maximum, message=f"Maksimal {maximum} karakter.")]


def slug_value(form, field):
    if field.data and not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", field.data):
        raise ValidationError("Gunakan huruf kecil, angka, dan tanda hubung.")


def https_url(form, field):
    if field.data and not safe_url(field.data):
        raise ValidationError("Gunakan URL HTTPS yang valid, tanpa kredensial.")


class SaveForm(FlaskForm):
    submit = SubmitField("Simpan Perubahan")


class CategoryForm(SaveForm):
    name = StringField("Nama", validators=required(100))
    slug = StringField("Slug (otomatis jika kosong)", validators=optional(120) + [slug_value])
    sort_order = IntegerField("Urutan", default=0, validators=[NumberRange(min=0, max=9999)])


class ServiceForm(CategoryForm):
    icon = SelectField(
        "Ikon",
        choices=select_choices(
            [
                ("music", "Musik"),
                ("users", "Private event"),
                ("heart", "Pernikahan"),
                ("building-2", "Korporat"),
                ("star", "Spesial"),
            ]
        ),
    )
    active = BooleanField("Aktif", default=True)


class EventForm(SaveForm):
    title = StringField("Judul event", validators=required())
    slug = StringField("Slug (otomatis jika kosong)", validators=optional(200) + [slug_value])
    date = DateField(
        "Tanggal event", validators=[DataRequired(message="Tanggal event wajib diisi.")]
    )
    venue = StringField("Venue", validators=optional(180))
    location = StringField("Lokasi", validators=optional(180))
    category_id = SelectField("Kategori event", coerce=int)
    status = SelectField(
        "Status", choices=select_choices([("draft", "Draft"), ("published", "Terbit")])
    )
    featured = BooleanField("Tampilkan sebagai featured performance")
    cover_id = SelectField("Foto cover", coerce=int)
    description = TextAreaField("Deskripsi", validators=optional(20000))
    video_url = StringField(
        "URL video recap (HTTPS, opsional)", validators=optional(500) + [https_url]
    )
    media_ids = SelectMultipleField(
        "Foto galeri (pilih beberapa)",
        coerce=int,
        description="Gunakan Ctrl/⌘ untuk memilih beberapa foto. Atur urutan foto di bawah.",
    )
    media_order = HiddenField(validators=optional(5000))


class PricingForm(SaveForm):
    name = StringField("Nama paket", validators=required(120))
    slug = StringField("Slug (otomatis jika kosong)", validators=optional(150) + [slug_value])
    price = DecimalField(
        "Harga mulai (Rp)",
        places=0,
        validators=[Optional(), NumberRange(min=0, max=99999999999999)],
        description="Kosongkan untuk Hubungi untuk Penawaran.",
    )
    duration = StringField("Durasi", validators=optional(100))
    description = TextAreaField("Deskripsi", validators=optional(5000))
    features_text = TextAreaField(
        "Fitur paket",
        validators=optional(8000),
        description="Satu fitur per baris, maksimal 30 fitur dan 250 karakter per fitur.",
    )
    notes = TextAreaField("Catatan", validators=optional(5000))
    featured = BooleanField("Paket unggulan")
    published = BooleanField("Terbit")
    sort_order = IntegerField("Urutan", default=0, validators=[NumberRange(min=0, max=9999)])

    def validate_features_text(self, field):
        lines = [x.strip() for x in (field.data or "").splitlines() if x.strip()]
        if len(lines) > 30 or any(len(x) > 250 for x in lines):
            raise ValidationError("Maksimal 30 fitur, masing-masing 250 karakter.")


class TestimonialForm(SaveForm):
    name = StringField("Nama klien", validators=required(120))
    context = StringField("Konteks event / lokasi", validators=optional(180))
    quote = TextAreaField("Testimoni asli", validators=required(5000))
    rating = SelectField(
        "Rating (hanya jika diberikan klien)",
        coerce=int,
        choices=select_choices([(0, "Tanpa rating")] + [(x, str(x)) for x in range(1, 6)]),
    )
    portrait_id = SelectField("Foto klien (opsional)", coerce=int)
    published = BooleanField("Terbit")
    sort_order = IntegerField("Urutan", default=0, validators=[NumberRange(min=0, max=9999)])


class ProfileForm(SaveForm):
    display_name = StringField("Nama tampilan", validators=required(100))
    hero_line_one = StringField("Headline hero — baris pertama", validators=required(100))
    hero_line_two = StringField("Headline hero — baris kedua", validators=required(100))
    hero_description = TextAreaField("Deskripsi hero", validators=optional(500))
    decorative_tagline = StringField("Tagline dekoratif", validators=optional(120))
    hero_media_id = SelectField("Foto hero", coerce=int)
    portrait_media_id = SelectField("Foto profil", coerce=int)
    bio_summary = TextAreaField("Ringkasan biografi", validators=optional(2000))
    biography = TextAreaField("Biografi lengkap", validators=optional(20000))
    genres = StringField("Genre musik", validators=optional(250))
    philosophy = TextAreaField("Filosofi performance", validators=optional(5000))
    career_highlights = TextAreaField(
        "Highlight karier (fakta yang sudah diverifikasi)", validators=optional(10000)
    )


class HighlightForm(SaveForm):
    label = StringField("Label", validators=required(100))
    value = StringField("Nilai statistik (opsional, data asli)", validators=optional(50))
    sort_order = IntegerField("Urutan", default=0, validators=[NumberRange(min=0, max=9999)])


class MediaForm(SaveForm):
    alt_text = StringField(
        "Alt text",
        validators=optional(250),
        description="Deskripsikan isi foto untuk pembaca layar.",
    )
    caption = StringField("Caption", validators=optional(500))
    category_id = SelectField("Kategori galeri", coerce=int)
    is_public = BooleanField("Tampilkan di galeri publik")
    is_featured = BooleanField("Tampilkan di strip recap beranda (harus publik)")
    sort_order = IntegerField("Urutan", default=0, validators=[NumberRange(min=0, max=9999)])


class UploadForm(MediaForm):
    image = FileField(
        "Pilih gambar",
        validators=[FileRequired(message="Pilih satu gambar JPEG, PNG, atau WebP.")],
        description=(
            "Maks. 8 MB, 8 juta piksel, sisi terpanjang 6000 px. Satu gambar diproses per request."
        ),
    )
    event_id = SelectField("Tambahkan ke galeri event (opsional)", coerce=int)
    submit = SubmitField("Unggah Foto")


INQUIRY_STATUSES = [
    ("baru", "Baru"),
    ("dihubungi", "Dihubungi"),
    ("negosiasi", "Negosiasi"),
    ("terkonfirmasi", "Terkonfirmasi"),
    ("ditutup", "Ditutup"),
]


class InquiryAdminForm(SaveForm):
    status = SelectField("Status tindak lanjut", choices=select_choices(INQUIRY_STATUSES))
    internal_notes = TextAreaField("Catatan internal", validators=optional(10000))


class SettingsForm(SaveForm):
    site_title = StringField("Judul situs", validators=required(120))
    wordmark = StringField("Wordmark teks", validators=optional(100))
    meta_description = TextAreaField("Meta description default", validators=optional(300))
    footer_description = StringField("Deskripsi footer", validators=optional(300))
    whatsapp = StringField(
        "Nomor WhatsApp",
        validators=optional(25),
        description="Format internasional, misalnya 62…; kosongkan jika belum tersedia.",
    )
    booking_email = StringField(
        "Email booking",
        validators=[Optional(), Email(message="Alamat email tidak valid."), Length(max=254)],
    )
    instagram = StringField("URL Instagram", validators=optional(500) + [https_url])
    tiktok = StringField("URL TikTok", validators=optional(500) + [https_url])
    youtube = StringField("URL YouTube", validators=optional(500) + [https_url])
    spotify = StringField("URL Spotify", validators=optional(500) + [https_url])
    logo_id = SelectField("Logo gambar (opsional)", coerce=int)
    favicon_id = SelectField("Favicon (opsional)", coerce=int)
    share_image_id = SelectField("Gambar Open Graph (opsional)", coerce=int)

    def validate_whatsapp(self, field):
        if field.data and not re.fullmatch(r"\+?[0-9][0-9 -]{7,24}", field.data):
            raise ValidationError("Nomor WhatsApp tidak valid.")


class DeleteForm(FlaskForm):
    confirm = BooleanField(
        "Saya memahami data ini akan dihapus.",
        validators=[DataRequired(message="Centang konfirmasi untuk menghapus.")],
    )
    submit = SubmitField("Ya, Hapus")
