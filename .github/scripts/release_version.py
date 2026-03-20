"""Release version planning and file synchronization helpers."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = ROOT / "pyproject.toml"
PACKAGE_VERSION_PATH = ROOT / "src/owi/metadatabase/results/__init__.py"
BUMPVERSION_PATH = ROOT / ".bumpversion.cfg"
GITVERSION_PATH = ROOT / "GitVersion.yml"
UV_LOCK_PATH = ROOT / "uv.lock"
TEST_IMPORTS_PATH = ROOT / "tests/test_imports.py"

TRACKED_VERSION_PATHS = (
    BUMPVERSION_PATH,
    GITVERSION_PATH,
    PYPROJECT_PATH,
    PACKAGE_VERSION_PATH,
    TEST_IMPORTS_PATH,
    UV_LOCK_PATH,
)

RELEASE_LABELS = {
    "release:major": "major",
    "release:minor": "minor",
    "release:patch": "patch",
}
SEMVER_PATTERN = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _find_bumpversion_executable() -> str:
    candidates = [
        ROOT / ".venv/bin/bumpversion",
        ROOT / ".venv/Scripts/bumpversion.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return "bumpversion"


def _run_bumpversion(*args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [_find_bumpversion_executable(), "--config-file", str(BUMPVERSION_PATH), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        details = stderr or stdout or f"exit code {result.returncode}"
        raise RuntimeError(f"bumpversion failed: {details}")
    return result


def _parse_bumpversion_output(output: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in output.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def read_project_version() -> str:
    content = _read_text(PYPROJECT_PATH)
    match = re.search(
        r'^\[project\]$(?:\n(?!\[).*)*?^version = "(?P<version>\d+\.\d+\.\d+)"$',
        content,
        flags=re.MULTILINE,
    )
    if match is None:
        raise ValueError("Could not resolve project version from pyproject.toml")
    return match.group("version")


def parse_labels(labels_json: str) -> list[str]:
    labels = json.loads(labels_json)
    if not isinstance(labels, list) or not all(isinstance(label, str) for label in labels):
        raise ValueError("Labels payload must be a JSON array of strings")
    return labels


def resolve_bump_type(labels: list[str]) -> str:
    requested = [bump for label, bump in RELEASE_LABELS.items() if label in set(labels)]
    if len(requested) > 1:
        supported = ", ".join(sorted(RELEASE_LABELS))
        raise ValueError(f"Multiple release labels detected. Use at most one of: {supported}")
    if requested:
        return requested[0]
    return "patch"


def bump_version(current_version: str, bump_type: str) -> str:
    match = SEMVER_PATTERN.match(current_version)
    if match is None:
        raise ValueError(f"Unsupported version format: {current_version}")

    major = int(match.group("major"))
    minor = int(match.group("minor"))
    patch = int(match.group("patch"))

    if bump_type == "major":
        return f"{major + 1}.0.0"
    if bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    if bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"Unsupported bump type: {bump_type}")


def plan_version(bump_type: str) -> dict[str, str]:
    result = _run_bumpversion("--allow-dirty", "--dry-run", "--list", bump_type)
    parsed = _parse_bumpversion_output(result.stdout)
    current_version = parsed.get("current_version")
    next_version = parsed.get("new_version")
    if current_version is None or next_version is None:
        raise ValueError("bumpversion did not provide current_version and new_version")
    return {
        "current_version": current_version,
        "bump_type": bump_type,
        "next_version": next_version,
    }


def infer_bump_type(current_version: str, new_version: str) -> str:
    current_match = SEMVER_PATTERN.match(current_version)
    new_match = SEMVER_PATTERN.match(new_version)
    if current_match is None or new_match is None:
        raise ValueError("Unsupported version format")

    current_major = int(current_match.group("major"))
    current_minor = int(current_match.group("minor"))
    current_patch = int(current_match.group("patch"))

    new_major = int(new_match.group("major"))
    new_minor = int(new_match.group("minor"))
    new_patch = int(new_match.group("patch"))

    if (new_major, new_minor, new_patch) == (current_major + 1, 0, 0):
        return "major"
    if (new_major, new_minor, new_patch) == (current_major, current_minor + 1, 0):
        return "minor"
    if (new_major, new_minor, new_patch) == (current_major, current_minor, current_patch + 1):
        return "patch"
    raise ValueError(f"Could not infer bump type from {current_version} -> {new_version}")


def write_github_output(output_path: str | None, values: dict[str, str]) -> None:
    if output_path is None:
        return

    lines = [f"{key}={value}" for key, value in values.items()]
    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def apply_version(new_version: str) -> list[str]:
    if SEMVER_PATTERN.match(new_version) is None:
        raise ValueError(f"Unsupported version format: {new_version}")

    current_version = read_project_version()
    bump_type = infer_bump_type(current_version, new_version)
    _run_bumpversion("--allow-dirty", "--new-version", new_version, bump_type)

    return [str(path.relative_to(ROOT)) for path in TRACKED_VERSION_PATHS if path.exists()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="Resolve the next release version from labels")
    plan_parser.add_argument("--labels-json", default="[]", help="JSON array of GitHub label names")
    plan_parser.add_argument("--github-output", help="Path to the GitHub Actions output file")

    apply_parser = subparsers.add_parser("apply", help="Update tracked files to a new version")
    apply_parser.add_argument("--new-version", required=True, help="Version to write across tracked files")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "plan":
        labels = parse_labels(args.labels_json)
        bump_type = resolve_bump_type(labels)
        payload = plan_version(bump_type)
        print(json.dumps(payload))
        write_github_output(args.github_output, payload)
        return 0

    if args.command == "apply":
        changed_paths = apply_version(args.new_version)
        print(json.dumps({"new_version": args.new_version, "changed_files": changed_paths}))
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
