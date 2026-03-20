"""Tests for release version planning and synchronization helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from subprocess import CompletedProcess

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / ".github/scripts/release_version.py"
SPEC = importlib.util.spec_from_file_location("release_version", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
release_version = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_version)


def test_resolve_bump_type_defaults_to_patch() -> None:
    """Patch releases are the default when no release label is present."""
    assert release_version.resolve_bump_type([]) == "patch"


def test_resolve_bump_type_rejects_multiple_release_labels() -> None:
    """Only one release label can drive the bump strategy."""
    with pytest.raises(ValueError, match="Multiple release labels detected"):
        release_version.resolve_bump_type(["release:major", "release:minor"])


def test_plan_version_uses_bumpversion_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Release planning is delegated to bumpversion dry-run output."""

    def fake_run_bumpversion(*args: str) -> CompletedProcess[str]:
        assert args == ("--allow-dirty", "--dry-run", "--list", "minor")
        return CompletedProcess(
            args=list(args),
            returncode=0,
            stdout="current_version=0.1.0\nnew_version=0.2.0\n",
            stderr="",
        )

    monkeypatch.setattr(release_version, "_run_bumpversion", fake_run_bumpversion)

    assert release_version.plan_version("minor") == {
        "current_version": "0.1.0",
        "bump_type": "minor",
        "next_version": "0.2.0",
    }


def test_apply_version_uses_bumpversion_configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Version application is delegated to bumpversion against tracked files."""
    bumpversion_cfg = tmp_path / ".bumpversion.cfg"
    gitversion = tmp_path / "GitVersion.yml"
    pyproject = tmp_path / "pyproject.toml"
    package_init = tmp_path / "src/owi/metadatabase/results/__init__.py"
    test_imports = tmp_path / "tests/test_imports.py"
    uv_lock = tmp_path / "uv.lock"

    package_init.parent.mkdir(parents=True, exist_ok=True)
    test_imports.parent.mkdir(parents=True, exist_ok=True)

    for path in (bumpversion_cfg, gitversion, pyproject, package_init, test_imports, uv_lock):
        path.write_text("stub\n", encoding="utf-8")

    recorded: list[tuple[str, ...]] = []

    def fake_run_bumpversion(*args: str) -> CompletedProcess[str]:
        recorded.append(args)
        return CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")

    monkeypatch.setattr(release_version, "ROOT", tmp_path)
    monkeypatch.setattr(release_version, "BUMPVERSION_PATH", bumpversion_cfg)
    monkeypatch.setattr(release_version, "GITVERSION_PATH", gitversion)
    monkeypatch.setattr(release_version, "PYPROJECT_PATH", pyproject)
    monkeypatch.setattr(release_version, "PACKAGE_VERSION_PATH", package_init)
    monkeypatch.setattr(release_version, "TEST_IMPORTS_PATH", test_imports)
    monkeypatch.setattr(release_version, "UV_LOCK_PATH", uv_lock)
    monkeypatch.setattr(
        release_version,
        "TRACKED_VERSION_PATHS",
        (bumpversion_cfg, gitversion, pyproject, package_init, test_imports, uv_lock),
    )
    monkeypatch.setattr(release_version, "read_project_version", lambda: "0.1.0")
    monkeypatch.setattr(release_version, "_run_bumpversion", fake_run_bumpversion)

    changed_paths = release_version.apply_version("0.1.1")

    assert recorded == [("--allow-dirty", "--new-version", "0.1.1", "patch")]
    assert changed_paths == [
        ".bumpversion.cfg",
        "GitVersion.yml",
        "pyproject.toml",
        "src/owi/metadatabase/results/__init__.py",
        "tests/test_imports.py",
        "uv.lock",
    ]


@pytest.mark.parametrize(
    ("current_version", "new_version", "expected"),
    [
        ("0.1.0", "1.0.0", "major"),
        ("0.1.0", "0.2.0", "minor"),
        ("0.1.0", "0.1.1", "patch"),
    ],
)
def test_infer_bump_type(current_version: str, new_version: str, expected: str) -> None:
    """Explicit target versions are mapped back to bumpversion parts."""
    assert release_version.infer_bump_type(current_version, new_version) == expected


def test_parse_bumpversion_output_ignores_non_key_value_lines() -> None:
    """Only key-value pairs are parsed from bumpversion output."""
    output = "Reading config file\ncurrent_version=0.1.0\nnew_version=0.1.1\n"
    assert release_version._parse_bumpversion_output(output) == {
        "current_version": "0.1.0",
        "new_version": "0.1.1",
    }
