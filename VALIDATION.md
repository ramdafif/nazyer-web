# Verification record — 29 October 2026

The implementation of all five phases is complete. This record distinguishes code/local verification from deployment-specific acceptance. No live VPS, existing database, Nginx configuration or domain was changed.

## Footer and mascots — latest local verification

Public pages and the 404 page now show the requested rights/developer credit.
The booking CTA uses the owner's casual-cap mascot; the 404 layout uses the
wizard-hat mascot. Both retain the original transparency and use static WebP
variants (19,902–60,680 bytes/file), responsive sources and explicit dimensions.
Mobile layouts keep the copy/buttons clear of the artwork. No database schema,
booking behavior, server or deployment configuration changed.

- Final `pytest -q`: **171 passed, 9 skipped in 148.20 s**, including all 20
  Chromium cases at 375/768/1280 px. The existing public browser cases now also
  check credits, the real 404 response, lazy-loaded image requests and working
  navigation from 404 to home and from the booking CTA to the contact form.
- Nine internal visual captures cover booking CTA, footer and 404 at all three
  widths; all layouts were inspected. The 404 overflow/status checks passed.
- `bash scripts/format.sh --check`, `python scripts/prepare_assets.py --check`,
  and `git diff --check` passed.
- An early browser run had 3 failures from an ambiguous test selector matching
  both the SVG icon and mascot; the selector now targets the illustration.
  After an environment restart, an initial full run reported 151 passed, 9 skipped
  and 20 setup errors because Chromium was missing. The browser was reinstalled
  and the full suite above was run successfully; the initial log is retained as
  `audit-evidence/UI-pytest-browser-unavailable.txt`.

The final log is `audit-evidence/UI-pytest.txt`. The nine MySQL cases remain
explicitly skipped because no isolated `MYSQL_TEST_URL` is configured. VPS/Nginx,
real backup/restore, memory and Lighthouse acceptance remain outstanding.
This update is committed locally on `ui/footer-mascots`; nothing was pushed or
deployed. Original drawings are under `design/mascots`; no new browser screenshots
are included in the release archive.

## Audit Batch B — previous local verification

All four Batch B implementations are complete on local branch `audit/batch-b`,
with one commit per item. See [AUDIT_BATCH_B.md](AUDIT_BATCH_B.md) for exact changes,
commands, the initial B4 browser failure/fix and outstanding deployment checks.

| Item | Full `pytest -q` result |
| --- | --- |
| B1 — opt-in MySQL tests | 140 passed, 9 skipped in 43.29 s |
| B2 — scheduled backup examples | 145 passed, 9 skipped in 43.79 s |
| B3 — required shared rate limits | 146 passed, 9 skipped in 43.93 s |
| B4 — truthful JSON-LD and testimonial navigation | **171 passed, 9 skipped in 56.09 s** |

B1–B3 include all 17 existing Chromium browser cases; the final B4 run includes
20 cases covering 375/768/1280 px. Nine MySQL tests are explicitly skipped because
`MYSQL_TEST_URL` is unset and no MySQL server is available. The SQLite process
harness does not establish MySQL compatibility. Backup tests used a fake dump
command with real tar/gzip and temporary files; no real database backup/restore
or timer activation occurred. Nginx runtime/rate enforcement, VPS memory,
Lighthouse and restore rehearsal remain unverified. No remote push or live server
change was made. The release includes the Batch A evidence, four Batch B final
pytest logs and the initial B4 failure log.

## Audit Batch A — previous local verification

Batch A is complete on the local `audit/batch-a` branch, with one commit per
item and no remote push or live server changes. See [AUDIT_BATCH_A.md](AUDIT_BATCH_A.md)
for per-item changes, exact commands, limitations and the screenshot comparison.

| Item | Full `pytest -q` result |
| --- | --- |
| A1 — formatting | 94 passed in 43.35 s |
| A2 — static asset versions | 112 passed in 37.95 s |
| A3 — formal Indonesian copy | 129 passed in 40.26 s |
| A4 — restart guidance | 130 passed in 39.45 s |
| A5 — safe logging and gzip examples | **133 passed in 41.36 s** |

Each run includes all 17 Chromium browser cases at 375/768/1280 px. A1 also
compared 58 normalized demo renders and 12 before/after full-page screenshot
pairs: no normalized HTML differences and zero changed pixels in every pair.
The release includes these explicitly requested demo-only screenshots and HTML
captures under `audit-evidence/`, plus the five pytest logs.

Nginx and logrotate are unavailable here: actual configuration loading, response
headers and log rotation were not tested. No unit was installed or restarted.
The deployment acceptance checks below remain outstanding; Batch B changes and
their verification are recorded above.

## Phase 5 executed checks — historical baseline

| Check | Actual result |
| --- | --- |
| `pytest -q --browser chromium` | **94 passed in 35.26 s**, no warnings |
| Application/security/integration cases | 77 passed, isolated SQLite databases migrated by Alembic |
| pytest-playwright browser cases | 17 passed, Chromium 141 headless, viewports 375/768/1280 px |
| `pip check` | No broken requirements |
| `flask --app wsgi db check` | No new upgrade operations detected |
| MySQL table/migration compilation | InnoDB/utf8mb4 DDL and offline Alembic SQL compiled; **no real MySQL integration run** |
| `bash -n deployment/backup.sh` | Syntax passed; no production backup/restore performed |
| Gunicorn measurement harness | Two preloaded sync workers started and handled public/CMS requests and concurrent uploads over local TCP |
| Visual QA | Desktop homepage render inspected; empty and populated layouts, no overflow, real asset requests, keyboard/lightbox/navigation/form behavior checked |

Coverage includes login/logout, password hashing/session revocation, anonymous admin protection, valid/invalid CSRF, event and package CRUD, draft protection, gallery/category filtering, safe upload rejection, EXIF removal, media FK restrictions, package WhatsApp messages, real settings/media references, testimonials with optional rating, service activation, inquiry validation/honeypot/follow-up, error responses, production configuration guardrails, read-only source deployment and production demo refusal. Browser checks also cover empty/populated CMS states, native dialog Escape/focus/keyboard controls, JavaScript-free navigation, reduced motion and basic accessibility semantics. This is not a full WCAG certification.

## Performance samples

Measured using `python scripts/measure_web.py`. See `PERFORMANCE_REPORT.json` for the exact environment.

| Width | Local FCP | Local LCP | Local CLS |
| --- | --- | --- | --- |
| 375 px | 212 ms | 212 ms | 0.002 |
| 768 px | 88 ms | 88 ms | 0.002 |
| 1280 px | 132 ms | 132 ms | 0.001 |

These are cold browser-context samples against an empty local CMS, without network/CPU throttling or HTTPS. They are not production Core Web Vitals or Lighthouse scores. Real photographs, hosting latency and visitors' devices change the outcome. Lighthouse and field INP were **not measured**.

## Memory budget — not verified

`python scripts/measure_memory.py` exercised the actual Gunicorn worker settings with a throwaway SQLite database. Unix sockets are not permitted in this validation environment, so the harness overrides transport with loopback TCP; production configuration remains a unix socket.

The environment also hides `/proc` process memory data. Consequently **PSS could not be measured**. The fallback sums per-process `getrusage` peak RSS values, double-counting shared preloaded pages and combining peaks that need not occur simultaneously:

- Public warm-path peak RSS sum: 204.11 MiB.
- After CMS requests: 220.73 MiB.
- Peak RSS sum including uploads: **292.94 MiB**.
- Two concurrent 7.2 MP uploads returned 302 (saved) and 422 (processing slot busy), demonstrating cross-worker serialization and the retry state.

These numbers do **not** establish physical memory usage below ±150 MB. That acceptance criterion remains unverified. Re-run the supplied profiler on the actual VPS with MySQL, Nginx, representative images and traffic, and inspect the systemd cgroup/PSS before setting a memory ceiling or asserting capacity. No memory target is advertised as achieved.

## Deployment checks still required

- Apply migrations to an isolated MySQL 8 staging schema and exercise permissions, transactions and charset with the real driver/server.
- Review the new virtual host/service paths, run `nginx -t` and validate the unix socket and filesystem permissions on Ubuntu.
- Obtain HTTPS for the selected domain, test secure cookies/CSRF through Nginx and verify certificate renewal.
- Run a protected backup and restore rehearsal for this database and media.
- Measure real server RAM, Lighthouse and field performance after actual content is installed.

The managed preview service does not execute this Python checkout. All reported browser results came from the requested isolated pytest-playwright harness; no hosted URL or deployment success is claimed.

## Delivery contents

Source, migration, self-hosted fonts/icons and notices, reference design, tests,
dependency locks, deployment examples, backup script, measurement scripts/reports,
phase/audit Git history and the requested A1 demo comparison evidence. No `.env`,
passwords from a real system, local database, user upload folder or virtualenv are
included in the release ZIP. Test credentials in test source are exclusively for
temporary test databases and do not bootstrap any production account.
