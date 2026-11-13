"""Shared helpers for the test suite. No test touches the network."""
import copy
import importlib.util
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL = ROOT / "morning-newspaper"
SCRIPTS = SKILL / "scripts"
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"


def load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


@pytest.fixture
def config():
    """The public example profile, used as the reader's config."""
    cfg = load_json(SKILL / "references" / "config.example.json")
    cfg.pop("_readme", None)
    return cfg


@pytest.fixture
def collected():
    return load_json(FIXTURES / "collected.sample.json")


@pytest.fixture
def edition():
    return load_json(FIXTURES / "edition.sample.json")


class Assembler:
    """Runs scripts/assemble.py in a temporary working folder."""

    def __init__(self, tmp_path, config, collected, edition):
        self.tmp = tmp_path
        self.config = config
        self.collected = collected
        self.edition = edition
        self.index = None

    def run(self, *args, index=None):
        work = self.tmp / "work"
        work.mkdir(exist_ok=True)
        cfg_path = self.tmp / "config.json"
        cfg_path.write_text(json.dumps(self.config, ensure_ascii=False), encoding="utf-8")
        (work / "edition.json").write_text(json.dumps(self.edition, ensure_ascii=False), encoding="utf-8")
        (work / "collected.json").write_text(json.dumps(self.collected, ensure_ascii=False), encoding="utf-8")
        cmd = [sys.executable, str(SCRIPTS / "assemble.py"), "--skill", str(SKILL),
               "--config", str(cfg_path), "--work", str(work), *args]
        index = index if index is not None else self.index
        if index is not None:
            idx_path = self.tmp / "index.json"
            idx_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
            cmd += ["--index", str(idx_path)]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        proc.archive = work / "archive"
        return proc

    def page(self, date="2026-11-13"):
        return (self.tmp / "work" / "archive" / "editions" / f"{date}.html").read_text(encoding="utf-8")

    def new_index(self):
        return load_json(self.tmp / "work" / "archive" / "editions" / "index.json")


@pytest.fixture
def assembler(tmp_path, config, collected, edition):
    return Assembler(tmp_path, copy.deepcopy(config), copy.deepcopy(collected), copy.deepcopy(edition))


@pytest.fixture(scope="session")
def collect_module():
    """Imports scripts/collect.py as a module so its functions can be tested directly."""
    spec = importlib.util.spec_from_file_location("collect", SCRIPTS / "collect.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def offline(monkeypatch, collect_module):
    """Replaces collect.fetch with a fake. Register responses with offline[url_substring] = bytes;
    any other URL raises, so a test can never reach the internet."""
    responses = {}

    def fake_fetch(url, tries=2):
        for key, body in responses.items():
            if key in url:
                if isinstance(body, Exception):
                    raise body
                return body if isinstance(body, bytes) else body.encode("utf-8")
        raise OSError(f"unexpected network access in a test: {url}")

    monkeypatch.setattr(collect_module, "fetch", fake_fetch)
    return responses
