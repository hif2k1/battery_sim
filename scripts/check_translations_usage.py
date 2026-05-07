#!/usr/bin/env python3
"""Check translation key usage and duplicate JSON keys for battery_sim."""

from __future__ import annotations

import ast
import json
import pathlib
import re
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "battery_sim"
TRANSLATIONS = COMPONENT / "translations"
CONFIG_FLOW = COMPONENT / "config_flow.py"
CONSTS = COMPONENT / "const.py"


def parse_consts() -> dict[str, str]:
    consts: dict[str, str] = {}
    for line in CONSTS.read_text(encoding="utf-8").splitlines():
        match = re.match(r'([A-Z_]+)\s*=\s*"([^"]+)"', line)
        if match:
            consts[match.group(1)] = match.group(2)
    return consts


def resolve_const(name: str, consts: dict[str, str]) -> str:
    return consts.get(name, name)


def flatten_leaves(obj: Any, prefix: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    leaves: set[tuple[str, ...]] = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            leaves |= flatten_leaves(value, prefix + (key,))
    else:
        leaves.add(prefix)
    return leaves


def load_json_and_duplicates(path: pathlib.Path) -> tuple[dict[str, Any], list[str]]:
    duplicates: list[str] = []

    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        seen: set[str] = set()
        for key, value in pairs:
            if key in seen:
                duplicates.append(key)
            seen.add(key)
            out[key] = value
        return out

    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs_hook)
    return data, duplicates


def collect_used_paths() -> set[tuple[str, ...]]:
    consts = parse_consts()
    src = CONFIG_FLOW.read_text(encoding="utf-8")
    tree = ast.parse(src)

    step_ids: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {"async_show_form", "async_show_menu"}:
                for kw in node.keywords:
                    if (
                        kw.arg == "step_id"
                        and isinstance(kw.value, ast.Constant)
                        and isinstance(kw.value.value, str)
                    ):
                        step_ids.add(kw.value.value)

    used: set[tuple[str, ...]] = {
        ("config", "abort", "already_configured"),
        ("config", "flow_title"),
        ("config", "error", "invalid_input"),
    }

    for section in ("config", "options"):
        for step_id in step_ids:
            used.add((section, "step", step_id, "title"))
            used.add((section, "step", step_id, "description"))

    for opt in ("add_import_meter", "add_export_meter", "all_done"):
        used.add(("config", "step", "meter_menu", "menu_options", opt))
    for opt in ("no_tariff_info", "fixed_tariff", "tariff_sensor"):
        used.add(("config", "step", "tariff_menu", "menu_options", opt))
        used.add(("options", "step", "tariff_menu", "menu_options", opt))
    for opt in ("main_params", "input_sensors", "all_done"):
        used.add(("options", "step", "init", "menu_options", opt))
    for opt in ("add_import_meter", "add_export_meter", "edit_input_tariff", "delete_input"):
        used.add(("options", "step", "input_sensors", "menu_options", opt))

    step_fields = {
        ("config", "user"): ["BATTERY_TYPE"],
        ("config", "custom"): [
            "CONF_UNIQUE_NAME",
            "CONF_BATTERY_SIZE",
            "CONF_BATTERY_MAX_DISCHARGE_RATE",
            "CONF_BATTERY_MAX_CHARGE_RATE",
            "CONF_BATTERY_DISCHARGE_EFFICIENCY",
            "CONF_BATTERY_CHARGE_EFFICIENCY",
            "CONF_RATED_BATTERY_CYCLES",
            "CONF_END_OF_LIFE_DEGRADATION",
            "CONF_UPDATE_FREQUENCY",
        ],
        ("config", "add_import_meter"): ["SENSOR_ID"],
        ("config", "add_export_meter"): ["SENSOR_ID"],
        ("config", "fixed_tariff"): ["FIXED_TARIFF"],
        ("config", "tariff_sensor"): ["TARIFF_SENSOR"],
        ("options", "main_params"): [
            "CONF_BATTERY_SIZE",
            "CONF_BATTERY_MAX_DISCHARGE_RATE",
            "CONF_BATTERY_MAX_CHARGE_RATE",
            "CONF_BATTERY_DISCHARGE_EFFICIENCY",
            "CONF_BATTERY_CHARGE_EFFICIENCY",
            "CONF_RATED_BATTERY_CYCLES",
            "CONF_END_OF_LIFE_DEGRADATION",
            "CONF_UPDATE_FREQUENCY",
        ],
        ("options", "add_import_meter"): ["SENSOR_ID"],
        ("options", "add_export_meter"): ["SENSOR_ID"],
        ("options", "fixed_tariff"): ["FIXED_TARIFF"],
        ("options", "tariff_sensor"): ["TARIFF_SENSOR"],
        ("options", "delete_input"): ["CONF_INPUT_LIST"],
        ("options", "edit_input_tariff"): ["CONF_INPUT_LIST"],
    }

    for (section, step_id), fields in step_fields.items():
        for field in fields:
            used.add((section, "step", step_id, "data", resolve_const(field, consts)))

    for svc in ("set_battery_charge_state", "set_battery_cycles"):
        used.add(("services", svc, "name"))
        used.add(("services", svc, "description"))

    for svc, field in (
        ("set_battery_charge_state", "device_id"),
        ("set_battery_charge_state", "charge_state"),
        ("set_battery_cycles", "device_id"),
        ("set_battery_cycles", "battery_cycles"),
    ):
        used.add(("services", svc, "fields", field, "name"))
        used.add(("services", svc, "fields", field, "description"))

    return used


def main() -> int:
    used = collect_used_paths()
    any_problem = False

    for path in sorted(TRANSLATIONS.glob("*.json")):
        data, duplicates = load_json_and_duplicates(path)
        leaves = flatten_leaves(data)
        unused = sorted(".".join(p) for p in leaves - used)
        missing = sorted(".".join(p) for p in used - leaves)

        print(f"{path.name}:")
        print(f"  duplicate keys: {len(duplicates)}")
        print(f"  unused leaf keys: {len(unused)}")
        print(f"  missing used keys: {len(missing)}")

        if duplicates:
            any_problem = True
            print("  duplicate key names:")
            for d in duplicates:
                print(f"    - {d}")

        if unused:
            any_problem = True
            print("  unused keys:")
            for u in unused:
                print(f"    - {u}")

        if missing:
            any_problem = True
            print("  missing keys:")
            for m in missing:
                print(f"    - {m}")

    return 1 if any_problem else 0


if __name__ == "__main__":
    raise SystemExit(main())
