#!/usr/bin/env python
"""Link this role into Molecule's ephemeral roles directory.

Molecule 2.x checks the Galaxy role name from meta/main.yml.  When the local
role directory name does not match ``author.role_name``, Ansible needs a role
path entry that points the Galaxy name back to this checkout.
"""

from __future__ import print_function

import os
import re
import sys


def fail(message):
    print("ERROR: {0}".format(message), file=sys.stderr)
    return 1


def read_galaxy_info(meta_file):
    if not os.path.isfile(meta_file):
        raise RuntimeError("meta file not found: {0}".format(meta_file))

    values = {}
    in_galaxy_info = False
    galaxy_indent = None
    key_pattern = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*):\s*(.*?)\s*$")

    with open(meta_file, "r") as stream:
        for line in stream:
            if not line.strip() or line.lstrip().startswith("#"):
                continue

            match = key_pattern.match(line)
            if not match:
                continue

            indent, key, value = match.groups()
            indent_len = len(indent)

            if key == "galaxy_info" and indent_len == 0:
                in_galaxy_info = True
                galaxy_indent = None
                continue

            if not in_galaxy_info:
                continue

            if indent_len == 0:
                break

            if galaxy_indent is None:
                galaxy_indent = indent_len

            if indent_len != galaxy_indent:
                continue

            if key in ("author", "role_name"):
                values[key] = value.strip("\"'")

    missing = [key for key in ("author", "role_name") if not values.get(key)]
    if missing:
        raise RuntimeError(
            "missing galaxy_info field(s) in {0}: {1}".format(
                meta_file, ", ".join(missing)
            )
        )

    return values


def molecule_ephemeral_directory(cache_home, project_name, scenario_name):
    override = os.environ.get("MOLECULE_EPHEMERAL_DIRECTORY")
    if override:
        return os.path.abspath(override)

    return os.path.abspath(
        os.path.join(cache_home, "molecule", project_name, scenario_name)
    )


def ensure_role_link(link_path, role_dir):
    parent = os.path.dirname(link_path)
    if not os.path.isdir(parent):
        os.makedirs(parent)

    if os.path.islink(link_path):
        current_target = os.readlink(link_path)
        current_path = os.path.abspath(os.path.join(parent, current_target))
        if current_path == role_dir:
            return "already linked"

        os.unlink(link_path)
    elif os.path.exists(link_path):
        raise RuntimeError(
            "refusing to replace non-symlink path: {0}".format(link_path)
        )

    os.symlink(role_dir, link_path)
    return "linked"


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    role_dir = os.path.abspath(os.path.join(script_dir, os.pardir, os.pardir))
    meta_file = os.path.join(role_dir, "meta", "main.yml")

    try:
        galaxy_info = read_galaxy_info(meta_file)
        scenario_name = os.environ.get("MOLECULE_SCENARIO_NAME", "default")
        cache_home = os.environ.get(
            "XDG_CACHE_HOME", os.path.expanduser(os.path.join("~", ".cache"))
        )
        project_name = os.path.basename(role_dir)
        role_name = "{0}.{1}".format(
            galaxy_info["author"], galaxy_info["role_name"]
        )
        ephemeral_dir = molecule_ephemeral_directory(
            cache_home, project_name, scenario_name
        )
        link_path = os.path.join(ephemeral_dir, "roles", role_name)
        result = ensure_role_link(link_path, role_dir)
    except Exception as exc:
        return fail(str(exc))

    print("{0}: {1} -> {2}".format(result, link_path, role_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
