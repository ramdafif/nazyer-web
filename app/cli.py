import click
from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import AdminUser


def register_cli(app):
    @app.cli.command("create-admin")
    @click.option("--username", prompt="Nama pengguna")
    def create_admin(username):
        """Create an administrator with a hidden, confirmed password prompt."""
        username = username.strip()
        if not username or len(username) > 80:
            raise click.ClickException("Nama pengguna wajib diisi (maks. 80 karakter).")
        if db.session.scalar(db.select(AdminUser).where(AdminUser.username == username)):
            raise click.ClickException("Nama pengguna sudah terdaftar.")
        password = click.prompt(
            "Password (minimal 12 karakter)", hide_input=True, confirmation_prompt=True
        )
        user = AdminUser(username=username)
        try:
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
        except (ValueError, IntegrityError) as exc:
            db.session.rollback()
            raise click.ClickException(
                "Admin tidak dibuat. Periksa nama pengguna dan panjang password."
            ) from exc
        click.echo("Admin berhasil dibuat.")

    @app.cli.command("seed-demo")
    def seed_demo():
        """Seed explicitly marked preview data, never in production."""
        if current_app.config["APP_ENV"] == "production":
            raise click.ClickException("seed-demo dilarang di production.")
        from app.services.demo import seed

        seed()
        click.echo("Data DEMO dibuat. Bukan informasi asli DJ NAZYER.")
