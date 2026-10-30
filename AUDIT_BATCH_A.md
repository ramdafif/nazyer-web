# Laporan Audit Fix — Batch A

Baseline: `78b86ba` (Phase 5), 29 Oktober 2026. Semua pekerjaan dilakukan pada
checkout lokal dan database SQLite uji terisolasi. Tidak ada server, database,
domain, konfigurasi Nginx/MySQL live, atau service systemd yang diubah.

## A1 — Format source tanpa perubahan perilaku

Diubah: template Jinja, CSS/JS, Python aplikasi/migrasi/test/script;
`pyproject.toml`, `requirements-dev.txt`, `requirements-dev.lock`,
`scripts/format.sh`, `scripts/format_assets.py`, `scripts/audit_format.py`, dan README.
Query beranda/dashboard/profil dipisahkan ke variabel bernama tanpa mengubah
urutan eksekusi, filter, batas hasil, atau output. String literal Python di seluruh
`app/` dibandingkan lewat AST dengan baseline: **tidak ada perubahan**.

Formatter dev: djLint 1.47.1, cssbeautifier/jsbeautifier 2.0.3, Ruff 0.17.3;
seluruhnya paket Python. Target panjang baris formatter Python adalah 100 karakter.
Tidak ada minifier dan tidak ada Node runtime baru.

| File | Baris sebelum → sesudah | Baris terpanjang sebelum → sesudah |
| --- | --- | --- |
| `public/home.html` | 8 → 208 | 1.420 → 126 karakter |
| `admin/edit.html` | 1 → 72 | 1.954 → 97 karakter |
| `pages/public.css` | 9 → 1.825 | 15.222 → 153 karakter |

Bukti yang benar-benar dijalankan:

- Capture sebelum/sesudah menggunakan `scripts/audit_format.py capture`:
  **58 halaman/varian route** publik dan admin dengan fixture demo yang sama.
  Waktu penandatanganan/CSRF dibuat deterministik; data dan UUID gambar tidak dibuat ulang.
- `scripts/audit_format.py compare`: **0 perbedaan HTML setelah normalisasi whitespace**.
  Normalisasi mempertahankan atribut URL/data secara persis, menormalkan indentasi
  teks normal dan whitespace sah pada atribut `sizes`. Teks `.prose`, `pre`, `code`,
  dan `textarea` dibandingkan persis; kontrol whitespace Jinja dipasang pada teks
  sensitif untuk mencegah tambahan baris kosong.
- Terdapat perubahan whitespace batas teks pada 54 halaman: misalnya teks wordmark
  `DJ NAZYER` sekarang dikelilingi newline/indentasi source. Teks ter-normalisasi
  sama; whitespace pada batas baris/flex tersebut tidak mengubah layout.
  Seluruh contoh sebelum/sesudah tersimpan di `audit-evidence/a1-comparison.json`.
- `bash scripts/format.sh --check`: lolos (Ruff format/check, djLint HTML/XML,
  cssbeautifier/jsbeautifier), serta `git diff --check`: bersih.
- `pytest -q`: **94 passed in 43.35s**, termasuk 17 kasus browser pada
  viewport 375/768/1280 px. Assertion SEO diperbaiki agar menerima whitespace sah
  di antara atribut HTML; nilai metadata tetap diperiksa dengan ketat.

Selisih piksel screenshot full-page, Chromium yang sama, device scale 1,
font/gambar selesai dimuat dan motion dimatikan:

| Halaman | 375 px | 768 px | 1280 px |
| --- | --- | --- | --- |
| Beranda | 0 piksel (0%) | 0 piksel (0%) | 0 piksel (0%) |
| Galeri | 0 piksel (0%) | 0 piksel (0%) | 0 piksel (0%) |
| Kontak | 0 piksel (0%) | 0 piksel (0%) | 0 piksel (0%) |
| Dashboard admin | 0 piksel (0%) | 0 piksel (0%) | 0 piksel (0%) |

Capture HTML dan 12 pasangan screenshot berada di `audit-evidence/a1-before/`
dan `audit-evidence/a1-after/` dalam paket hasil. Bukti ini menggunakan konten
DEMO; tidak ada foto atau data pribadi produksi.

Belum diverifikasi: kesamaan pixel pada semua kombinasi konten/peramban di luar
fixture dan 12 kombinasi yang diukur. Test MySQL, PSS/cgroup, Lighthouse throttled,
dan restore rehearsal tetap berada di luar Batch A.

## A2 — Versi aset dan kebijakan cache

Diubah: `app/services/assets.py`, application factory, seluruh pemanggilan static
di template/ikon, CSS publik/admin, salinan font berhash dan manifest,
`scripts/prepare_assets.py`, `tests/test_assets.py`, README,
`deployment/nginx.conf`, serta contoh map `nginx-static-cache.conf.example`.

`asset_url()` tersedia melalui Jinja global dan context processor. SHA-256
dihitung sekali saat startup dari `Path(app.root_path) / 'static'`; URL memakai
10 karakter hex pertama. Lookup per request tidak membaca file. Salinan font
yang dilayani memakai nama berhash; file tanpa hash adalah input developer.
Perubahan font/background CSS disiapkan oleh script Python yang juga memperbarui
versi dependensi CSS, sehingga cache CSS ikut berubah. Tidak ada bundler/minifier.

Contoh Nginx hanya memakai `add_header` untuk Cache-Control, dengan `expires off`.
Aset berversi: satu tahun + immutable; font: 30 hari; URL static tanpa versi:
validasi ulang. Map unik dipasang sebagai contoh file baru pada konteks `http {}`.
Regex upload diberi quote agar quantifier-nya tidak ambigu bagi parser konfigurasi.

Bukti yang benar-benar dijalankan:

- `pytest tests/test_assets.py -q`: **18 passed**.
- `pytest -q`: **112 passed in 37.95s**, termasuk seluruh 17 kasus browser.
- `python scripts/prepare_assets.py --check`, formatter/linter check, dan
  `git diff --check`: lolos.
- Test memeriksa query `?v=` sesuai isi file pada halaman publik/admin, perubahan
  hash pada startup berikutnya, tidak adanya file I/O saat lookup, tidak adanya
  `url_for('static'` pada template, serta pergantian nama font/dependensi CSS.
- Factory production dengan `static_folder=None` benar-benar merender login dan
  template galeri dengan context eksplisit, tanpa menghubungkan ke MySQL.

Belum diverifikasi: respons header dari proses Nginx sebenarnya (`nginx -t` dan
request staging belum dijalankan). Script penyiapan aset dan restart aplikasi
wajib masuk alur rilis; kode tidak memodifikasi static saat melayani request.

## A3 — Bahasa formal-hangat

Diubah: copy publik pada template/form/blueprint, label pengaturan/unggah/pratinjau
admin, pesan unggah di backend dan JS, assertion browser untuk halaman sukses,
serta `tests/test_language.py`. Sapaan menggunakan Anda/kami; headline brand
Inggris dipertahankan. Route, nama field, validasi, model, dan alur simpan tidak berubah.

Contoh: “Inquiry Anda sudah kami terima”, “Ceritakan rencana acara Anda”, dan
“Kontak Anda hanya digunakan untuk menindaklanjuti inquiry ini”. Copy bawaan
metadata, empty state, CTA, serta pilihan “Konsultasi terlebih dahulu” ikut diperiksa.

Bukti yang benar-benar dijalankan:

- `pytest tests/test_language.py -q`: **17 passed**.
- `pytest -q`: **129 passed in 40.26s**, termasuk seluruh 17 kasus browser.
- Pemindai AST Python dan AST Jinja memeriksa string template, form, blueprint,
  service, dan seed demo dengan pola kata utuh `\b(lo|lu|gue|gw)\b`.
  Test positif/negatif membuktikan kata terlarang ditolak tanpa menandai kata
  seperti lokasi, logo, global, glow, workflow, katalog, gulir, dan dialog.
- Pencarian case-insensitive pada source aplikasi/Python/HTML/JS untuk kata-kata
  tersebut dan bentuk slang lain yang ditemukan: **0 hasil**.
- Formatter/linter, versi aset, dan `git diff --check`: lolos.

Belum diverifikasi: bahasa konten bebas yang kelak dimasukkan pemilik melalui CMS.
Konten database pengguna tidak ditulis ulang; pemindai menjaga copy bawaan source.

## A4 — Update kode menggunakan restart

Diubah: `deployment/dj-nazyer.service`, README, dan `tests/test_deployment.py`.
Directive `ExecReload` dihapus. Komentar unit dan panduan menyatakan update kode
memakai `systemctl restart dj-nazyer`; `preload_app=True` dan dua worker tetap dipertahankan.
Reload Nginx untuk perubahan konfigurasinya dibedakan dari restart kode Python.

Bukti yang benar-benar dijalankan:

- `pytest tests/test_deployment.py -q`: **1 passed**.
- `pytest -q`: **130 passed in 39.45s**, termasuk seluruh 17 kasus browser.
- Test membaca konfigurasi Gunicorn dan mem-parse unit: preload tetap aktif,
  worker tetap dua, serta tidak ada opsi `ExecReload`.
- Ruff format/check: lolos.

Belum diverifikasi: instalasi unit, siklus restart, unix socket, dan health check
pada systemd VPS sebenarnya. Tidak ada perintah restart/reload service yang dijalankan.

## A5 — Log akses yang aman dan kompresi

Diubah: `deployment/nginx.conf`, contoh baru
`deployment/nginx-log-format.conf.example` dan
`deployment/dj-nazyer-logrotate.conf.example`, README, dan
`tests/test_deployment.py`. Contoh exact-location pada
`deployment/rate-limits.conf.example` hanya mendapat pengecualian gzip yang sama;
status deployment rate limit lintas worker tidak diubah (B3 belum dikerjakan).

Format `nazyer_safe` pada konteks `http {}` mencatat IP, waktu ISO, method,
`$uri`, status, ukuran respons, dan user agent. Query string, body, cookie,
authorization, dan referrer tidak masuk format. `escape=json` melindungi struktur
log dari quote/control character. Log situs memakai direktori tersendiri agar
tidak berbagi berkas dengan situs lain.

Gzip diaktifkan pada contoh vhost untuk HTML publik, CSS, JavaScript, SVG, dan XML,
dengan komentar agar mewarisi konfigurasi global yang setara bila sudah tersedia.
Respons admin/kontak yang memuat informasi sesi/CSRF dikecualikan dari gzip;
directive proxy lain tetap sama. Tidak ada minifier.

README menjelaskan IP/user agent sebagai data pribadi, izin berkas terbatas,
serta anjuran maksimum 14 hari total. Contoh logrotate memakai 13 arsip harian
ditambah berkas aktif, `maxage 13`, dan rotasi berkas kosong agar usia arsip tetap
berjalan. Jadwal harian dan aturan yang tumpang tindih wajib diperiksa pada host;
tidak ada konfigurasi atau job yang diaktifkan.

Bukti yang benar-benar dijalankan:

- `pytest tests/test_deployment.py -q`: **4 passed in 0.02s**.
- `pytest -q`: **133 passed in 41.36s**, termasuk seluruh 17 kasus browser pada
  viewport 375/768/1280 px. Log lengkap tersimpan di `audit-evidence/A5-pytest.txt`.
- Test memeriksa tujuh variabel log yang diizinkan, fixture JSON dengan user agent
  berisi quote/newline dan query rahasia yang tidak tercatat, directive gzip,
  pengecualian admin/kontak, kesamaan directive proxy, dan kebijakan rotasi.
- `bash scripts/format.sh --check`, `python scripts/prepare_assets.py --check`,
  dan `git diff --check`: lolos.

Belum diverifikasi: `nginx -t`, header cache/gzip/log dari proses Nginx sebenarnya,
serta rotasi dan penghapusan log nyata. Nginx dan logrotate tidak tersedia pada
lingkungan ini. Test konfigurasi source tidak menggantikan validasi staging;
retensi bergantung pada jadwal logrotate host yang berjalan. Tidak ada service
atau konfigurasi live yang disentuh.

## Penyerahan dan batas verifikasi

Setiap item A1–A5 mempunyai satu commit pada cabang lokal `audit/batch-a`.
Tidak ada remote Git yang dikonfigurasi dan tidak ada push. Paket hasil memuat
source, bundle seluruh riwayat Git, laporan ini, lima log pytest, serta bukti
HTML dan screenshot A1 sebelum/sesudah. Screenshot tersebut berisi fixture demo.

Batch B belum dikerjakan dan menunggu instruksi `lanjut` setelah Batch A.
Uji MySQL staging, pengukuran RAM PSS/cgroup di VPS, Lighthouse mobile dengan
throttling, dan restore rehearsal tetap belum dijalankan. Hasil lokal ini tidak
menyatakan penerimaan deployment production atau tercapainya budget RAM.

## Status akhir

| Item | Status |
| --- | --- |
| A1 | selesai |
| A2 | selesai |
| A3 | selesai |
| A4 | selesai |
| A5 | selesai |
