# Implementation checkpoints

## Phase 1 — Foundation

- Initialized the previously empty workspace, wrote PLAN.md and preserved the reference in design/reference.png.
- Added factory/configuration, 14 timestamped models, initial Alembic migration, auth, password session revocation, CLI admin creation, base CSS and error handlers.
- Actually ran: migration generation, `flask db upgrade`, `pytest -q`.
- Result: **7 passed** (SQLite isolated databases). MySQL not yet exercised. Public UI/CMS CRUD belong to later phases.

The user explicitly requested continuing through all phases; no intermediate approval stop applies.

## Phase 2 — Public UI

- Added all public pages, intentional empty states, database-driven homepage, draft protection, filters/pagination and booking form rendering.
- Built Black × Dark Purple CSS, responsive navigation drawer, native-dialog lightbox with keyboard/swipe support and reduced-motion behavior.
- Actually ran `pytest -q`: **15 passed**. `flask db check`: no schema drift. `pip check`: no broken requirements.
- Browser and detailed CMS/inquiry integration checks are scheduled for subsequent phases.

## Phase 3 — Admin CMS

- Added protected dashboard metrics, content CRUD, media library, safe WebP uploads, event galleries and ordering, package preview, profile/highlights, categories/services, testimonials, settings and inquiry follow-up.
- Fixed failures discovered by tests: date validator type and wildcard route shadowing GET logout.
- Actually ran `pytest -q`: **35 passed** after corrections. Production MySQL and browser verification remain outstanding.
- Managed live preview cannot execute this Python checkout; it does not share the Python runtime. This does not change the required Flask deployment architecture.

## Phase 4 — Integration

- Verified actual event/gallery ordering, public filtering, package CTA prefill, inquiry persistence/follow-up, profile/highlight rendering, testimonial behavior and safe media reuse/deletion.
- Added explicit demo seeding with abstract assets and is_demo flags; production refuses the command. Seed is repeatable.
- Added active CSRF-token submission tests, which exposed the current Flask-WTF requirement for an integer timeout; corrected the configuration to 7200 seconds.
- Actually ran `pytest -q`: **57 passed**. Unsafe/mismatched/corrupt uploads, EXIF, dimension limits, FK protections and honeypot are covered.
- Chromium headless shell became available after selecting a working dev-only Playwright release. Full viewport tests follow in Phase 5.

## Phase 5 — Production preparation and final verification

- Added SEO sitemap/robots/canonical/Open Graph, local sharing PNG, safe caching, hardened production configuration, explicit InnoDB/utf8mb4 tables and Indonesian form messages.
- Added two-worker Gunicorn/unix-socket, separate Nginx and systemd examples, optional shared Nginx rate limits, isolated MySQL setup example, backup procedure/script and complete installation/update/restore documentation.
- Actually ran the full suite: **94 passed in 35.26 s**, including **17 Playwright cases** at 375/768/1280 px. No warnings. `pip check`, migration drift check and backup shell syntax check passed.
- Executed local paint/shift measurements and two-worker upload/memory harness. **The ±150 MB physical memory budget remains unverified**: PSS is unavailable here; conservative per-process peak RSS sum was 292.94 MiB. MySQL server, Nginx/HTTPS, live unix socket and restore execution remain deployment-specific checks.
- Fixed and regression-tested production startup with a read-only checkout: the app no longer creates a local instance directory in production.
- See VALIDATION.md for the exact results and limitations. No live server was touched. All phases are implemented; production acceptance is not represented as completed.

## Phase commits

1. `9c8e20b` — Foundation.
2. `06f43a5` — Public UI.
3. `b3b775f` — Admin CMS.
4. `7afc762` — Integration.
5. Final production-preparation commit is included in `git-history.bundle`.
