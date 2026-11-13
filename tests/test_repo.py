"""Repository consistency: version, changelog, SKILL.md, referenced files and the release zip."""
import json
import re
import shutil
import subprocess
import zipfile

import pytest

from conftest import ROOT, SKILL

VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def test_version_is_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", VERSION), VERSION


def test_changelog_has_a_section_for_this_version():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.search(rf"^## v{re.escape(VERSION)}\b", changelog, re.M), \
        f"CHANGELOG.md needs a '## v{VERSION}' section (the release notes come from it)"


def test_user_agent_matches_version():
    """Bump the User-Agent in collect.py together with VERSION."""
    source = (SKILL / "scripts" / "collect.py").read_text(encoding="utf-8")
    assert f"morning-newspaper/{VERSION}" in source


def frontmatter():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert m, "SKILL.md must start with a --- frontmatter block"
    fields = {}
    for line in m.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip('"')
    return fields


def test_skill_frontmatter():
    fm = frontmatter()
    assert fm.get("name") == "morning-newspaper" == SKILL.name
    assert 0 < len(fm.get("description", "")) <= 1024
    assert "<" not in fm["description"] and ">" not in fm["description"]


def test_every_referenced_file_exists():
    texts = [SKILL / "SKILL.md", *(SKILL / "references").glob("*.md")]
    missing = set()
    for path in texts:
        for ref in re.findall(r"\b((?:references|scripts|assets)/[\w./-]+\.(?:md|py|json|html))", path.read_text(encoding="utf-8")):
            if not (SKILL / ref).exists():
                missing.add(f"{path.name}: {ref}")
    assert not missing, sorted(missing)


def test_config_example_is_complete():
    cfg = json.loads((SKILL / "references" / "config.example.json").read_text(encoding="utf-8"))
    for key in ("language", "timezone", "newspaper", "city", "sections", "total_news", "avoid"):
        assert key in cfg, key
    assert cfg["avoid"] == [], "the example must not filter anything by default"
    ids = [s["id"] for s in cfg["sections"]]
    assert len(ids) == len(set(ids)), "section ids must be unique"
    for sec in cfg["sections"]:
        assert sec.get("title") and sec.get("layout") in ("main", "half", "single"), sec["id"]
        assert all(str(f).startswith("https://") for f in sec.get("feeds", [])), sec["id"]


@pytest.mark.skipif(not shutil.which("zip"), reason="zip command not installed")
def test_build_zip(tmp_path):
    """Runs build-zip.sh on a copy of the repository, never touching the committed dist/ zip."""
    shutil.copy(ROOT / "build-zip.sh", tmp_path)
    shutil.copytree(SKILL, tmp_path / SKILL.name)
    (tmp_path / SKILL.name / "config.json").write_text("{}", encoding="utf-8")  # must be left out
    (tmp_path / SKILL.name / "scripts" / "__pycache__").mkdir(exist_ok=True)
    (tmp_path / SKILL.name / "scripts" / "__pycache__" / "x.pyc").write_bytes(b"")
    subprocess.run(["sh", "build-zip.sh"], cwd=tmp_path, check=True, capture_output=True)
    names = zipfile.ZipFile(tmp_path / "dist" / "morning-newspaper.zip").namelist()
    assert "morning-newspaper/SKILL.md" in names
    assert "morning-newspaper/scripts/assemble.py" in names
    assert all(n.startswith("morning-newspaper/") for n in names)
    assert not any(n.endswith("config.json") or "__pycache__" in n or n.endswith(".pyc") for n in names)


def test_setup_does_not_ask_for_the_newspaper_name():
    """Readers rename the newspaper on request; setup only asks topics, time, subjects to avoid and city."""
    setup = (SKILL / "references" / "setup.md").read_text(encoding="utf-8")
    screen2 = setup[setup.index("**Screen 2**"):setup.index("**Then one line of text**")]
    assert "name" not in screen2.lower()
    for option in ("Don't schedule for now", "Another time", "(Recommended)"):
        assert option in setup, option
