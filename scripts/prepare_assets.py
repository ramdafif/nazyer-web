"""Version font filenames and local CSS dependencies without a bundler/minifier.

Run after changing fonts/images and before starting a release. --check never writes.
Only trusted, repository-owned static files are processed; uploads are unrelated.
"""

import argparse
import hashlib
import json
import posixpath
import re
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:10]


def logical_font(path):
    stem = re.sub(r"\.[a-f0-9]{10}$", "", path.stem)
    return path.with_name(stem + ".woff2")


def prepare(static_root, check=False):
    root = static_root.resolve()
    fonts, sources, copies = {}, {}, []
    for source in sorted((root / "fonts").glob("*.woff2")):
        # Unversioned files are editable source; hashed files are release outputs.
        if source.name != logical_font(source).name:
            continue
        logical = logical_font(source).relative_to(root).as_posix()
        target = source.with_name(logical_font(source).stem + "." + digest(source) + ".woff2")
        physical = target.relative_to(root).as_posix()
        if logical in fonts:
            raise RuntimeError(f"Multiple font versions found for {logical}")
        fonts[logical] = physical
        sources[physical] = source
        if not target.exists() or digest(target) != digest(source):
            copies.append((source, target))

    updates = []
    for css in sorted((root / "css").rglob("*.css")):
        original = css.read_text()

        def version_reference(match):
            quote, reference = match.groups()
            parts = urlsplit(reference)
            if parts.scheme or parts.netloc or not parts.path:
                return match.group()
            target = (css.parent / unquote(parts.path)).resolve()
            if not target.is_relative_to(root):
                raise RuntimeError(f"CSS reference escapes static root: {css}")
            relative = target.relative_to(root).as_posix()
            if target.suffix == ".woff2":
                logical = logical_font(target).relative_to(root).as_posix()
                relative = fonts[logical]
                target = sources[relative]
            if not target.is_file():
                raise RuntimeError(f"Missing local CSS asset: {relative}")
            path = posixpath.relpath(relative, css.parent.relative_to(root).as_posix())
            parameters = [(key, value) for key, value in parse_qsl(parts.query) if key != "v"]
            parameters.append(("v", digest(target)))
            value = urlunsplit(("", "", path, urlencode(parameters), parts.fragment))
            return f"url({quote}{value}{quote})"

        current = URL.sub(version_reference, original)
        if current != original:
            updates.append((css, current))

    manifest = root / "fonts" / "manifest.json"
    manifest_text = json.dumps(fonts, indent=2, sort_keys=True) + "\n"
    if not manifest.exists() or manifest.read_text() != manifest_text:
        updates.append((manifest, manifest_text))
    changed = [str(target.relative_to(root)) for _, target in copies]
    changed += [str(path.relative_to(root)) for path, _ in updates]
    if not check:
        for source, target in copies:
            target.write_bytes(source.read_bytes())
        for path, text in updates:
            path.write_text(text)
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    changed = prepare(ROOT / "app/static", check=args.check)
    if changed:
        print(
            ("Stale asset versions: " if args.check else "Prepared assets: ") + ", ".join(changed)
        )
    if args.check and changed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
