import hmac

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, fresh_login_required, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, limiter
from app.forms.auth import LoginForm, PasswordForm
from app.models import AdminUser

bp = Blueprint("auth", __name__, url_prefix="/admin")
_DUMMY_HASH = generate_password_hash("unused-timing-check", method="scrypt:16384:8:1")


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
@limiter.limit("30 per hour", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            db.select(AdminUser).where(AdminUser.username == form.username.data.strip())
        )
        valid = check_password_hash(user.password_hash if user else _DUMMY_HASH, form.password.data)
        if user and valid and user.active:
            session.clear()
            session.permanent = True
            login_user(user, fresh=True)
            # Never redirect to an untrusted next URL.
            return redirect(url_for("admin.dashboard"))
        flash("Nama pengguna atau password tidak sesuai.", "error")
    return render_template("auth/login.html", form=form, title="Login Admin")


@bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    if request.method != "POST":
        abort(405)
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/password", methods=["GET", "POST"])
@fresh_login_required
@limiter.limit("5 per minute", methods=["POST"])
def password():
    form = PasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            form.current_password.errors.append("Password saat ini tidak sesuai.")
        elif hmac.compare_digest(form.current_password.data, form.password.data):
            form.password.errors.append("Pilih password yang berbeda.")
        else:
            current_user.set_password(form.password.data)
            current_user.session_version += 1
            db.session.commit()
            logout_user()
            session.clear()
            flash("Password diperbarui. Silakan masuk kembali.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/password.html", form=form, title="Ganti Password")
