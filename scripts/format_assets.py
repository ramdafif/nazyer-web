"""Format repository-owned CSS/JS with the Python beautifiers, without Node."""

import argparse
from pathlib import Path

import cssbeautifier
import jsbeautifier

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    changed = []
    for extension, formatter in [("css", cssbeautifier), ("js", jsbeautifier)]:
        options = formatter.default_options()
        options.indent_size = 4
        options.end_with_newline = True
        # Automatic JS line wrapping can oscillate around nested ES6 expressions.
        # The default zero-wrap policy is idempotent; block indentation remains explicit.
        options.wrap_line_length = 100 if extension == "css" else 0
        for path in sorted((ROOT / "app/static" / extension).rglob("*." + extension)):
            source = path.read_text()
            formatted = formatter.beautify(source, options)
            if source != formatted:
                changed.append(str(path.relative_to(ROOT)))
                if not args.check:
                    path.write_text(formatted)
    if changed:
        print(("Needs formatting: " if args.check else "Formatted: ") + ", ".join(changed))
    if args.check and changed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
