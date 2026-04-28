#!/usr/bin/env python3
"""Create or delete tox-specific Molecule scenario files."""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import shutil
import subprocess


TOX_ENV_RE = re.compile(r"(?P<ansible_factor>\d+\.\d+)$")


def find_project_root(start_dir: pathlib.Path) -> pathlib.Path:
    current = start_dir.resolve()

    while current != current.parent:
        if (current / "molecule").is_dir():
            return current
        current = current.parent

    raise SystemExit(f"Unable to find project root from script directory: {start_dir}")


def current_tox_env_name(cli_value: str | None) -> str:
    if cli_value:
        return cli_value

    env_value = os.environ.get("TOX_ENV_NAME") or os.environ.get("TOXENV")
    if env_value:
        return env_value

    raise SystemExit(
        "Unable to determine tox environment name. Pass --tox-env or set TOX_ENV_NAME/TOXENV."
    )


def ansible_factor_from_tox_env(tox_env_name: str) -> str:
    match = TOX_ENV_RE.search(tox_env_name)
    if match is None:
        raise SystemExit(f"Unable to extract ansible factor from tox env: {tox_env_name}")
    return match.group("ansible_factor")


def core_name_from_ansible_factor(ansible_factor: str) -> str:
    return f"core{ansible_factor.replace('.', '')}"


def repo_relative_path(absolute_path: pathlib.Path, repo_root: pathlib.Path) -> str:
    return str(absolute_path.relative_to(repo_root))


def run_git(*args: str, repo_root: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        text=True,
        capture_output=True,
    )


def is_git_tracked(path: pathlib.Path, repo_root: pathlib.Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "--error-unmatch", "--", repo_relative_path(path, repo_root)],
        check=False,
        text=True,
        capture_output=True,
    )
    return result.returncode == 0


def create_target(source_file: pathlib.Path, target_dir: pathlib.Path, repo_root: pathlib.Path) -> None:
    if not source_file.is_file():
        raise SystemExit(f"Source molecule file does not exist: {source_file}")

    source_dir = source_file.parent

    if target_dir.is_symlink():
        target_dir.unlink()
    elif target_dir.is_dir():
        subprocess.run(
            ["git", "-C", str(repo_root), "rm", "-r", "-f", "--", repo_relative_path(target_dir, repo_root)],
            check=False,
            text=True,
            capture_output=True,
        )
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=False)
    elif target_dir.exists():
        raise SystemExit(f"Refusing to replace non-directory path: {target_dir}")

    target_dir.mkdir(parents=True, exist_ok=True)

    for source_path in sorted(source_dir.rglob("*")):
        relative_path = source_path.relative_to(source_dir)
        target_path = target_dir / relative_path

        if source_path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
            continue

        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists() or target_path.is_symlink():
            target_path.unlink()
        target_path.symlink_to(source_path)

    run_git("add", "-A", "--", repo_relative_path(target_dir, repo_root), repo_root=repo_root)


def delete_target(target_dir: pathlib.Path, repo_root: pathlib.Path) -> None:
    if target_dir.is_symlink():
        if is_git_tracked(target_dir, repo_root):
            subprocess.run(
                ["git", "-C", str(repo_root), "rm", "-f", "--", repo_relative_path(target_dir, repo_root)],
                check=True,
                text=True,
            )
        else:
            target_dir.unlink()
    elif target_dir.is_dir():
        if is_git_tracked(target_dir, repo_root):
            subprocess.run(
                ["git", "-C", str(repo_root), "rm", "-r", "-f", "--", repo_relative_path(target_dir, repo_root)],
                check=True,
                text=True,
            )
        else:
            shutil.rmtree(target_dir, ignore_errors=False)
    elif target_dir.exists():
        raise SystemExit(f"Refusing to delete non-directory path: {target_dir}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create or delete tox-specific Molecule scenario files.")
    parser.add_argument("action", choices=["create", "delete"])
    parser.add_argument("--scenario-name", default="default")
    parser.add_argument("--tox-env")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    script_dir = pathlib.Path(__file__).resolve().parent
    project_root = find_project_root(script_dir)
    repo_root = pathlib.Path(
        subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "--show-toplevel"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
    )

    tox_env_name = current_tox_env_name(args.tox_env)
    ansible_factor = ansible_factor_from_tox_env(tox_env_name)
    core_name = core_name_from_ansible_factor(ansible_factor)

    source_file = project_root / "molecule" / core_name / args.scenario_name / "molecule.yml"
    target_dir = project_root / "molecule" / f"{args.scenario_name}@{core_name}"

    if args.action == "create":
        create_target(source_file, target_dir, repo_root)
        return 0

    delete_target(target_dir, repo_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
