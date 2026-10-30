"""Guard bundled UI copy without mistaking substrings or Python identifiers for slang."""

import ast
import re
from pathlib import Path

import pytest
from jinja2 import Environment, nodes

ROOT = Path(__file__).resolve().parents[1]
INFORMAL = re.compile(r"\b(lo|lu|gue|gw)\b", re.IGNORECASE)


def displayed_strings(path):
    source = path.read_text()
    if path.suffix == ".py":
        tree = ast.parse(source)
        return [
            (node.lineno, node.value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
    template = Environment().parse(source)
    return [
        (node.lineno, node.data if isinstance(node, nodes.TemplateData) else node.value)
        for node in template.find_all((nodes.TemplateData, nodes.Const))
        if isinstance(node, nodes.TemplateData) or isinstance(node.value, str)
    ]


def test_bundled_public_admin_and_demo_copy_has_no_informal_pronouns():
    files = list((ROOT / "app/templates").rglob("*.html"))
    files += list((ROOT / "app/templates").rglob("*.xml"))
    for directory in ["forms", "blueprints", "services"]:
        files += list((ROOT / "app" / directory).rglob("*.py"))
    violations = [
        f"{path.relative_to(ROOT)}:{line}: {text.strip()}"
        for path in files
        for line, text in displayed_strings(path)
        if INFORMAL.search(text)
    ]
    assert not violations, "\n".join(violations)


@pytest.mark.parametrize("word", ["lo", "lu", "gue", "gw", "Lo", "GUE", "event lo."])
def test_copy_guard_rejects_whole_informal_words(word):
    assert INFORMAL.search(word)


@pytest.mark.parametrize(
    "word", ["lokasi", "logo", "global", "glow", "workflow", "katalog", "gulir", "dialog"]
)
def test_copy_guard_preserves_unrelated_words(word):
    assert not INFORMAL.search(word)


def test_form_and_default_metadata_address_visitors_formally(client):
    homepage = client.get("/").text
    contact = client.get("/kontak").text
    assert "acara Anda" in homepage
    assert "Ceritakan rencana acara Anda" in contact
    assert "Kontak Anda hanya digunakan untuk menindaklanjuti inquiry ini." in contact
