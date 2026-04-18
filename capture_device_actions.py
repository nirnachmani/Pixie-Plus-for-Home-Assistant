#!/usr/bin/env python3
"""Interactive Pixie device data and action capture tool.

This script:
- logs in with user-supplied credentials
- starts the existing local control/inventory flow
- writes a sanitized report without credentials or home/account identifiers
- lets the user record manual actions per device while live hub updates arrive
"""

from __future__ import annotations

import argparse
import getpass
import json
import threading
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pixie_auth_handler import PixieAuthError, PixieAuthHandler


def _json_safe(value: Any) -> Any:
    """Convert dataclass-heavy runtime structures into JSON-safe values."""
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _sanitize_runtime(runtime: Any) -> Dict[str, Any]:
    return {
        "presence": getattr(runtime, "presence", None),
        "online": _json_safe(getattr(runtime, "online", None)),
        "br": getattr(runtime, "br", None),
        "rgb": _json_safe(getattr(runtime, "rgb", None)),
        "effect": getattr(runtime, "effect", None),
        "effect_speed": getattr(runtime, "effect_speed", None),
        "r": getattr(runtime, "r", None),
        "last_source": getattr(runtime, "last_source", None),
        "last_updated_ms": getattr(runtime, "last_updated_ms", None),
        "raw": _json_safe(getattr(runtime, "raw", {})),
    }


def _sanitize_device(rec: Any) -> Dict[str, Any]:
    return {
        "id": getattr(rec, "id", None),
        "name": getattr(rec, "name", None),
        "model_no": getattr(rec, "model_no", None),
        "type": getattr(rec, "type", None),
        "stype": getattr(rec, "stype", None),
        "version": getattr(rec, "version", None),
        "left_name": getattr(rec, "left_name", None),
        "right_name": getattr(rec, "right_name", None),
        "rooms": _json_safe(getattr(rec, "rooms", [])),
        "import_mode": getattr(rec, "import_mode", None),
        "profile_state_raw": _json_safe(getattr(rec, "profile_state_raw", {})),
        "runtime": _sanitize_runtime(getattr(rec, "runtime", None)),
    }


def _upsert_device_user_details(report: Dict[str, Any], device_id: int, details: Dict[str, Any]) -> None:
    devices = report.get("devices", [])
    for device in devices:
        if device.get("id") == device_id:
            device["user_provided"] = dict(details)
            return


def _prompt_device_user_details(rec: Any, existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    existing = dict(existing or {})

    default_name = existing.get("device_name") or ""
    default_model = existing.get("device_model") or ""
    default_description = existing.get("device_description") or ""

    print("Record the official Pixie Plus product details for this device.")
    print("Do not enter the custom name the user gave the device in the app.")
    print(f"Current user-assigned device name: {getattr(rec, 'name', '')}")
    print("Examples: name='Smart dimmer G3', model='SDD300BTAM', description='a light dimmer'")
    print("Press Enter to keep the shown default.")

    device_name = input(f"  Official Pixie Plus product name [{default_name}]: ").strip() or default_name
    device_model = input(f"  Official Pixie Plus model [{default_model}]: ").strip() or default_model
    device_description = input(f"  Device description/type [{default_description}]: ").strip() or default_description

    return {
        "device_name": device_name,
        "device_model": device_model,
        "device_description": device_description,
    }


def _device_runtime_digest(rec: Any) -> Dict[str, Any]:
    runtime = getattr(rec, "runtime", None)
    return {
        "presence": getattr(runtime, "presence", None),
        "online": _json_safe(getattr(runtime, "online", None)),
        "br": getattr(runtime, "br", None),
        "rgb": _json_safe(getattr(runtime, "rgb", None)),
        "effect": getattr(runtime, "effect", None),
        "effect_speed": getattr(runtime, "effect_speed", None),
        "r": getattr(runtime, "r", None),
        "last_source": getattr(runtime, "last_source", None),
        "last_updated_ms": getattr(runtime, "last_updated_ms", None),
        "raw": _json_safe(getattr(runtime, "raw", {})),
    }


def _diff_values(before: Any, after: Any) -> Any:
    if isinstance(before, dict) and isinstance(after, dict):
        keys = sorted(set(before.keys()) | set(after.keys()))
        diff: Dict[str, Any] = {}
        for key in keys:
            before_val = before.get(key)
            after_val = after.get(key)
            if before_val == after_val:
                continue
            nested = _diff_values(before_val, after_val)
            diff[key] = nested
        return diff
    return {"before": before, "after": after}


class CaptureSession:
    def __init__(self, handler: PixieAuthHandler, sync_timeout: float, hub_ip: Optional[str]) -> None:
        self.handler = handler
        self.sync_timeout = sync_timeout
        self.hub_ip = hub_ip
        self.stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._result: Optional[Dict[str, Any]] = None
        self._error: Optional[BaseException] = None

    def start(self, username: str, password: str, *, login_required: bool = True) -> None:
        def _runner() -> None:
            try:
                self._result = self.handler.discover_and_connect(
                    username,
                    password,
                    hub_ip=self.hub_ip,
                    login_required=login_required,
                    sync_timeout=self.sync_timeout,
                    stop_event=self.stop_event,
                )
            except BaseException as exc:  # surfaced to caller after join/poll
                self._error = exc

        self._thread = threading.Thread(target=_runner, name="pixie-capture-session", daemon=True)
        self._thread.start()

    def wait_for_inventory(self, timeout: float) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._error is not None:
                raise self._error
            if self.handler.inventory is not None:
                return
            if self._thread is not None and not self._thread.is_alive() and self.handler.inventory is None:
                break
            time.sleep(0.1)
        if self._error is not None:
            raise self._error
        raise PixieAuthError("Timed out waiting for inventory/control session to initialize")

    def stop(self) -> None:
        self.stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def capture_action(self, device_id: int, action_label: str, capture_seconds: float, poll_interval: float) -> Dict[str, Any]:
        if self.handler.inventory is None:
            raise PixieAuthError("Inventory not available")

        baseline_inventory = self.handler.inventory.devices_by_id
        if device_id not in baseline_inventory:
            raise PixieAuthError(f"Unknown device id: {device_id}")

        before_target = _sanitize_device(baseline_inventory[device_id])
        device_last_seen: Dict[int, Optional[int]] = {
            dev_id: getattr(rec.runtime, "last_updated_ms", None)
            for dev_id, rec in baseline_inventory.items()
        }
        change_events: List[Dict[str, Any]] = []
        window_start = time.time()
        deadline = window_start + capture_seconds

        while time.time() < deadline:
            inventory = self.handler.inventory
            if inventory is None:
                time.sleep(poll_interval)
                continue

            for dev_id, rec in inventory.devices_by_id.items():
                current_ts = getattr(rec.runtime, "last_updated_ms", None)
                if current_ts is None:
                    continue
                previous_ts = device_last_seen.get(dev_id)
                if previous_ts is not None and current_ts <= previous_ts:
                    continue

                device_last_seen[dev_id] = current_ts
                change_events.append({
                    "t_offset_ms": int((time.time() - window_start) * 1000),
                    "device_id": dev_id,
                    "name": getattr(rec, "name", None),
                    "model_no": getattr(rec, "model_no", None),
                    "runtime": _device_runtime_digest(rec),
                })
            time.sleep(poll_interval)

        after_inventory = self.handler.inventory.devices_by_id if self.handler.inventory else {}
        after_target = _sanitize_device(after_inventory[device_id]) if device_id in after_inventory else None
        target_diff = _diff_values(before_target.get("runtime", {}), after_target.get("runtime", {})) if after_target else {}

        return {
            "device_id": device_id,
            "action": action_label,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "capture_seconds": capture_seconds,
            "before": before_target,
            "after": after_target,
            "target_runtime_diff": target_diff,
            "change_events": change_events,
        }


def _render_report(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("Pixie Device Capture Report")
    lines.append("=" * 80)
    lines.append(f"Generated UTC: {report['generated_at_utc']}")
    lines.append("")
    lines.append("Notes")
    lines.append("- This file intentionally excludes credentials, account ids, home ids, session tokens, net ids, mesh values, and hub IPs.")
    lines.append("- Device metadata and captured live runtime updates are included for reverse-engineering only.")
    lines.append("")
    lines.append("Devices")
    lines.append("-" * 80)
    for device in report.get("devices", []):
        lines.append(json.dumps(device, ensure_ascii=True, indent=2, sort_keys=True))
        lines.append("")

    lines.append("Captured Actions")
    lines.append("-" * 80)
    actions = report.get("actions", [])
    if not actions:
        lines.append("No actions were recorded.")
    else:
        for index, action in enumerate(actions, start=1):
            lines.append(f"Action #{index}")
            lines.append(json.dumps(action, ensure_ascii=True, indent=2, sort_keys=True))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _print_device_list(handler: PixieAuthHandler) -> None:
    inventory = handler.inventory
    if inventory is None:
        return
    print("\nAvailable devices:")
    print(f"  {'ID':>4}  {'Model':<8}  Name")
    print("  " + "-" * 60)
    for dev_id in sorted(inventory.devices_by_id.keys()):
        rec = inventory.devices_by_id[dev_id]
        model = rec.model_no if rec.model_no else "unknown"
        print(f"  {rec.id:>4}  {model:<8}  {rec.name}")


def _is_valid_login_config(config: Dict[str, Any]) -> bool:
    """Treat cloud login as valid only when key identity/session fields exist."""
    if not isinstance(config, dict):
        return False

    required_keys = ("userid", "homeid", "sessiontoken")
    for key in required_keys:
        value = config.get(key)
        if value in (None, "", "unknown"):
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture sanitized Pixie device data and manual action traces")
    parser.add_argument("--username", help="Pixie Plus username/email. If omitted, you will be prompted.")
    parser.add_argument("--password", help="Pixie Plus password. If omitted, you will be prompted securely.")
    parser.add_argument("--hub-ip", help="Optional hub IP. If omitted, LAN discovery is used.")
    parser.add_argument("--sync-timeout", type=float, default=5.0, help="Timeout for local sync/control startup")
    parser.add_argument("--startup-timeout", type=float, default=30.0, help="Seconds to wait for inventory startup")
    parser.add_argument("--capture-seconds", type=float, default=8.0, help="Seconds to capture updates after each armed action")
    parser.add_argument("--poll-interval", type=float, default=0.1, help="Polling interval for runtime change capture")
    parser.add_argument("--output", type=str, default=None, help="Output report path. Default: capture_report_<utc>.txt")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose protocol logging from PixieAuthHandler")
    args = parser.parse_args()

    username = args.username or input("Pixie username/email: ").strip()
    if not username:
        print("Username is required.")
        return 1

    password = args.password or ""

    output_path = Path(args.output) if args.output else Path(
        f"capture_report_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.txt"
    )

    handler = PixieAuthHandler(verbose=bool(args.verbose))
    handler.dump_structures = False
    handler.suppress_heartbeat_logs = True

    # Explicitly validate cloud credentials before starting LAN scan/handshake.
    while True:
        if not password:
            password = getpass.getpass("Pixie password: ")
        if not password:
            print("Password is required.")
            continue

        cfg = handler._fetch_login_data(username, password, include_inventory_seed=False)
        if _is_valid_login_config(cfg):
            handler.netid_seed = cfg.get("netid")
            handler.meshnet = cfg.get("meshnet")
            handler.meshnet2 = cfg.get("meshnet2")
            handler.home_id = cfg.get("homeid")
            handler.user_id = cfg.get("userid")
            handler.session_token = cfg.get("sessiontoken")
            handler.stored_username = username
            handler.stored_password = password
            break

        print("\nLogin failed: invalid username/password. Please try again.\n")
        password = ""

    session = CaptureSession(handler=handler, sync_timeout=float(args.sync_timeout), hub_ip=args.hub_ip)
    report: Dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "devices": [],
        "actions": [],
    }
    device_user_details: Dict[int, Dict[str, Any]] = {}

    try:
        print("\nStarting Pixie session and building inventory...")
        session.start(username, password, login_required=False)
        session.wait_for_inventory(timeout=float(args.startup_timeout))

        if handler.inventory is None:
            raise PixieAuthError("Inventory did not initialize")

        report["devices"] = [
            _sanitize_device(handler.inventory.devices_by_id[dev_id])
            for dev_id in sorted(handler.inventory.devices_by_id.keys())
        ]

        print("\nInventory ready.")
        _print_device_list(handler)
        print("\nCommands: enter a device id, 'list' to show devices again, or 'done' to finish.")

        should_exit = False
        while True:
            choice = input("\nDevice id / list / done: ").strip().lower()
            if choice == "done":
                break
            if choice == "list":
                _print_device_list(handler)
                continue
            if not choice:
                continue
            try:
                device_id = int(choice)
            except ValueError:
                print("Please enter a numeric device id, 'list', or 'done'.")
                continue

            inventory = handler.inventory
            if inventory is None or device_id not in inventory.devices_by_id:
                print(f"Unknown device id: {device_id}")
                continue

            rec = inventory.devices_by_id[device_id]
            print(f"Selected device {rec.id}: model={rec.model_no} name={rec.name}")

            details = _prompt_device_user_details(rec, device_user_details.get(device_id))
            device_user_details[device_id] = details
            _upsert_device_user_details(report, device_id, details)

            while True:
                action_label = input(
                    "Describe the action to capture (blank to choose another device, 'done' to finish): "
                ).strip()
                if not action_label:
                    break
                if action_label.lower() == "done":
                    should_exit = True
                    break

                print(
                    "Arm capture, then perform the action within the capture window.\n"
                    f"The script will watch for updates for {float(args.capture_seconds):.1f} seconds."
                )
                input("Press Enter to start capture...")
                print("Capture active. Perform the action now.")
                action_result = session.capture_action(
                    device_id=device_id,
                    action_label=action_label,
                    capture_seconds=float(args.capture_seconds),
                    poll_interval=float(args.poll_interval),
                )
                report["actions"].append(action_result)

                diff_keys = []
                target_diff = action_result.get("target_runtime_diff") or {}
                if isinstance(target_diff, dict):
                    diff_keys = sorted(target_diff.keys())
                print(
                    "Capture stored: events={events} changed_fields={fields}".format(
                        events=len(action_result.get("change_events", [])),
                        fields=diff_keys or ["none"],
                    )
                )

            if should_exit:
                break

        report_text = _render_report(report)
        output_path.write_text(report_text, encoding="utf-8")
        print(f"\nReport written to: {output_path}")
        print("Review the file before sending it on.")
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130
    except Exception as exc:
        print(f"\nCapture failed: {exc}")
        return 1
    finally:
        try:
            session.stop()
        except KeyboardInterrupt:
            # Ignore Ctrl+C during shutdown join so we can exit cleanly.
            pass


if __name__ == "__main__":
    raise SystemExit(main())