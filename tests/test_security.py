"""Security and privacy checks that run on every change.

1. The scripts only use the standard library, never run other programs or dynamic code, and
   only contain URLs for the hosts the skill documents.
2. No personal data is committed. Terms to look for (name, city, e-mail...) come from the
   PRIVACY_TERMS repository secret, one per line, so the list itself is never public.
"""
import ast
import os
import re
import subprocess

import pytest

from conftest import ROOT, SKILL

SCRIPTS = sorted((SKILL / "scripts").glob("*.py"))
ALLOWED_HOSTS = {"news.google.com", "wttr.in", "api.open-meteo.com", "open-meteo.com", "wikipedia.org",
                 "mail.google.com"}
BANNED_IMPORTS = {"subprocess", "socket", "pickle", "marshal", "ctypes", "shelve", "requests", "http.server"}
BANNED_CALLS = {"eval", "exec", "compile", "__import__", "system", "popen", "spawnl", "spawnv", "execv", "execl"}


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_no_dangerous_imports_or_calls(script):
    tree = ast.parse(script.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            names = []
        for name in names:
            assert name not in BANNED_IMPORTS and name.split(".")[0] not in BANNED_IMPORTS, name
        if isinstance(node, ast.Call):
            fn = node.func
            called = fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else ""
            assert called not in BANNED_CALLS, f"{script.name}:{node.lineno} calls {called}()"


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_only_documented_hosts(script):
    hosts = re.findall(r"https?://([a-z0-9.{}_-]+)", script.read_text(encoding="utf-8"), re.I)
    for host in hosts:
        host = host.lower().rstrip(".")
        if "{" in host:  # e.g. {lang}.wikipedia.org
            host = host.split("}", 1)[-1].lstrip(".")
        assert any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS), f"{script.name}: {host}"


def test_no_http_links_in_scripts():
    for script in SCRIPTS:
        assert "http://" not in script.read_text(encoding="utf-8"), script.name


def tracked_files():
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        return [ROOT / f for f in out.splitlines()]
    except (OSError, subprocess.CalledProcessError):
        return [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]


def test_no_reader_profile_committed():
    names = [p.relative_to(ROOT).as_posix() for p in tracked_files()]
    assert not [n for n in names if n.endswith("config.json") or n.endswith("collected.json")]


def test_no_personal_data():
    terms = [t.strip().lower() for t in os.environ.get("PRIVACY_TERMS", "").splitlines() if t.strip()]
    if not terms:
        pytest.skip("PRIVACY_TERMS secret not set (normal on forks and local runs)")
    hits = []
    for path in tracked_files():
        if path.suffix.lower() in {".png", ".jpg", ".zip", ".ico"} or not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for i, term in enumerate(terms, 1):
            if term in text:
                hits.append(f"{path.relative_to(ROOT)} contains private term #{i}")  # never print the term
    assert not hits, hits
