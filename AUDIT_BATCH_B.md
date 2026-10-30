# Laporan Audit Fix — Batch B

Baseline: `24d38ba` (Batch A), 29 Oktober 2026. Pekerjaan dilakukan di cabang
lokal `audit/batch-b`, tanpa remote/push, koneksi ke server live, perubahan domain,
atau aktivasi Nginx/MySQL/systemd. Satu item mempunyai satu commit.

## B1 — Test MySQL opt-in

Diubah: `tests/test_mysql.py`, `tests/test_mysql_safety.py`, dan README.
Sembilan kasus berpenanda `mysql` mencakup CLI upgrade/downgrade pada skema kosong,
unique slug, roundtrip emoji utf8mb4, pencarian LIKE literal `%`, `_`, `/`, `\`,
filter tahun pada batas tanggal dengan draft tersembunyi, dan lock upload pada dua
proses terpisah. Proses upload menggunakan request admin sebenarnya dan barrier
pada lock file agar contention deterministik, lalu menguji retry setelah lock lepas.

Target harus `mysql+pymysql`, user non-root, dan nama skema dengan segmen `test`.
Skema berisi tabel/view ditolak sebelum migrasi. Fixture memeriksa MySQL 8 dan
charset utf8mb4, tidak membuat database/user, serta membersihkan migrasi dan tabel
Alembic miliknya pada database uji. Tidak ada URL atau password yang dicetak.

Bukti yang benar-benar dijalankan:

- `pytest tests/test_mysql.py tests/test_mysql_safety.py -q`:
  **7 passed, 9 skipped in 1.99s** pada pemeriksaan awal.
- `pytest -q`: **140 passed, 9 skipped in 43.29s**, termasuk seluruh 17 kasus
  Chromium pada viewport 375/768/1280 px. Log: `audit-evidence/B1-pytest.txt`.
- Tujuh kasus yang lulus menguji pengaman URL dan harness dua proses pada SQLite
  terisolasi; ini **bukan bukti kompatibilitas MySQL**.
- `bash scripts/format.sh --check` dan `python scripts/prepare_assets.py --check`
  dari virtualenv, serta `git diff --check`: lolos. Pemanggilan formatter awal
  tanpa aktivasi virtualenv gagal menemukan Ruff; telah diulang dengan virtualenv.

Belum diverifikasi: **sembilan test MySQL nyata tidak dijalankan** karena
`MYSQL_TEST_URL` tidak diatur dan MySQL tidak tersedia. Suite siap dijalankan
pemilik pada database uji khusus; tidak ada koneksi MySQL yang dicoba di sini.

## B2 — Backup harian dan retensi

Diubah: `deployment/backup.sh`, contoh baru `dj-nazyer-backup.service`,
`dj-nazyer-backup.timer`, `backup.env.example`, `tests/test_backup.py`, dan README.
Timer menargetkan 03.15 Asia/Jakarta dengan jitter maksimal lima menit;
`Persistent=true` dapat mengejar jadwal terlewat setelah boot. Unit oneshot
berjalan sebagai user aplikasi, menulis hanya ke direktori backup, dan tidak
menghentikan service apa pun.

Script memakai file kredensial 0600, lock untuk menolak backup paralel, dan
publikasi atomik. Setelah sukses, hanya bundle reguler dengan nama timestamp
yang valid yang dipangkas menjadi 14 terbaru. Kegagalan dump tidak memangkas
backup lama atau menerbitkan arsip parsial. Dump hanya database aplikasi dan
tidak menambahkan pengaturan GTID global. Path media dapat diarahkan ke fixture
terisolasi untuk pengujian; default produksi tetap `/var/lib/dj-nazyer/uploads`.

README menjelaskan batas backup online DB/media, langkah maintenance offline
untuk konsistensi, penyalinan off-VPS melalui proses yang sudah ada, izin/data
pribadi, monitoring freshness, dan checklist restore rehearsal ke target terpisah.

Bukti yang benar-benar dijalankan:

- `pytest tests/test_backup.py -q`: **5 passed in 0.08s**. Menggunakan executable
  dump palsu, SQL/media fixture dan tar/gzip sebenarnya pada direktori sementara.
  Dari 16 bundle lama ditambah satu baru, tersisa 14 bundle valid; berkas situs lain
  tidak terhapus. Isi SQL/media, mode 0600, kegagalan dump, pembersihan parsial,
  penolakan lock paralel, dan unit/timer diperiksa.
- `pytest -q`: **145 passed, 9 skipped in 43.79s**, termasuk 17 kasus browser
  pada 375/768/1280 px. Log: `audit-evidence/B2-pytest.txt`.
- `bash -n deployment/backup.sh`, formatter/linter, penyiapan aset, dan
  `git diff --check`: lolos.
- `systemd-analyze calendar '*-*-* 03:15:00 Asia/Jakarta'` menerima jadwal dan
  menampilkan 03.15 WIB sebagai waktu berikutnya; tidak mengaktifkan timer.

Belum diverifikasi: dump dari MySQL nyata, aktivasi unit/timer, izin filesystem
VPS, salinan off-VPS, dan restore rehearsal. Backup online tetap best effort;
pair DB/media konsisten memerlukan penghentian seluruh penulis aplikasi saat
maintenance. Retensi 14 bundle tidak membuktikan jadwal berjalan atau restore berhasil.

## B3 — Rate limit lintas worker wajib saat deployment

Diubah: `deployment/rate-limits.conf.example`, `deployment/nginx.conf`, README,
dan `tests/test_deployment.py`. Zona shared memory ber-key IP hanya untuk POST
diwajibkan sebagai file HTTP-context baru. Contoh vhost langsung merujuk kedua
zona pada exact-location login dan inquiry, dengan respons 429; tidak lagi
bergantung pada penyalinan blok route yang dikomentari secara manual.

Checklist deployment mewajibkan pemasangan zona, validasi konfigurasi, pengujian
normal/excess POST dan GET, serta pemeriksaan pada dua worker Gunicorn. Header
proxy, timeout, dan pengecualian gzip tetap sama. Counter Flask-Limiter tetap
berlaku per worker sebagai lapisan tambahan; tidak ditambahkan Redis/service baru.
Dokumentasi menjelaskan burst/leaky bucket agar angka rate tidak disalahartikan
sebagai penghitung rolling-minute yang persis.

Bukti yang benar-benar dijalankan:

- `pytest tests/test_deployment.py -q`: **5 passed in 0.03s**.
- `pytest -q`: **146 passed, 9 skipped in 43.93s**, termasuk seluruh 17 kasus
  browser pada 375/768/1280 px. Log: `audit-evidence/B3-pytest.txt`.
- Test memastikan setiap referensi zona memiliki deklarasi, hanya POST mendapat
  key IP, kedua route memakai zona yang benar/429, dan semua lokasi privat tetap
  memakai gzip off serta directive proxy yang sama dengan route umum.
- Formatter/linter, penyiapan aset, dan `git diff --check`: lolos.

Belum diverifikasi: pemuatan konfigurasi dan pembatasan request pada Nginx nyata
karena executable Nginx tidak tersedia. Belum ada reload atau konfigurasi server
yang dipasang. Verifikasi staging tersebut tetap wajib sebelum deployment.

## B4 — JSON-LD jujur dan navigasi Testimoni

Diubah: `app/services/seo.py`, `app/services/content.py`,
`app/blueprints/public.py`, template `public/layout.html` dan `public/home.html`,
`app/static/js/app.js`, `tests/test_structured_data.py`, `tests/test_browser.py`,
README, dan VALIDATION.

Beranda mengeluarkan WebSite + Person dengan nama/origin CMS, sameAs hanya dari
sosial HTTPS terkonfigurasi, dan gambar profil/hero asli jika tersedia. Profil
demo atau nama kosong tidak menerbitkan identitas. Placeholder/gambar demo tidak
menjadi foto Person/Event. Recap hanya mengeluarkan Event bila terbit, bukan demo,
dan nama/tanggal/venue atau lokasi tersedia. Tanggal tidak diberi jam/zona waktu
buatan; alamat tetap teks yang diisi CMS. Tidak ada rating/review, penawaran,
status jadwal, end time, atau klaim performa tambahan. JSON diserialisasi dengan
Jinja `tojson`; CSP ketat tetap dipertahankan.

Menu Testimoni desktop/mobile mengikuti keberadaan testimoni terbit pada setiap
halaman publik. Beranda memakai hasil query yang sudah ada; halaman lain memakai
EXISTS pada kolom terindeks dan cache per request. Tidak ada counter lintas
request yang dapat menyembunyikan perubahan publikasi.

Bukti yang benar-benar dijalankan:

- `pytest tests/test_structured_data.py -q`: **22 passed in 3.84s**. Mencakup
  sumber data, origin, escaping payload penutup script, data demo/kosong,
  kelengkapan event, cover opsional, pembatasan ke halaman yang tepat, dan
  perubahan draft/terbit Testimoni pada enam halaman publik.
- Run awal seluruh suite: **1 failed, 170 passed, 9 skipped in 58.01s**.
  Browser 375 px menemukan tujuan anchor Testimoni tidak masuk viewport walau
  URL sudah benar. Handler penutupan drawer memanggil focus yang dapat menggulir
  kembali ke tombol header. Fokus kini dipulihkan dengan `preventScroll: true`.
  Assertion viewport tetap dipertahankan dan diperluas untuk klik dari halaman
  lain maupun fragment pada beranda sendiri. Log awal tidak disembunyikan:
  `audit-evidence/B4-pytest-initial.txt`.
- Setelah perbaikan dan perluasan kasus:
  `pytest tests/test_browser.py -q -k testimonial`:
  **3 passed, 17 deselected in 7.99s**.
- `pytest -q` final: **171 passed, 9 skipped in 56.09s**, termasuk seluruh
  **20 kasus Chromium** pada 375/768/1280 px. Log: `audit-evidence/B4-pytest.txt`.
  Kasus baru memeriksa klik menu, section terlihat, drawer tertutup, perubahan
  publikasi, tidak ada overflow, JSON dapat dibaca, dan tidak ada pelanggaran CSP.
- Formatter/linter, penyiapan aset, dan `git diff --check`: lolos.

Belum diverifikasi: validator/rich result Google terhadap domain dan konten
staging sebenarnya, serta bahasa/kebenaran informasi bebas yang kelak diisi CMS.
Test ini membuktikan struktur/escaping dan perilaku lokal, bukan jaminan hasil
pencarian atau sertifikasi aksesibilitas penuh.

## Penyerahan dan batas akhir

Empat item mempunyai empat commit lokal di `audit/batch-b`. Paket final memuat
source terbaru, bundle seluruh riwayat fase/Batch A/Batch B, kedua laporan audit,
log pengujian, dan bukti A1 yang tetap disimpan sebagai pembanding historis.
Tidak ada secret, database lokal, upload pemilik, atau virtualenv di paket.

Implementasi B1–B4 selesai. Verifikasi MySQL B1 masih **sebagian** karena sembilan
kasus nyata dilewati; konfigurasi uji telah disediakan. Pemeriksaan pemilik yang
tetap diperlukan: MySQL staging, Nginx dan unit/timer pada VPS, pengukuran RAM
PSS/cgroup, Lighthouse mobile dengan throttling, salinan off-VPS dan restore
rehearsal. Tidak ada server live, domain, database, Nginx/MySQL global, service,
atau job backup yang dipasang/diaktifkan selama pekerjaan ini.

## Status akhir

| Item | Status |
| --- | --- |
| B1 | sebagian: implementasi selesai; verifikasi MySQL belum dijalankan |
| B2 | selesai; rehearsal VPS belum dijalankan |
| B3 | selesai; uji Nginx staging belum dijalankan |
| B4 | selesai; validator domain staging belum dijalankan |
