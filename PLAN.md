# DJ NAZYER implementation plan

The workspace was empty. This project uses Flask/Jinja2, vanilla CSS/JS and MySQL on a VPS. It is prepared locally, not deployed to live infrastructure. The final user instruction overrides intermediate stop checkpoints: run tests and commit each phase, then continue automatically.

## Architecture

- Application factory, dev/test/production environment validation, thin public/auth/admin blueprints.
- SQLAlchemy models with UTC timestamps, explicit relationships and deletion restrictions; Alembic migrations are the only schema bootstrap path.
- Services for content queries, safe URLs, uploads and deletion, inquiry transitions and demo data.
- Reusable Jinja components; self-hosted fonts and SVG icons; progressive enhancement without a bundler.
- Files in persistent external media storage; Nginx handles production static/media. No deployment execution.

## Models

AdminUser, ArtistProfile, ProfileHighlight, ServiceType, EventCategory, Event, MediaAsset, EventMedia, GalleryCategory, PricingPackage, PricingFeature, Testimonial, BookingInquiry, SiteSetting. All include created_at and updated_at. Content tables have is_demo flags. Media references use RESTRICT; dependent features/highlights/event links cascade.

## Sequence and checkpoints

1. Foundation: config, dependencies, all models, initial migration, auth and create-admin, base assets. Test and commit.
2. Public UI: Black × Dark Purple system and reference composition, responsive routes and empty states. Test and commit.
3. Admin CMS: protected dashboard, all management forms and media processing. Test and commit.
4. Integration: public content queries, inquiry submission, packages/WhatsApp, lifecycle and safety tests. Test and commit.
5. Production readiness: security/SEO, Playwright at 375/768/1280, memory measurement, deployment examples, documentation, full tests. Commit and package.

## Evidence policy

No fictional credentials, prices, reviews, statistics or performances in production. Reference photographs are never public assets. Empty content has deliberate placeholders. Demo seed is explicitly marked and blocked in production. Measurements and unavailable checks are reported honestly.
