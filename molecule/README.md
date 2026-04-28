# Molecule

## [[role_name_check|Disable name check]]

All Molecule tests reference the role using the `role_name` and `author`
values from `meta/main.yml`. If either value is missing, the generated role
FQRN will not contain the `.` separator. This usually causes validation to fail
and stops the test run. Setting `role_name_check` can skip the check or ignore
the error, but this may not work correctly in some older `ansible-compat`
versions. Because of that, this project's Molecule scenarios try to set both
values whenever possible.

This is because `ansible_compat` derives the role FQRN as either
`{namespace}.{role_name}` or `{author}.{role_name}`. If `namespace` or
`author` is missing or contains spaces, the derived FQRN becomes only
`{role_name}`.

If `role_name` is missing, `ansible_compat` falls back to the role directory
name:

- With `role_name_check=1`, it removes `ansible-` from the directory name and
  extracts the part after the `.`.
- With `role_name_check=2`, it uses the directory name directly.

Because directory names may change, using the directory name as `role_name` is
not a stable choice.

All Molecule configs in this project set `role_name_check=1` to skip the
check. Validation failures are reported as warnings instead of stopping the
test run. This works correctly with `ansible-compat >= v2.1.0`. In versions
`>= v1.0.0, < v2.1.0`, which are usually only used in Python 3.5
environments, [ansible-compat issue #78](https://github.com/ansible/ansible-compat/issues/78)
causes `role_name_check` to always behave as `0`, so validation failures still
stop the test run.

## [[driver_default|Default driver name]]

Starting with v6.0.0, the default driver name changed from `delegated` to `default`.

## [[glob_notwork|MOLECULE_GLOB not work]]

Versions from v6.0.0 to v24.7.0 cannot change the glob pattern using `MOLECULE_GLOB`.

This will affect the `list` command, but not the `test` command.
