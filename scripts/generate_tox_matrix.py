#!/usr/bin/env python3
"""Generate GitHub Actions matrix data for Molecule scenarios and tox envs."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
from typing import Any


PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
TOX_DIR = PROJECT_ROOT / "tox"
TOX_ENV_RE = re.compile(
    r"^(?P<tox_env>molecule-(?P<py_factor>py\d+\.\d+)-(?P<ansible_factor>\d+\.\d+))$"
)
TOX_ENVLIST_ITEM_RE = re.compile(
    r"molecule-(?P<py_factor>py\d+\.\d+)-\{(?P<ansible_factors>[^}]+)\}"
)
SKIP_MOLECULE_SCENARIO_RE = re.compile(
    r"^\s*(?P<ansible_factor>\d+\.\d+):\s*SKIP_MOLECULE_SCENARIO\s*=\s*(?P<scenario_names>.*?)\s*$",
    re.MULTILINE,
)


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""

    if value[0] in {'"', "'"}:
        return value[1:-1]

    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "Null", "none", "None", "~"}:
        return None

    try:
        return int(value)
    except ValueError:
        pass

    try:
        return float(value)
    except ValueError:
        pass

    return value


def parse_simple_yaml(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line == "---":
            continue

        if raw_line[:1].isspace():
            raise ValueError(f"Unsupported nested YAML content: {raw_line}")

        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError(f"Unsupported YAML line: {raw_line}")

        data[key.strip()] = parse_scalar(value)

    return data


def load_github_config(scenario_dir: pathlib.Path) -> dict[str, Any]:
    for github_path in (scenario_dir / "github.yaml", scenario_dir / "github.yml"):
        if github_path.is_file():
            return parse_simple_yaml(github_path.read_text(encoding="utf-8"))

    return {}


def parse_py_envs(raw: str | None) -> list[str]:
    if raw is None:
        return discover_default_py_envs()

    py_envs: list[str] = []
    for part in raw.replace("\n", ",").split(","):
        py_env = part.strip()
        if py_env and py_env not in py_envs:
            py_envs.append(py_env)
    return py_envs


def discover_default_py_envs() -> list[str]:
    py_envs: list[str] = []

    for tox_ini_path in sorted(TOX_DIR.glob("py*/tox.ini"), key=lambda path: path.parent.name):
        py_env = tox_ini_path.parent.name
        if py_env not in py_envs:
            py_envs.append(py_env)

    return py_envs


def discover_scenarios() -> list[str]:
    scenarios: set[str] = set()
    for scenario_dir in PROJECT_ROOT.glob("molecule/core*/*"):
        if not scenario_dir.is_dir():
            continue
        scenario_name = scenario_dir.name
        if scenario_name.startswith("."):
            continue
        scenarios.add(scenario_name)
    return sorted(scenarios)


def to_core_name(ansible_factor: str) -> str:
    return f"core{ansible_factor.replace('.', '')}"


def to_pixi_python_env(py_factor: str) -> str:
    return py_factor.replace(".", "")


def to_ansible_factor(core_name: str) -> str:
    if not core_name.startswith("core"):
        raise ValueError(f"Unsupported core directory name: {core_name}")

    suffix = core_name.removeprefix("core")
    if not suffix.isdigit() or len(suffix) < 2:
        raise ValueError(f"Unsupported core directory name: {core_name}")

    return f"{int(suffix[0])}.{int(suffix[1:])}"


def discover_core_names_for_scenario(scenario_name: str) -> list[str]:
    core_names: list[str] = []

    for scenario_dir in sorted(PROJECT_ROOT.glob(f"molecule/core*/{scenario_name}")):
        if not scenario_dir.is_dir():
            continue
        core_name = scenario_dir.parent.name
        if core_name not in core_names:
            core_names.append(core_name)

    return core_names


def collect_skip_molecule_scenarios(tox_ini_text: str) -> dict[str, set[str]]:
    skip_molecule_scenarios: dict[str, set[str]] = {}

    for match in SKIP_MOLECULE_SCENARIO_RE.finditer(tox_ini_text):
        ansible_factor = match.group("ansible_factor")
        scenario_names = {
            scenario_name.strip()
            for scenario_name in match.group("scenario_names").split(",")
            if scenario_name.strip()
        }
        skip_molecule_scenarios.setdefault(ansible_factor, set()).update(scenario_names)

    return skip_molecule_scenarios


def collect_tox_envs(py_envs: list[str], ansible_factors: list[str], scenario_name: str) -> list[str]:
    tox_envs: list[str] = []

    for py_env in py_envs:
        tox_ini_path = TOX_DIR / py_env / "tox.ini"
        if not tox_ini_path.is_file():
            continue

        tox_ini_text = tox_ini_path.read_text(encoding="utf-8")
        skip_molecule_scenarios = collect_skip_molecule_scenarios(tox_ini_text)
        for match in TOX_ENVLIST_ITEM_RE.finditer(tox_ini_text):
            py_factor = match.group("py_factor")
            available_ansible_factors = [
                factor.strip() for factor in match.group("ansible_factors").split(",") if factor.strip()
            ]

            for ansible_factor in available_ansible_factors:
                if ansible_factor not in ansible_factors:
                    continue

                tox_env = f"molecule-{py_factor}-{ansible_factor}"
                if scenario_name in skip_molecule_scenarios.get(ansible_factor, set()):
                    continue

                if tox_env not in tox_envs:
                    tox_envs.append(tox_env)

    return tox_envs


def filter_tox_envs_for_scenario(scenario_name: str, py_envs: list[str]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    core_names = discover_core_names_for_scenario(scenario_name)
    ansible_factors = [to_ansible_factor(core_name) for core_name in core_names]
    tox_envs = collect_tox_envs(py_envs, ansible_factors, scenario_name)

    for tox_env in tox_envs:
        match = TOX_ENV_RE.match(tox_env)
        if match is None:
            continue

        py_factor = match.group("py_factor")
        ansible_factor = match.group("ansible_factor")
        core_name = to_core_name(ansible_factor)
        scenario_dir = PROJECT_ROOT / "molecule" / core_name / scenario_name

        if not scenario_dir.is_dir():
            continue

        entries.append(
            {
                "name": f"{scenario_name}@{tox_env}",
                "scenario_name": scenario_name,
                "tox_env": tox_env,
                "py_factor": py_factor,
                "pixi_py_env": to_pixi_python_env(py_factor),
                "ansible_factor": ansible_factor,
                "core_name": core_name,
                "scenario_dir": str(scenario_dir.relative_to(PROJECT_ROOT)),
                "github": load_github_config(scenario_dir),
            }
        )

    return entries


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate GitHub Actions matrix data from Molecule scenarios and tox envs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "discover-molecule-scenarios",
        help="Discover unique scenario names from molecule/*/*/molecule.yml.",
    )

    filter_parser = subparsers.add_parser(
        "filter-tox-envs",
        help="Filter tox envs for a single scenario name.",
    )
    filter_parser.add_argument("--scenario-name", required=True, help="Scenario name to filter for.")
    filter_parser.add_argument(
        "--py-envs",
        help=(
            "Comma-separated or newline-separated pixi Python environments used to run `tox -l`, "
            "default: discovered from tox/py*/tox.ini"
        ),
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.command == "discover-molecule-scenarios":
        print(json.dumps(discover_scenarios(), separators=(",", ":")))
        return 0

    if args.command == "filter-tox-envs":
        entries = filter_tox_envs_for_scenario(args.scenario_name, parse_py_envs(args.py_envs))
        print(json.dumps(entries, separators=(",", ":")))
        return 0

    raise AssertionError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
