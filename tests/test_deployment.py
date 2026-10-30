"""Static deployment contracts; these checks never start or signal live services."""

import json
import re
import runpy
import shlex
from configparser import ConfigParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_preloaded_application_requires_restart_not_a_reload_shortcut():
    gunicorn = runpy.run_path(str(ROOT / "deployment/gunicorn.conf.py"))
    service = ConfigParser(interpolation=None)
    service.read(ROOT / "deployment/dj-nazyer.service")
    assert gunicorn["preload_app"] is True
    assert gunicorn["workers"] == 2
    assert not service.has_option("Service", "ExecReload")
    assert "systemctl restart dj-nazyer" in (ROOT / "README.md").read_text()


def test_access_log_schema_omits_queries_and_escapes_untrusted_text():
    source = (ROOT / "deployment/nginx-log-format.conf.example").read_text()
    lexer = shlex.shlex(source, posix=True, punctuation_chars=";")
    lexer.whitespace_split = True
    tokens = list(lexer)
    assert tokens[:3] == ["log_format", "nazyer_safe", "escape=json"]
    template = "".join(tokens[3 : tokens.index(";")])
    variables = set(re.findall(r"\$[A-Za-z_][A-Za-z_0-9]*", template))
    assert variables == {
        "$remote_addr",
        "$time_iso8601",
        "$request_method",
        "$uri",
        "$status",
        "$body_bytes_sent",
        "$http_user_agent",
    }
    sample = {
        "$remote_addr": "192.0.2.10",
        "$time_iso8601": "2026-10-29T21:00:00+07:00",
        "$request_method": "GET",
        "$uri": "/kontak",
        "$status": 200,
        "$body_bytes_sent": 1234,
        "$http_user_agent": 'Browser "audit"\nnext-line',
        "$args": "secret=PRIVATE_QUERY_VALUE",
    }

    def escaped(match):
        value = sample[match.group()]
        return json.dumps(value)[1:-1] if isinstance(value, str) else str(value)

    rendered = re.sub(r"\$[A-Za-z_][A-Za-z_0-9]*", escaped, template)
    row = json.loads(rendered)
    assert row["uri"] == "/kontak"
    assert row["user_agent"] == sample["$http_user_agent"]
    assert "PRIVATE_QUERY_VALUE" not in rendered


def test_gzip_and_site_logging_keep_sensitive_html_uncompressed():
    source = (ROOT / "deployment/nginx.conf").read_text()
    assert "access_log /var/log/nginx/dj-nazyer/access.log nazyer_safe;" in source
    assert "access_log off;" not in source
    assert "gzip on;" in source
    types = re.search(r"gzip_types\s+([^;]+);", source).group(1).split()
    assert {"text/css", "application/javascript", "image/svg+xml", "application/xml"} <= set(types)

    def proxy_lines(prefix):
        body = re.search(prefix + r"\s*\{([^{}]*)\}", source, re.DOTALL).group(1)
        directives = [
            line.strip() for line in body.splitlines() if line.strip().startswith("proxy_")
        ]
        return body, directives

    _, expected = proxy_lines(r"location /")
    for prefix in [
        r"location \^~ /admin",
        r"location \^~ /kontak",
        r"location = /admin/login",
        r"location = /kontak",
    ]:
        body, directives = proxy_lines(prefix)
        assert "gzip off;" in body
        assert directives == expected


def test_shared_post_rate_zones_are_required_and_connected_to_vhost():
    limits = (ROOT / "deployment/rate-limits.conf.example").read_text()
    source = (ROOT / "deployment/nginx.conf").read_text()
    zones = dict(
        re.findall(r"limit_req_zone \$nazyer_write_key zone=(\w+):1m rate=([^;]+)", limits)
    )
    assert zones == {"nazyer_login": "5r/m", "nazyer_inquiry": "3r/m"}
    mapping = re.search(r"map \$request_method \$nazyer_write_key\s*\{([^}]+)\}", limits).group(1)
    assert 'default "";' in mapping and "POST $binary_remote_addr;" in mapping
    referenced = set(re.findall(r"limit_req zone=(\w+)", source))
    assert referenced == set(zones)
    for path, zone in [("/admin/login", "nazyer_login"), ("/kontak", "nazyer_inquiry")]:
        body = re.search(r"location = " + path + r"\s*\{([^{}]+)\}", source).group(1)
        assert f"limit_req zone={zone}" in body
        assert "limit_req_status 429;" in body and "nodelay;" in body
    readme = (ROOT / "README.md").read_text()
    assert "### Required shared rate-limit deployment checklist" in readme
    assert "dj-nazyer-rate-limits.conf" in readme and "- [ ] Run `nginx -t`" in readme


def test_log_retention_limits_daily_archives_and_continues_when_empty():
    source = (ROOT / "deployment/dj-nazyer-logrotate.conf.example").read_text()
    assert "/var/log/nginx/dj-nazyer/access.log" in source
    assert re.search(r"^\s*daily\s*$", source, re.MULTILINE)
    archives = int(re.search(r"^\s*rotate\s+(\d+)", source, re.MULTILINE).group(1))
    maximum_age = int(re.search(r"^\s*maxage\s+(\d+)", source, re.MULTILINE).group(1))
    assert archives + 1 <= 14
    assert maximum_age <= 13
    assert re.search(r"^\s*ifempty\s*$", source, re.MULTILINE)
    assert "create 0640" in source and "nginx -s reopen" in source
