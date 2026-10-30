# DJ NAZYER — Official Website & CMS

Server-rendered artist portfolio and booking inquiry CMS. Flask 3, Python 3.12+, Jinja2, MySQL 8, vanilla CSS and JavaScript. No frontend build, Node runtime, Redis, Celery or paid service is needed.

All five implementation phases are recorded in [CHECKPOINTS.md](CHECKPOINTS.md). Actual verification and its limits are in [VALIDATION.md](VALIDATION.md). The supplied screenshot is **only** in `design/reference.png`, never a public photograph or background. Real media, statistics, prices and testimonials start empty.

## Local development

Use Python 3.12 or newer. The commands below assume Linux/macOS. Upload locking targets the production Linux environment.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.lock
cp .env.example .env
python -c 'import secrets; print(secrets.token_hex(32))'
```

Put the generated secret into `.env` as `SECRET_KEY`. Set `MEDIA_ROOT` to an absolute, writable directory **outside this checkout**, for example `/home/your-user/.local/share/dj-nazyer/uploads`. Keep `APP_ENV=development` and `DATABASE_URL=sqlite:///development.sqlite3` for an isolated local database. Never point development/test tools at another application's database.

```bash
flask --app wsgi db upgrade
flask --app wsgi create-admin
flask --app wsgi run
```

Open `http://127.0.0.1:5000` and `/admin/login`. The admin CLI prompts for a hidden, confirmed password of 12–128 characters; there is no default account/password and no public registration. A password change revokes all existing sessions for that admin.

Optional local preview: `flask --app wsgi seed-demo`. Every seeded record and abstract picture is marked DEMO. The command is idempotent and refuses production **before querying the database**. Use a separate local database and media directory for demo previews; never copy them into production. Reference photographs are never included in the seed.

## Managing content

1. **Settings:** site title/wordmark or logo, favicon, sharing image, description, WhatsApp, email and social HTTPS URLs. Unconfigured contacts/social links are hidden. WhatsApp accepts international digits; Indonesian `08…` is normalized to `628…` in generated links.
2. **Profil Artis:** hero headlines/description, hero/profile photographs, biography, genre, philosophy and verified career information. **Highlight Profil** manages label/value items; only the first three appear in the homepage strip.
3. **Kategori Galeri:** add Live Performance, Event Recap, Personal Photos and Behind the Scenes as needed. Categories contain no implied performance history. **Jenis Event** has activation and ordering; the first four active types appear on the homepage.
4. **Media Library:** upload original JPEG/PNG/WebP. Set alt text, caption and category. Publishing in the gallery and featuring in the homepage recap are separate switches. Choose existing media through CMS selectors. Library metadata changes do not regenerate images.
5. **Event & Recap:** save a draft, choose a cover/category, attach existing photos, or use “Upload Foto” with the event selected. Select multiple files with JavaScript enabled; the queue sends **one image per request** and reports each result. Select/reorder gallery photos with Naik/Turun, then save the event. Drafts return 404 publicly. Featured performances appear only when a featured event is published.
6. **Pricelist:** blank price means “Hubungi untuk Penawaran”; numeric prices render as IDR starting prices. One feature per line. Draft package preview is protected under `/admin`. The homepage shows at most three published packages, featured first. Package buttons prefill WhatsApp messages, or lead to the inquiry form with the package selected if WhatsApp is not configured.
7. **Testimoni:** add only authentic quotes and names. Rating is optional and never inferred. The homepage hides the section when no testimonial is published; no rating/review structured data is emitted.
8. **Booking Inquiry:** new submissions start as `baru`. Update to dihubungi, negosiasi, terkonfirmasi or ditutup and add private notes. **An inquiry is not a confirmed booking.** All deletion actions have a separate confirmation form. Media in use cannot be deleted; remove its references first.

Media rules: max. 8 MB/file, 8 million pixels, 6000 px on the longest side, min. 32 px each side. Animated images, GIF, SVG, mismatched formats and corrupt files are refused. Original files are discarded. Three metadata-free WebP variants (up to 1600/640/320 px) are created once. A cross-process file lock allows only one Pillow decode at a time; a simultaneous upload can ask the user to retry. The lock file is not publicly served. Files must never be placed manually in the public uploads directory unless they are intended as public assets.

The public footer and 404 page include “All rights reserved.” and “Developed by
Elkyno Technology”. The copyright year follows the current year and the public
footer retains the configured artist name. Credits are readable text rather than
an extra call to action.

Owner-supplied mascots appear in the shared booking CTA and the dedicated 404
layout. Their transparent WebP variants use explicit dimensions, responsive
`srcset` and versioned static URLs; the below-fold CTA illustration is lazy-loaded.
Original drawings and preparation notes are retained under `design/mascots`,
outside the public static directory. No image transformation runs per request.

## Structured data and testimonial navigation

The homepage emits minimal `WebSite` and `Person` JSON-LD using the configured
site/profile names and canonical origin. `sameAs` contains only configured valid
HTTPS social URLs; images come only from actual configured profile/hero media.
Empty identity, demo profiles and demo/placeholder images are omitted. Other
public pages and the CMS do not inherit the homepage's identity block.

A published, non-demo recap emits `Event` only when its name, date and venue or
location are available. The date uses `YYYY-MM-DD`, since the CMS has no start
time. Location stays the entered venue/free-text address; no street, city, end
time, schedule status, ticket offer, rating or review is invented. Cover image and
description are included only when present. JSON is serialized with Jinja's
HTML-safe `tojson`; the existing strict CSP is retained.

Desktop/mobile Testimoni links appear only while at least one testimonial is
published, on every public page, and lead to the real homepage section. Publication
changes are reflected on the next request without a persistent cached counter.

References: [WebSite](https://schema.org/WebSite), [Person](https://schema.org/Person),
[Event](https://schema.org/Event), and
[Google event guidance](https://developers.google.com/search/docs/appearance/structured-data/event).
Schema.org data does not promise search rich results; validate the actual staging
content after entering verified information, without inventing missing fields to
satisfy a search feature.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | `development`, `testing`, `production` |
| `SECRET_KEY` | Required in production, at least 32 random characters; keep stable across workers/restarts |
| `DATABASE_URL` | Production: `mysql+pymysql://nazyer_app:ENCODED_PASSWORD@127.0.0.1:3306/dj_nazyer?charset=utf8mb4` |
| `MEDIA_ROOT` | Absolute persistent path outside the checkout |
| `PUBLIC_BASE_URL` | Canonical origin; use `https://dj.example.com` in production |
| `TRUSTED_HOSTS` | Comma-separated exact host names; required in production |
| `PROXY_HOPS` | `1` behind the supplied Nginx proxy, otherwise `0`; the app does not trust forwarded host headers |

URL-encode special characters in the database password. SQL parameters are hidden from SQLAlchemy error output. No server credentials are editable or exposed in the CMS. Use `.env` only for local development; systemd reads `/etc/dj-nazyer.env` directly in production.

## Production deployment — prepare and run manually

These are examples, not an automated deployment. They have **not** been applied to a live server. Select a unique domain and paths and inspect existing Nginx/systemd configuration before installing new files. No command below requires changing another application's MySQL database or global MySQL configuration.

Prerequisites: Nginx, MySQL 8 and an independently installed Python 3.12+ interpreter. On Ubuntu 22.04, do not replace the OS Python or the interpreters used by existing services. This guide assumes `python3.12` is already available. The app can also run on Ubuntu 24.04 with its Python 3.12.

Create a dedicated Linux user `nazyer` and directories `/srv/dj-nazyer/current`, `/srv/dj-nazyer/venv`, `/var/lib/dj-nazyer/uploads`. Put the source checkout under `current`. The `nazyer` user and Nginx's `www-data` group need to traverse the static/media paths; only `nazyer` needs write access to media. Suggested media ownership is `nazyer:www-data`, directory mode `2750` and files `0640`. Never make the entire checkout world-writable.

Create **only this schema and its dedicated MySQL user** using [deployment/mysql-setup.sql.example](deployment/mysql-setup.sql.example), replacing its password first in a private session. Do not use root in `DATABASE_URL`. The privileges are scoped to `dj_nazyer.*` and cover Alembic migrations. No `FLUSH PRIVILEGES`, global tuning, or changes to other databases are needed. If the schema/user already exist, inspect them rather than blindly recreating them.

```bash
python3.12 -m venv /srv/dj-nazyer/venv
/srv/dj-nazyer/venv/bin/pip install -r /srv/dj-nazyer/current/requirements.lock
```

Create `/etc/dj-nazyer.env` from `.env.example` with the production values above; protect it as `root:nazyer`, mode `0640`. From `current`, the Flask CLI can read that file as the dedicated application user without putting secrets in arguments or sourcing it as shell code:

```bash
sudo -u nazyer /srv/dj-nazyer/venv/bin/flask --env-file /etc/dj-nazyer.env --app wsgi db upgrade
sudo -u nazyer /srv/dj-nazyer/venv/bin/flask --env-file /etc/dj-nazyer.env --app wsgi create-admin
```

Use migrations for all schema changes; never `db.create_all()` in production. All tables explicitly use InnoDB/utf8mb4. Pool settings are 2 connections plus 2 overflow per worker, pre-ping, recycle 1800 s. Times are stored in UTC and displayed as Asia/Jakarta.

Install [deployment/dj-nazyer.service](deployment/dj-nazyer.service) as a **new** systemd unit and verify its paths. It runs two sync Gunicorn workers with preloading, request recycling and a unix socket. `ProtectSystem` and write-path restrictions keep source read-only. The optional memory ceiling is commented out until actual VPS measurements are available.

Code updates require **`systemctl restart dj-nazyer`**. With `preload_app=True`,
the master has already imported the application; a worker HUP/reload is not the
code-deployment path. The example unit deliberately has no `ExecReload` shortcut.
Preloading remains enabled for memory sharing. An Nginx reload after validating
its configuration is a separate operation and does not update Python code.

Install [deployment/nginx-static-cache.conf.example](deployment/nginx-static-cache.conf.example)
as a **new** `/etc/nginx/conf.d/dj-nazyer-static-cache.conf` in the existing `http {}`
context. Its uniquely named map is required by this site's cache policy; do not
replace the existing `nginx.conf`.

Install [deployment/nginx-log-format.conf.example](deployment/nginx-log-format.conf.example)
as a separate **new** `/etc/nginx/conf.d/dj-nazyer-log-format.conf` in the same
`http {}` context. Create `/var/log/nginx/dj-nazyer` for this site's log, with
restricted ownership/permissions appropriate for the Nginx master (for example,
`root:adm`, directory `0750`, log `0640` on Ubuntu). Do not overwrite existing
log formats, virtual hosts, or other sites' log files.

Install [deployment/nginx.conf](deployment/nginx.conf) as a **new virtual host**, replace `dj.example.com`, then validate and reload:

Complete the required shared rate-limit checklist below **before** loading this
vhost; its exact login/contact locations reference the HTTP-context zones.

```bash
sudo nginx -t
sudo systemctl daemon-reload
sudo systemctl enable --now dj-nazyer
sudo systemctl reload nginx
```

The supplied host listens on HTTP only for certificate bootstrap. After DNS points at the VPS, run Certbot for **this domain** (`sudo certbot --nginx -d dj.example.com`), inspect the resulting HTTPS block and verify renewals. Secure production cookies make admin/form use over HTTP unsuitable. Keep port 80 for HTTPS redirects/ACME only after setup. The application socket is never exposed publicly. Nginx serves `/static` and UUID-named `/uploads` directly; Flask deliberately refuses those files in production.

All template asset URLs use `asset_url(filename)` with `?v=` plus the first ten
hex characters of the file's SHA-256. Hashes are computed once at application
startup and cached in memory, even with `static_folder=None`. Restart the service
when switching releases. Versioned assets cache for one year with `immutable`;
unversioned URLs must revalidate. Fonts have content-hashed filenames and a
30-day cache. UUID-named media variants cache for one year. Only `add_header`
generates Cache-Control; `expires off` prevents duplicate generated headers.
Form/admin responses retain `no-store`.

The example enables gzip for public HTML and the listed CSS, JavaScript, SVG and
XML types. If an equivalent global gzip configuration already exists, inherit it
instead of duplicating the site policy. Admin/contact responses that contain
session/CSRF information keep `gzip off`, including the rate-limited exact
locations in the vhost. No minification step is used.

### Site access logs and privacy

`nazyer_safe` writes only the remote IP, ISO timestamp, method, `$uri` path,
status, bytes and user agent to `/var/log/nginx/dj-nazyer/access.log`. It does not
record the request query string, form body, cookies, credentials or referrer.
`escape=json` protects the log structure from quotes/control characters in user
agents. Logs contain visitor IP addresses and user agents: **treat them as
personal data**, restrict access and avoid copying them into public reports.

Use a maximum **14-day total** retention policy. The separate
[deployment/dj-nazyer-logrotate.conf.example](deployment/dj-nazyer-logrotate.conf.example)
keeps 13 daily archives plus the active daily file (`rotate 13`, `maxage 13`),
compresses archives, rotates even empty files so aging continues, and reopens the
Nginx log after rotation. Review it as a new `/etc/logrotate.d/dj-nazyer` entry;
the host's daily logrotate schedule must already work. Check for overlapping
rules before installation. No rotation job or server configuration is activated
by this repository. Rehearse rotation and confirm actual retention on staging.

Nginx directive references: [headers/cache](https://nginx.org/en/docs/http/ngx_http_headers_module.html),
[access logs](https://nginx.org/en/docs/http/ngx_http_log_module.html), and
[gzip](https://nginx.org/en/docs/http/ngx_http_gzip_module.html).

After editing a font or an image referenced from CSS, run
`python scripts/prepare_assets.py` and commit the generated font copies, manifest and
updated CSS references. It adds matching versions to local CSS dependencies,
including abstract backgrounds, so an image/font change also changes its parent
CSS hash. Font preloads and CSS refer to the same versioned URL. Before tests or
deployment, run `python scripts/prepare_assets.py --check`; a stale reference fails
the check. This is a Python preparation step, not a bundler or minifier, and it is
never run as a production request handler. Edit the unversioned font source;
templates/CSS link only to the generated hashed copy. Startup rejects a stale
font manifest/source mismatch. Older hashed files can remain available for
visitors with a cached previous release.

### Required shared rate-limit deployment checklist

**In-memory Flask-Limiter counters are per worker and reset on restart.** Two
workers do not share an application counter. The uniquely named Nginx shared
memory zones are a **required deployment layer**, without Redis or a new service.

- [ ] Review [deployment/rate-limits.conf.example](deployment/rate-limits.conf.example)
  and install it as a **new** `/etc/nginx/conf.d/dj-nazyer-rate-limits.conf` in the
  existing `http {}` context. Never overwrite the main Nginx configuration.
- [ ] Use this site's reviewed vhost with the exact `/admin/login` and `/kontak`
  locations. They reference `nazyer_login` (5 requests/minute, burst 3) and
  `nazyer_inquiry` (3/minute, burst 2), returning 429 for excess POST requests.
  These use Nginx's leaky-bucket policy, not an exact rolling-minute counter.
  GET/HEAD use an empty key and are not counted by these zones.
- [ ] Keep the same unix-socket proxy headers/timeouts and `gzip off` in these
  exact locations. Nginx must overwrite forwarded headers with its observed
  client address/protocol; do not trust arbitrary incoming forwarded values.
- [ ] Run `nginx -t` on staging before reload. Confirm the zones are loaded once,
  normal login/inquiry submissions work, repeated POSTs receive 429, and GET
  pages still load. Test with the real two-worker Gunicorn configuration and
  inspect the safe access log. Only then apply the reviewed vhost to this site.

These checks are mandatory for deployment acceptance; they have not been run
against a live Nginx instance here. Application rate limiting remains enabled as
an additional layer. All changes in this repository are examples for review.
See the [Nginx limit_req reference](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
for shared-zone, empty-key and burst semantics.

## Updating the application

Back up this database and media first. Prepare dependencies/source in a new release directory, review migrations, run tests on an isolated staging database, then switch `current` and restart **only `dj-nazyer`**. Run forward migrations using the new source. Do not downgrade database schema without reviewing the specific migration and restore plan. Existing uploads remain in `/var/lib/dj-nazyer/uploads`; replacing code does not replace media.

```bash
sudo systemctl restart dj-nazyer
sudo systemctl status dj-nazyer
sudo journalctl -u dj-nazyer --since '10 minutes ago'
```

## Backup and restore

[deployment/backup.sh](deployment/backup.sh) dumps only `dj_nazyer` and archives
`uploads`. It uses an owner-readable MySQL client option file (`0600`), so passwords
are not passed on the command line. Use a dedicated account with access only to
this schema. The script skips routines/events/triggers because this application
creates none, and disables GTID-purged statements so a restore does not set global
GTID state. It does not stop the app or any other service.

A lock prevents concurrent manual/scheduled backups. A failed dump/archive leaves
previous backups intact. After successfully publishing one complete bundle
atomically, the script retains the **14 latest timestamped bundles**; unrelated
files and partial archives are not pruned. Output files use `0600`. Retention is
14 backups, not necessarily 14 days if extra manual backups are made.

### Daily backup example — enable only after staging review

Review the new [backup service](deployment/dj-nazyer-backup.service),
[timer](deployment/dj-nazyer-backup.timer), and
[environment example](deployment/backup.env.example). Install them manually under
new names; do not replace any existing server backup job. The timer targets
**03:15 Asia/Jakarta daily**, with up to five minutes of jitter. `Persistent=true`
can catch up a missed run after boot, outside the quiet window; change that policy
if this is unsuitable for the host. No unit/timer is installed or enabled here.

Before activation, create `/var/backups/dj-nazyer` owned by `nazyer` with mode
`0700`. The service runs as `nazyer` with only that directory writable. Store
`/etc/dj-nazyer-backup.env` as `root:nazyer`, mode `0640`, and the separate
`/etc/dj-nazyer-backup.cnf` as `nazyer:nazyer`, mode `0600`. The option file needs a
`[client]` section containing the selected local host, dedicated user and password;
create it privately, never commit it. Adjust the service sandbox if the chosen
backup output directory differs. `NAZYER_MEDIA_PARENT` defaults to
`/var/lib/dj-nazyer`; its `uploads` child is included read-only.

Validate paths/permissions and unit syntax on staging, run a manual backup there,
inspect its archive and rehearse restore before choosing to enable the timer.
Monitor the timer/service status, exit code, free space and backup freshness through
the host's existing monitoring process. Retention alone does not prove backups run.

### Online versus offline consistency

| Mode | Behavior and trade-off |
| --- | --- |
| Online (timer default) | No downtime. `--single-transaction` snapshots InnoDB, but the media archive is taken later. Concurrent uploads/deletions or schema changes can make the DB/media pair inconsistent or make archiving fail. Suitable as a best-effort daily copy, with restore validation; avoid migrations during backup. |
| Offline maintenance | Stop **only `dj-nazyer`** and ensure no CLI/import job writes this schema/media, then run the backup. This provides a stable DB/media pair but causes a short outage. Restart the app after success or failure. Other applications, MySQL and Nginx remain running. |

Copy successful bundles off the VPS through the **existing secure backup process**;
this repository adds no destination, credentials or transfer daemon. Apply access
controls/encryption and a separately reviewed retention policy at that destination.
A local backup cannot protect against loss of the VPS. Backups contain personal
inquiry data; do not publish them or put them in the source repository.

### Restore rehearsal checklist — isolated target only

- Select a local/off-VPS bundle, verify its transfer checksum and archive integrity,
  then inspect the nested `dj_nazyer.sql.gz` and `media.tar.gz` contents.
- Provision an empty dedicated restore schema and separate media directory, with a
  user scoped only to that schema. Never restore into another app's database/media.
- Import the SQL into that explicitly selected schema and unpack `uploads` into the
  isolated media parent. Restore `nazyer:www-data` ownership, directory/file modes,
  and verify the saved Alembic revision against the matching application release.
- Run the matching release on an isolated origin. Verify admin login, event/draft
  visibility, package/settings values, inquiry records, and DB-referenced images
  (including all WebP variants). Check for missing files and compare record counts.
- Record backup age, measured restore time, integrity results and any missing data;
  have the owner accept the recovery result before declaring the backup usable.
  Remove the isolated restored personal data securely after the rehearsal.

For a real recovery, keep this app stopped during import/media restore and verify
the same checks before restarting only its service. Do not treat an untested
backup file as a proven restore.

## Verification

Development formatting uses only Python tools: Ruff, djLint, cssbeautifier and
jsbeautifier. After activating the development virtualenv, run
`bash scripts/format.sh` to format or `bash scripts/format.sh --check` to check
without writing. Ruff enforces a 100-character Python line limit. No minifier or
Node-based formatter is involved.

For a formatting-only regression audit, `scripts/audit_format.py` captures all
HTML view variants against its own SQLite demo fixture and compares normalized
HTML plus exact screenshot pixels. Its state/output paths must be outside the
checkout. It fixes the audit clock/CSRF token and reuses the same fixture between
captures; no environment database credentials are read. Whitespace-sensitive
`.prose`, `pre`, `code` and `textarea` text remains exact during comparison.

```bash
pip install -r requirements-dev.lock
playwright install chromium --only-shell
pytest -q --browser chromium
flask --app wsgi db check
python scripts/measure_memory.py
```

Default tests migrate fresh SQLite databases; they do not create or modify production data. Browser tests run a short-lived local pytest server and exercise 375/768/1280 px viewports with real CSRF. Test media and accounts are isolated temporary files, never release assets. Dev-only Playwright uses Node internally; **Node is not an application/server runtime requirement**.

### Opt-in MySQL integration tests

`tests/test_mysql.py` is marked `mysql` and skips unless `MYSQL_TEST_URL` is set.
Manually provision an **empty, disposable MySQL 8 database** with `utf8mb4`, named
for example `dj_nazyer_test`, and a non-root user granted access only to that
database. Do not use staging application data or production credentials. The URL
must use `mysql+pymysql://`; its schema name must contain a separate `test` segment
(`dj_nazyer_test` or `test_dj_nazyer`, not `contest`). Passwords must be URL-encoded.

The suite refuses existing tables/views before migrating. It upgrades and
downgrades the schema, then removes only the Alembic bookkeeping table it created.
It also tests unique slugs, emoji, literal LIKE searches (`%`, `_`, `/`, `\\`),
year boundaries/draft visibility, and two independent upload processes sharing
the same media directory. Do not run two test suites against the same test schema.

Enter the isolated test URL privately so it does not enter shell history:

```bash
read -r -s -p 'MYSQL_TEST_URL for empty disposable schema: ' MYSQL_TEST_URL
export MYSQL_TEST_URL
pytest -q -m mysql
unset MYSQL_TEST_URL
```

An explicitly configured but unsafe/unreachable target fails; it is not silently
skipped. With no URL, report the MySQL cases as **skipped**, not passed. The separate
SQLite process-harness and URL-guard checks do not establish MySQL compatibility.

`measure_memory.py` starts two temporary Gunicorn workers with the deployment settings, an isolated SQLite DB and a loopback transport override. On a real Linux host it samples combined PSS/RSS from `/proc`; restricted runtimes fall back to conservative per-process peak RSS. Re-run on the VPS with its actual deployment and traffic before asserting the ±150 MB target. MySQL, Nginx, HTTPS and actual-user Core Web Vitals still require deployment-specific verification.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Startup refuses production | Secret length, HTTPS canonical origin, trusted hosts, dedicated MySQL credentials and external media path |
| Database access denied | Match `127.0.0.1` in the user grant and URL, URL-encode the password, verify schema-specific grants |
| 502 from Nginx | This service's status/logs, unix socket path and `www-data` permissions |
| Static/media 404 in production | Nginx aliases and exact source/media paths; Flask intentionally does not serve them |
| Login/form returns 400 | Reload for a fresh CSRF token; verify HTTPS, stable shared secret and `PROXY_HOPS=1` |
| Login succeeds then disappears | All workers must use the same secret; check secure cookies and HTTPS |
| Upload refused | File content/type, 8 MB/8 MP/6000 px limits, free disk space, media permissions, concurrent processing lock |
| 429 | Allow rate counters to expire; check the per-worker/Nginx policy rather than disabling it |
| Cannot delete media/category | Remove references first; database FK restrictions are intentional |

## Source structure and history

`app/blueprints`, `forms`, `models`, `services`, `templates`, and `static` hold application code. `migrations`, `tests`, `deployment` and `scripts` are separate. Secrets, local DBs, uploads, test screenshots and virtual environments are ignored. `design/reference.png` is design documentation only.

The release ZIP includes `git-history.bundle` with the original phase commits,
one commit per audit item and the footer/mascot update. Optional history inspection
from the unpacked release:
`git clone -b ui/footer-mascots git-history.bundle dj-nazyer-history`.
This selects the latest UI branch; the audit branches remain available and `main`
retains the Phase 5 baseline.
The code itself can be used directly without restoring Git history.

Third-party asset notices are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Fonts and SVGs are self-hosted; no CDN is contacted by the application.
