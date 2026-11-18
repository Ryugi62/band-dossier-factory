"""demo.sh: from this checkout, one command reaches a healthy stage-4 service; `stop` cleans up.

Skipped when Docker is not available. Uses PORT=18093 so it does not collide with a local 8080.
"""
import json
import os
import pathlib
import shutil
import subprocess
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PORT = "18093"


@pytest.mark.skipif(shutil.which("docker") is None, reason="needs Docker")
def test_demo_reaches_health_and_stops():
    env = dict(os.environ, PORT=PORT)
    up = subprocess.run(["sh", str(ROOT / "demo.sh")], env=env, capture_output=True, text=True, timeout=900)
    try:
        assert up.returncode == 0, up.stderr
        assert f"ready: http://localhost:{PORT}" in up.stdout
        with urllib.request.urlopen(f"http://localhost:{PORT}/health", timeout=10) as r:
            assert json.load(r) == {"status": "ok"}
    finally:
        down = subprocess.run(["sh", str(ROOT / "demo.sh"), "stop"], capture_output=True, text=True, timeout=120)
    assert down.stdout.strip() == "stopped"
    names = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True).stdout.split()
    assert "dossier-demo-svc" not in names and "dossier-demo-web" not in names


@pytest.mark.skipif(shutil.which("docker") is None, reason="needs Docker")
def test_demo_fails_fast_with_hint_when_mock_web_dies(tmp_path):
    """Corpus not visible to the container (e.g. a folder the Docker VM does not share) -> exit 1 within
    ~30 s and name the mock web, not 180 s of silence."""
    org = ROOT.parent / "sf-buildathon-2026"
    if not (org / "challenges/dossier/web").is_dir():
        pytest.skip("needs the organizer checkout next to this repo")
    fake = tmp_path / "org"
    shutil.copytree(org / "challenges/dossier/web", fake / "challenges/dossier/web", ignore=shutil.ignore_patterns("sample"))
    (fake / "challenges/dossier/web/corpus/sample").mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PORT="18094", ORG=str(fake))
    try:
        r = subprocess.run(["sh", str(ROOT / "demo.sh")], env=env, capture_output=True, text=True, timeout=170)
        assert r.returncode == 1
        assert "mock web" in r.stderr
    finally:
        subprocess.run(["sh", str(ROOT / "demo.sh"), "stop"], capture_output=True, text=True, timeout=120)
