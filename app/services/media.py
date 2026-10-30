import io
import os
import secrets
import warnings
from contextlib import contextmanager
from pathlib import Path

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import exists, or_
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import ArtistProfile, Event, EventMedia, MediaAsset, SiteSetting, Testimonial

ALLOWED = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}


class MediaError(ValueError):
    pass


@contextmanager
def processing_slot():
    """Only one Pillow decode across the two production workers at a time."""
    import fcntl

    with open(Path(current_app.config["MEDIA_ROOT"]) / ".processing.lock", "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise MediaError("Gambar lain sedang diproses. Coba kembali sebentar lagi.") from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def paths(asset):
    root = Path(current_app.config["MEDIA_ROOT"])
    return [root / name for name in (asset.filename, asset.small, asset.thumbnail)]


def upload_image(file, metadata):
    original = secure_filename(file.filename or "")
    extension = Path(original).suffix.lower()
    if extension not in ALLOWED:
        raise MediaError("Format yang diizinkan: JPEG, PNG, dan WebP. SVG/GIF tidak diterima.")
    raw = file.stream.read(8 * 1024 * 1024 + 1)
    if not raw or len(raw) > 8 * 1024 * 1024:
        raise MediaError("Gambar kosong atau melebihi 8 MB.")
    filename = secrets.token_hex(20) + ".webp"
    asset = MediaAsset(filename=filename, original_name=original[:200], **metadata)
    written = []
    try:
        with processing_slot(), warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as check:
                if check.format != ALLOWED[extension] or getattr(check, "n_frames", 1) != 1:
                    raise MediaError("Isi gambar tidak sesuai ekstensi atau gambar beranimasi.")
                width, height = check.size
                if (
                    width * height > current_app.config["MAX_IMAGE_PIXELS"]
                    or max(width, height) > 6000
                    or min(width, height) < 32
                ):
                    raise MediaError(
                        "Dimensi harus minimal 32 px, maksimal 8 juta piksel dan 6000 px per sisi."
                    )
                check.verify()
            with Image.open(io.BytesIO(raw)) as source:
                source = ImageOps.exif_transpose(source)
                source.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                # A fresh pixel-only image strips EXIF, XMP, ICC and original metadata.
                converted = source.convert("RGBA" if "A" in source.getbands() else "RGB")
                clean = Image.new(converted.mode, converted.size)
                clean.paste(converted)
                asset.width, asset.height = clean.size
                for target, size, quality in [
                    (filename, 1600, 84),
                    (asset.small, 640, 82),
                    (asset.thumbnail, 320, 78),
                ]:
                    variant = clean.copy()
                    variant.thumbnail((size, size), Image.Resampling.LANCZOS)
                    path = Path(current_app.config["MEDIA_ROOT"]) / target
                    variant.save(path, "WEBP", quality=quality, method=4)
                    os.chmod(path, 0o640)
                    written.append(path)
                    variant.close()
                clean.close()
                converted.close()
        asset.byte_size = sum(p.stat().st_size for p in written)
        db.session.add(asset)
        db.session.flush()
        return asset
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        SyntaxError,
        ValueError,
    ) as exc:
        for path in written:
            path.unlink(missing_ok=True)
        if isinstance(exc, MediaError):
            raise
        raise MediaError("Gambar rusak atau tidak dapat diproses.") from exc
    except Exception:
        for path in written:
            path.unlink(missing_ok=True)
        raise


def in_use(asset_id):
    checks = [
        db.select(ArtistProfile.id).where(
            or_(
                ArtistProfile.hero_media_id == asset_id, ArtistProfile.portrait_media_id == asset_id
            )
        ),
        db.select(Event.id).where(Event.cover_id == asset_id),
        db.select(EventMedia.id).where(EventMedia.media_id == asset_id),
        db.select(Testimonial.id).where(Testimonial.portrait_id == asset_id),
        db.select(SiteSetting.id).where(SiteSetting.media_id == asset_id),
    ]
    return any(db.session.scalar(db.select(exists(query))) for query in checks)


def delete_asset(asset):
    if in_use(asset.id):
        raise MediaError(
            (
                "Foto masih dipakai. Lepaskan dari profil, event, testimoni, atau "
                "pengaturan terlebih dahulu."
            )
        )
    files = paths(asset)
    try:
        db.session.delete(asset)
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise MediaError("Foto masih dipakai dan tidak dapat dihapus.") from exc
    for file in files:
        file.unlink(missing_ok=True)
