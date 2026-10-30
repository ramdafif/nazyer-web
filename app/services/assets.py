"""Startup-only content versions for self-hosted static assets."""

import hashlib
import json
from pathlib import Path
from types import MappingProxyType

from flask import url_for


def register_assets(app):
    # Production intentionally disables Flask's static_folder. The source tree
    # stays read-only; all hashing is finished before serving any request.
    root = Path(app.root_path) / "static"
    versions = {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()[:10]
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
    manifest = root / "fonts" / "manifest.json"
    aliases = json.loads(manifest.read_text()) if manifest.is_file() else {}
    for logical, physical in aliases.items():
        if (
            physical not in versions
            or f".{versions[physical]}.woff2" not in physical
            or (logical in versions and versions[logical] != versions[physical])
        ):
            raise RuntimeError(
                f"Stale font version for {logical}; run python scripts/prepare_assets.py"
            )
    versions = MappingProxyType(versions)
    aliases = MappingProxyType(aliases)

    def asset_url(filename):
        physical = aliases.get(filename, filename)
        return url_for("static", filename=physical, v=versions[physical])

    app.extensions["asset_versions"] = versions
    app.extensions["asset_aliases"] = aliases
    app.jinja_env.globals["asset_url"] = asset_url

    @app.context_processor
    def asset_context():
        return {"asset_url": asset_url}
