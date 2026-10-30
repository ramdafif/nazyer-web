from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length

from app.forms.base import IndonesianForm as FlaskForm


class LoginForm(FlaskForm):
    username = StringField("Nama pengguna", validators=[DataRequired(), Length(max=80)])
    password = PasswordField("Password", validators=[DataRequired(), Length(max=128)])
    submit = SubmitField("Masuk ke Dashboard")


class PasswordForm(FlaskForm):
    current_password = PasswordField(
        "Password saat ini", validators=[DataRequired(), Length(max=128)]
    )
    password = PasswordField("Password baru", validators=[DataRequired(), Length(min=12, max=128)])
    confirm = PasswordField(
        "Ulangi password baru", validators=[EqualTo("password", message="Password belum sama.")]
    )
    submit = SubmitField("Simpan password")
