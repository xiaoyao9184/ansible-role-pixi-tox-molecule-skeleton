#!/usr/bin/env python3
"""Generate a minimal galaxy.yml from meta/main.yml for tox-ansible."""

from __future__ import annotations

import argparse
import pathlib


PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_META = PROJECT_ROOT / "meta" / "main.yml"
DEFAULT_GALAXY = PROJECT_ROOT / "galaxy.yml"


def parse_galaxy_info(meta_path: pathlib.Path) -> dict[str, str]:
    galaxy_info: dict[str, str] = {}
    in_galaxy_info = False

    for raw_line in meta_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        if raw_line.startswith("galaxy_info:"):
            in_galaxy_info = True
            continue

        if not in_galaxy_info:
            continue

        if raw_line[:1] not in {" ", "\t"}:
            break

        line = stripped
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        value = value.strip()

        if not value:
            continue

        if value[0] in {'"', "'"} and value[-1] == value[0]:
            value = value[1:-1]

        galaxy_info[key.strip()] = value

    return galaxy_info


def fallback(value: str | None) -> str:
    if value is None:
        return "none"

    normalized = value.strip()
    return normalized or "none"


def fallback_version(value: str | None) -> str:
    if value is None:
        return "0.0.0"

    normalized = value.strip()
    return normalized or "0.0.0"


def quote_yaml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_galaxy_yaml(meta: dict[str, str]) -> str:
    data = {
        "namespace": fallback(meta.get("namespace")),
        "name": fallback(meta.get("role_name") or meta.get("name")),
        "version": fallback_version(meta.get("version")),
        "readme": fallback(meta.get("description")),
        "authors": fallback(meta.get("author")),
    }

    return (
        f"namespace: {data['namespace']}\n"
        f"name: {data['name']}\n"
        f"version: {data['version']}\n"
        f"readme: {quote_yaml_string(data['readme'])}\n"
        f"authors: {data['authors']}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a fake galaxy.yml from meta/main.yml for tox-ansible.",
    )
    parser.add_argument(
        "--meta",
        type=pathlib.Path,
        default=DEFAULT_META,
        help=f"Path to meta/main.yml (default: {DEFAULT_META})",
    )
    parser.add_argument(
        "--galaxy-output",
        type=pathlib.Path,
        default=DEFAULT_GALAXY,
        help=f"Path to generated galaxy.yml (default: {DEFAULT_GALAXY})",
    )
    args = parser.parse_args()

    meta_path = args.meta if args.meta.is_absolute() else PROJECT_ROOT / args.meta
    output_path = args.galaxy_output if args.galaxy_output.is_absolute() else PROJECT_ROOT / args.galaxy_output

    output_path.write_text(render_galaxy_yaml(parse_galaxy_info(meta_path)), encoding="utf-8")
    print(output_path.relative_to(PROJECT_ROOT))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
