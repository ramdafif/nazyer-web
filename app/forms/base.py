from flask_wtf import FlaskForm
from wtforms.fields.choices import SelectChoice


def select_choices(pairs):
    return [SelectChoice(str(value), label) for value, label in pairs]


class IndonesianTranslations:
    messages = {
        "This field is required.": "Kolom ini wajib diisi.",
        "Not a valid choice.": "Pilihan tidak valid.",
        "Not a valid date value.": "Tanggal tidak valid.",
        "Not a valid datetime value.": "Tanggal dan waktu tidak valid.",
        "Not a valid integer value.": "Masukkan bilangan bulat yang valid.",
        "Not a valid decimal value.": "Masukkan angka yang valid.",
        "Field must be at least %(min)d characters long.": "Minimal %(min)d karakter.",
        "Field cannot be longer than %(max)d characters.": "Maksimal %(max)d karakter.",
        "Field must be between %(min)d and %(max)d characters long.": (
            "Panjang harus antara %(min)d dan %(max)d karakter."
        ),
        "Number must be at least %(min)s.": "Angka minimal %(min)s.",
        "Number must be at most %(max)s.": "Angka maksimal %(max)s.",
        "Number must be between %(min)s and %(max)s.": "Angka harus antara %(min)s dan %(max)s.",
        "Invalid Choice: could not coerce.": "Pilihan tidak valid.",
        "Invalid choice(s): one or more data inputs could not be coerced.": (
            "Salah satu pilihan tidak valid."
        ),
        "'%(value)s' is not a valid choice for this field.": "Pilihan tidak valid.",
    }

    def gettext(self, message):
        return self.messages.get(message, message)

    def ngettext(self, singular, plural, n):
        return self.gettext(singular if n == 1 else plural)


class IndonesianForm(FlaskForm):
    class Meta(FlaskForm.Meta):
        def get_translations(self, form):
            return IndonesianTranslations()
