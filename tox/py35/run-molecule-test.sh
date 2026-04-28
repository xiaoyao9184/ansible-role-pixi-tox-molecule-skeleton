#!/usr/bin/env bash
set -euo pipefail

scenario_name="${MOLECULE_SCENARIO_NAME:-default}"
skip_scenarios="${SKIP_MOLECULE_SCENARIO:-}"
check_only=false

if [[ "${1:-}" == "--check-only" ]]; then
    check_only=true
    shift
fi

if [[ -n "${skip_scenarios}" ]]; then
    normalized_skip_scenarios="${skip_scenarios//,/ }"
    normalized_skip_scenarios="${normalized_skip_scenarios//:/ }"

    for skip_scenario in ${normalized_skip_scenarios}; do
        if [[ "${scenario_name}" == "${skip_scenario}" ]]; then
            echo "Skipping molecule scenario '${scenario_name}' because it is listed in SKIP_MOLECULE_SCENARIO."
            if [[ "${check_only}" == true ]]; then
                echo "__TOX_SKIP__"
                exit 99
            fi
            exit 0
        fi
    done
fi

if [[ "${check_only}" == true ]]; then
    exit 0
fi

exec molecule "$@"
