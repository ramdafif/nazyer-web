import re
from datetime import datetime
from zoneinfo import ZoneInfo

from wtforms import DateField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from app.forms.base import IndonesianForm as FlaskForm
from app.forms.base import select_choices


def contact_number(form, field):
    if not re.fullmatch(r"\+?[0-9][0-9 ()-]{7,24}", field.data.strip()):
        raise ValidationError("Masukkan nomor kontak yang valid.")


class InquiryForm(FlaskForm):
    name = StringField("Nama lengkap *", validators=[DataRequired(), Length(min=2, max=120)])
    contact = StringField(
        "Nomor WhatsApp / telepon *", validators=[DataRequired(), Length(max=80), contact_number]
    )
    service_type_id = SelectField(
        "Jenis event", coerce=int, choices=select_choices([(0, "Pilih jenis event")])
    )
    event_date = DateField("Tanggal event (opsional)", validators=[Optional()])
    location = StringField("Lokasi event *", validators=[DataRequired(), Length(max=200)])
    package_id = SelectField(
        "Paket (opsional)", coerce=int, choices=select_choices([(0, "Konsultasi terlebih dahulu")])
    )
    message = TextAreaField(
        "Ceritakan rencana acara Anda *", validators=[DataRequired(), Length(min=10, max=3000)]
    )
    website = StringField("Kosongkan kolom ini", validators=[Optional(), Length(max=200)])
    submit = SubmitField("Kirim Inquiry")

    def validate_event_date(self, field):
        if field.data and field.data < datetime.now(ZoneInfo("Asia/Jakarta")).date():
            raise ValidationError("Tanggal event tidak boleh di masa lalu.")
