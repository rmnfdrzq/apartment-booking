"""End-to-end test: run scripts/demo.sh against a real server process (Checkpoint 1)."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

DEMO_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "demo.sh"

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("bash") is None or shutil.which("curl") is None,
    reason="demo script needs bash and curl",
)


def test_demo_script_passes_end_to_end() -> None:
    env = {**os.environ, "NO_COLOR": "1", "PYTHON": sys.executable}
    # The script starts its own server with a temporary database; it must not
    # inherit the in-memory test database or an external server URL.
    env.pop("DATABASE_URL", None)
    env.pop("BASE_URL", None)

    result = subprocess.run(
        ["bash", str(DEMO_SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "All" in result.stdout and "checks passed" in result.stdout
    assert "skipped" not in result.stdout  # persistence step must really run


def test_demo_script_help() -> None:
    result = subprocess.run(["bash", str(DEMO_SCRIPT), "--help"], capture_output=True, text=True, check=False)

    assert result.returncode == 0
    assert "BASE_URL" in result.stdout
