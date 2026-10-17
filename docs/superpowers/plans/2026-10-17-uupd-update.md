# uupd-update (faithful Python port of the uupd front-end) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fork's 58-line bash `uupd-update` with a faithful, tested stdlib Python console script (`uupd-update`) packaged in the halcyon `python-packages` COPR repo and consumed by the halcyon image.

**Architecture:** One stdlib-only console script keeps the bash contract exactly: pick the already-running `uupd.service` (else `uupd-manual.service`, else start the manual one), stream its journal on stdout — the JSON-lines stream `ujust update` pipes to jq — and exit with the service's exit code. `systemctl`/`journalctl` are driven via `subprocess`; the journal child is stopped when the tool exits. The image keeps zero uupd-update logic: it installs the RPM from the `aahsnr-work/python-packages` Copr it already enables and repoints its just recipe at `/usr/bin/uupd-update`.

**Tech Stack:** Python 3.13, stdlib only; setuptools + pyproject; Fedora RPM (pyproject-rpm-macros); Copr; just/ujust.

**Spec:** No separate design doc — the approved conversation design of 2026-10-17 ("repeat the ublue-motd tasks", faithful behavior, complete control delegated) is restated in "Decisions locked" and "Review Focus" below. This plan mirrors `2026-10-17-ublue-motd.md`.

**Repos:**
- A (behavior + packaging): `~/Git/halcyon/copr/python-packages`.
- B (image payload): `~/Git/halcyon/bazzite-fork`.

## Decisions locked

- Faithful port of the bash script. Contract: `pick_target` prefers an active main service, then an active manual service, else targets `uupd-manual.service` with `needs_start=True`; attach streams `journalctl -u <svc> -f -o cat --synchronize-on-exit=yes` with `--since <InactiveExitTimestamp>` when attaching (read with `LC_ALL=C`) and `--lines=0` otherwise; `systemctl start --wait <svc>` in the start path (its exit code ignored, like the bash); poll `ActiveState` every 1 s when attaching; exit with `ExecMainStatus` (`""` ⇒ 0).
- Deliberate deviations from the bash, all narrower than the original: an empty `ActiveState` (missing unit / systemd unreachable) counts as not active — the bash treated `""` as active and would follow a nonexistent unit and poll forever; SIGTERM/SIGHUP stop the journal child and exit `128+signum` (the bash trapped EXIT/INT/TERM); SIGINT exits 130 after stopping the child; a `FileNotFoundError` (systemctl/journalctl absent) reports to stderr and exits 1 instead of bash's silent continue; a non-empty non-numeric `ExecMainStatus` exits 2 (bash `exit` semantics).
- stdout is inherited by the journal child: no Python buffering, no re-formatting. The `ujust update` jq filter in `10-update.just` stays as-is; only the script path changes.
- Package: `uupd-update`, module `uupd_update`, console script `/usr/bin/uupd-update`, first version 1.0.0, `Requires: systemd uupd`. No args beyond `--version`; root is not special-cased (faithful).
- The image keeps no copy of the script: `system_files/desktop/usr/libexec/uupd-update` is deleted.
- Non-goals: parsing or re-formatting the JSON stream, TUI/progress niceties, resume, cache files, locale handling, changing uupd's own units, non-login shells (irrelevant here).

## Global Constraints

- **Repo A: commit and push when tests pass — CI/Copr is the build.** **Repo B: edit only; do not commit or push** (main is a release branch; its push publishes the image and must wait until the `ublue-motd` **and** `uupd-update` Copr builds are green, or the image fails at the install step).
- **No local builds:** no `podman`, `rpmbuild`, `just build`. Validation is the unittest suite plus `ci/matrix.py --list`; Copr is the RPM build and CI is the image build.
- Both repos carry in-flight work (bazzite-fork: ~23 dirty paths; python-packages: clean at `73ddc0d` — re-check with `git status`). **Read every target file immediately before editing it; edit on top of the working tree, never from an earlier snapshot.**
- python-packages conventions: stdlib-only; `from __future__ import annotations`; 4-space indentation; unittest (never pytest); sources vendored under `pkgs/<pkg>/src/`; manual `Release: N%{?dist}` + written `%changelog`; never mention rpm macros textually in comments; `%pyproject_save_files -l <import-name>`; console script claimed explicitly in `%files`; `%define debug_package %{nil}`.
- Fork task ordering: **Tasks 4–5 assume the `ublue-motd` plan's fork tasks have run first** — they edit the same files (`10-update.just` is motd-independent, but `install-common-packages`, `verify`, `tree.list`, and `system_files-desktop.md` overlap).
- Python code must run on the CI runner's `python3` (ubuntu-latest) and Fedora — keep runtime syntax ≥3.10-compatible (`from __future__ import annotations` for annotations).
- No new dependencies: stdlib only; `systemd` and `uupd` are hard RPM `Requires`. `--synchronize-on-exit=yes` needs systemd ≥ 253 (F44 and CI are fine).
- Every test runs with: `cd ~/Git/halcyon/copr/python-packages && python3 -m unittest discover -s pkgs/uupd-update/src/tests -v`
- Repo A commit style: `feat: <summary>` single line; stage only the feature paths (never `git add -A`).

## Review Focus

1. Unit/systemd absent (empty `ActiveState`) → no infinite poll, no traceback; the start attempt fails gracefully and the tool exits 0 (same net effect as the bash's no-op path). (Task 1, Task 2)
2. Ctrl-C / SIGTERM / SIGHUP mid-update → the journal child is stopped; exit 130 / `128+signum`; no orphaned `journalctl`. (Task 2)
3. `systemctl` or `journalctl` missing on PATH → one clear stderr line, exit 1, no traceback. (Task 2)
4. Empty or garbage `ExecMainStatus` → `0` for empty, `2` for garbage (bash `exit` parity). (Task 1)
5. Attach vs start: `--since` is used only when attaching to an already-running service; the started service gets `--lines=0` (no old lines, none skipped after start). (Task 1, Task 2)

---

### Task 1: Package skeleton + static fact helpers (repo A)

**Files:**
- Create: `pkgs/uupd-update/src/pyproject.toml`
- Create: `pkgs/uupd-update/src/LICENSE` (copy of the repo root `LICENSE`)
- Create: `pkgs/uupd-update/src/src/uupd_update/__init__.py`
- Test: `pkgs/uupd-update/src/tests/test_uupd_update.py`

**Interfaces:**
- Consumes: nothing.
- Produces (used by Task 2 and by the tests): `MAIN_SERVICE = "uupd.service"`, `MANUAL_SERVICE = "uupd-manual.service"`, `INACTIVE_STATES = ("inactive", "failed", "")`, `__version__ = "1.0.0"`, `read_state(unit: str) -> str`, `inactive_exit_timestamp(unit: str) -> str`, `pick_target(main_state: str, manual_state: str) -> tuple[str, bool]`, `journal_args(unit: str, since: str) -> list[str]`, `exec_status(unit: str) -> str`, `exit_code(raw: str) -> int`.

- [x] **Step 1: Create the package skeleton**

```bash
cd ~/Git/halcyon/copr/python-packages
mkdir -p pkgs/uupd-update/src/src/uupd_update pkgs/uupd-update/src/tests
cp LICENSE pkgs/uupd-update/src/LICENSE
```

Write `pkgs/uupd-update/src/pyproject.toml` exactly:

```toml
[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[project]
name = "uupd-update"
version = "1.0.0"
description = "Front-end for uupd: attach to or start the update service, stream its journal, pass through its exit code."
requires-python = ">=3.13"
license = "Apache-2.0"

[project.scripts]
uupd-update = "uupd_update:main"

[tool.setuptools.packages.find]
where = ["src"]
```

- [x] **Step 2: Write the failing tests**

Create `pkgs/uupd-update/src/tests/test_uupd_update.py` exactly:

```python
"""Tests for the uupd-update package."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tomllib
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

import uupd_update


def require(name: str):
    value = getattr(uupd_update, name, None)
    if value is None:
        raise AssertionError(f"uupd_update.{name} is not implemented")
    return value


class PackageTests(unittest.TestCase):
    def test_package_exposes_only_uupd_update_command(self):
        project = tomllib.loads(
            (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
        )["project"]
        self.assertEqual(project["name"], "uupd-update")
        self.assertEqual(project["scripts"], {"uupd-update": "uupd_update:main"})

    def test_module_is_importable(self):
        self.assertIsNotNone(importlib.util.find_spec("uupd_update"))


class ReadStateTests(unittest.TestCase):
    def test_returns_stripped_state(self):
        with patch.object(uupd_update.subprocess, "run",
                          return_value=Mock(returncode=0, stdout="active\n")):
            self.assertEqual(require("read_state")("uupd.service"), "active")

    def test_failed_query_is_empty_state(self):
        with patch.object(uupd_update.subprocess, "run",
                          return_value=Mock(returncode=1, stdout="")):
            self.assertEqual(require("read_state")("uupd.service"), "")

    def test_queries_the_active_state_property(self):
        with patch.object(uupd_update.subprocess, "run",
                          return_value=Mock(returncode=0, stdout="inactive\n")) as run:
            require("read_state")("uupd-manual.service")
        self.assertEqual(
            run.call_args.args[0],
            ["systemctl", "show", "-p", "ActiveState", "--value", "uupd-manual.service"],
        )


class TimestampTests(unittest.TestCase):
    def test_returns_timestamp_and_forces_c_locale(self):
        with patch.object(uupd_update.subprocess, "run",
                          return_value=Mock(returncode=0,
                                            stdout="Mon 2026-10-17 10:00:00 UTC\n")) as run:
            self.assertEqual(require("inactive_exit_timestamp")("uupd.service"),
                             "Mon 2026-10-17 10:00:00 UTC")
        self.assertEqual(run.call_args.kwargs["env"]["LC_ALL"], "C")

    def test_failed_query_is_empty(self):
        with patch.object(uupd_update.subprocess, "run",
                          return_value=Mock(returncode=1, stdout="")):
            self.assertEqual(require("inactive_exit_timestamp")("uupd.service"), "")


class PickTargetTests(unittest.TestCase):
    def test_prefers_main_then_manual_then_starts_manual(self):
        pick = require("pick_target")
        self.assertEqual(pick("active", "inactive"), ("uupd.service", False))
        self.assertEqual(pick("activating", "inactive"), ("uupd.service", False))
        self.assertEqual(pick("inactive", "active"), ("uupd-manual.service", False))
        self.assertEqual(pick("failed", "deactivating"), ("uupd-manual.service", False))
        self.assertEqual(pick("failed", "inactive"), ("uupd-manual.service", True))

    def test_missing_services_are_treated_as_inactive(self):
        self.assertEqual(require("pick_target")("", ""), ("uupd-manual.service", True))
        self.assertEqual(require("pick_target")("", "active"), ("uupd-manual.service", False))


class JournalArgsTests(unittest.TestCase):
    def test_since_when_attaching_and_zero_lines_otherwise(self):
        args = require("journal_args")
        base = ["journalctl", "-u", "uupd.service", "-f", "-o", "cat",
                "--synchronize-on-exit=yes"]
        self.assertEqual(args("uupd.service", "Mon 2026-10-17 10:00:00 UTC"),
                         base + ["--since", "Mon 2026-10-17 10:00:00 UTC"])
        self.assertEqual(args("uupd.service", ""), base + ["--lines=0"])


class ExecStatusTests(unittest.TestCase):
    def test_returns_status_or_empty(self):
        with patch.object(uupd_update.subprocess, "run",
                          return_value=Mock(returncode=0, stdout="1\n")):
            self.assertEqual(require("exec_status")("uupd.service"), "1")
        with patch.object(uupd_update.subprocess, "run",
                          return_value=Mock(returncode=1, stdout="")):
            self.assertEqual(require("exec_status")("uupd.service"), "")


class ExitCodeTests(unittest.TestCase):
    def test_empty_is_success_numeric_passes_through_garbage_is_two(self):
        code = require("exit_code")
        self.assertEqual(code(""), 0)
        self.assertEqual(code("0"), 0)
        self.assertEqual(code("137"), 137)
        self.assertEqual(code("abc"), 2)


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 3: Run the tests to verify they fail**

Run: `cd ~/Git/halcyon/copr/python-packages && python3 -m unittest discover -s pkgs/uupd-update/src/tests -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'uupd_update'`.

- [x] **Step 4: Implement the static helpers in `pkgs/uupd-update/src/src/uupd_update/__init__.py` exactly**

```python
"""Front-end for uupd: attach to or start the update service and stream its journal."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time

MAIN_SERVICE = "uupd.service"
MANUAL_SERVICE = "uupd-manual.service"
INACTIVE_STATES = ("inactive", "failed", "")
__version__ = "1.0.0"


def read_state(unit: str) -> str:
    """ActiveState of unit; "" when the unit is unknown or systemctl fails."""
    result = subprocess.run(
        ["systemctl", "show", "-p", "ActiveState", "--value", unit],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def inactive_exit_timestamp(unit: str) -> str:
    """When the unit last started; "" when systemctl has nothing to report."""
    result = subprocess.run(
        ["systemctl", "show", "-p", "InactiveExitTimestamp", "--value", unit],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "LC_ALL": "C"},
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def pick_target(main_state: str, manual_state: str) -> tuple[str, bool]:
    """(service, needs_start): the first active service, else the manual service to start."""
    if main_state not in INACTIVE_STATES:
        return MAIN_SERVICE, False
    if manual_state not in INACTIVE_STATES:
        return MANUAL_SERVICE, False
    return MANUAL_SERVICE, True


def journal_args(unit: str, since: str) -> list[str]:
    args = ["journalctl", "-u", unit, "-f", "-o", "cat", "--synchronize-on-exit=yes"]
    if since:
        return args + ["--since", since]
    return args + ["--lines=0"]


def exec_status(unit: str) -> str:
    """ExecMainStatus of the finished unit; "" when systemctl has nothing to report."""
    result = subprocess.run(
        ["systemctl", "show", "-p", "ExecMainStatus", "--value", unit],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def exit_code(raw: str) -> int:
    """The service's status as our exit code; empty means success, garbage mirrors bash (2)."""
    if not raw:
        return 0
    try:
        return int(raw)
    except ValueError:
        return 2
```

- [x] **Step 5: Run the tests to verify they pass**

Run: `cd ~/Git/halcyon/copr/python-packages && python3 -m unittest discover -s pkgs/uupd-update/src/tests -v`
Expected: PASS (12 tests). The orchestration names are still missing — Task 2 adds them.

---

### Task 2: Journal streaming, service wait, CLI (repo A)

**Files:**
- Modify: `pkgs/uupd-update/src/src/uupd_update/__init__.py` (append)
- Modify: `pkgs/uupd-update/src/tests/test_uupd_update.py` (append)

**Interfaces:**
- Consumes: every name from Task 1.
- Produces (Task 3 packages these): `stream_journal(unit: str, since: str) -> subprocess.Popen`, `stop_journal(process) -> None`, `wait_for_service(unit: str, needs_start: bool) -> None`, `install_stop_handlers(process) -> None`, `main(argv: list[str] | None = None) -> int` (the console-script entry point).

- [x] **Step 1: Append the failing tests** to `test_uupd_update.py` (before the `if __name__ == "__main__":` block)

```python
class StreamJournalTests(unittest.TestCase):
    def test_spawns_journalctl_with_inherited_output(self):
        with patch.object(uupd_update.subprocess, "Popen", return_value=Mock()) as popen:
            process = require("stream_journal")("uupd.service", "")
        popen.assert_called_once_with(["journalctl", "-u", "uupd.service", "-f", "-o", "cat",
                                       "--synchronize-on-exit=yes", "--lines=0"])
        self.assertIs(process, popen.return_value)


class StopJournalTests(unittest.TestCase):
    def test_terminates_only_a_running_child(self):
        stop = require("stop_journal")
        running = Mock()
        running.poll.return_value = None
        stop(running)
        running.terminate.assert_called_once_with()
        exited = Mock()
        exited.poll.return_value = 1
        stop(exited)
        exited.terminate.assert_not_called()


class WaitServiceTests(unittest.TestCase):
    def test_start_wait_when_starting(self):
        with patch.object(uupd_update.subprocess, "run",
                          return_value=Mock(returncode=1)) as run:
            require("wait_for_service")("uupd-manual.service", True)
        self.assertEqual(run.call_args.args[0],
                         ["systemctl", "start", "--wait", "uupd-manual.service"])

    def test_polls_until_inactive_when_attaching(self):
        with patch.object(uupd_update, "read_state",
                          side_effect=["active", "active", "failed"]) as state, \
             patch.object(uupd_update.time, "sleep") as sleep:
            require("wait_for_service")("uupd.service", False)
        self.assertEqual(state.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_missing_state_does_not_spin(self):
        with patch.object(uupd_update, "read_state", return_value=""), \
             patch.object(uupd_update.time, "sleep") as sleep:
            require("wait_for_service")("uupd.service", False)
        sleep.assert_not_called()


class StopHandlersTests(unittest.TestCase):
    def test_handlers_stop_journal_and_exit_by_signal(self):
        handlers = {}

        def capture(sig, handler):
            handlers[sig] = handler

        with patch.object(uupd_update.signal, "signal", side_effect=capture), \
             patch.object(uupd_update, "stop_journal") as stop:
            require("install_stop_handlers")(Mock())
            self.assertEqual(set(handlers),
                             {uupd_update.signal.SIGTERM, uupd_update.signal.SIGHUP})
            for sig, handler in handlers.items():
                with self.assertRaises(SystemExit) as raised:
                    handler(sig, None)
                self.assertEqual(raised.exception.code, 128 + sig)
        self.assertEqual(stop.call_count, 2)


class MainTests(unittest.TestCase):
    def test_attach_reuses_running_service_and_passes_exit_code(self):
        with patch.object(uupd_update, "read_state", side_effect=["active", "inactive"]), \
             patch.object(uupd_update, "inactive_exit_timestamp", return_value="TS"), \
             patch.object(uupd_update, "stream_journal") as stream, \
             patch.object(uupd_update, "install_stop_handlers"), \
             patch.object(uupd_update, "wait_for_service") as wait, \
             patch.object(uupd_update, "exec_status", return_value="1"), \
             patch.object(uupd_update, "stop_journal") as stop:
            self.assertEqual(require("main")([]), 1)
        stream.assert_called_once_with("uupd.service", "TS")
        wait.assert_called_once_with("uupd.service", False)
        stop.assert_called_once_with(stream.return_value)

    def test_starts_manual_service_when_none_running(self):
        with patch.object(uupd_update, "read_state", side_effect=["inactive", "failed"]), \
             patch.object(uupd_update, "inactive_exit_timestamp") as timestamp, \
             patch.object(uupd_update, "stream_journal") as stream, \
             patch.object(uupd_update, "install_stop_handlers"), \
             patch.object(uupd_update, "wait_for_service") as wait, \
             patch.object(uupd_update, "exec_status", return_value="0"), \
             patch.object(uupd_update, "stop_journal"):
            self.assertEqual(require("main")([]), 0)
        timestamp.assert_not_called()
        stream.assert_called_once_with("uupd-manual.service", "")
        wait.assert_called_once_with("uupd-manual.service", True)

    def test_ctrl_c_returns_130_after_stopping_journal(self):
        with patch.object(uupd_update, "read_state", side_effect=["active", "inactive"]), \
             patch.object(uupd_update, "inactive_exit_timestamp", return_value="TS"), \
             patch.object(uupd_update, "stream_journal"), \
             patch.object(uupd_update, "install_stop_handlers"), \
             patch.object(uupd_update, "wait_for_service", side_effect=KeyboardInterrupt), \
             patch.object(uupd_update, "stop_journal") as stop:
            self.assertEqual(require("main")([]), 130)
        stop.assert_called_once()

    def test_missing_systemctl_reports_and_fails(self):
        with patch.object(uupd_update.subprocess, "run",
                          side_effect=FileNotFoundError("systemctl")), \
             patch.object(uupd_update, "stop_journal") as stop, \
             contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(require("main")([]), 1)
        self.assertTrue(err.getvalue())
        stop.assert_not_called()

    def test_version_flag_exits_zero(self):
        with contextlib.redirect_stdout(io.StringIO()) as out, \
             self.assertRaises(SystemExit) as raised:
            require("main")(["--version"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("uupd-update", out.getvalue())
```

- [x] **Step 2: Run the tests to verify the new ones fail**

Run: `cd ~/Git/halcyon/copr/python-packages && python3 -m unittest discover -s pkgs/uupd-update/src/tests -v`
Expected: FAIL — `AssertionError: uupd_update.stream_journal is not implemented` (and the other new names).

- [x] **Step 3: Append the orchestration to `__init__.py` exactly**

```python
def stream_journal(unit: str, since: str) -> subprocess.Popen:
    """Follow the unit's journal on our stdout/stderr; the child runs until stopped."""
    return subprocess.Popen(journal_args(unit, since))


def stop_journal(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()


def wait_for_service(unit: str, needs_start: bool) -> None:
    """Block until the service has finished: start --wait, or poll an attached one."""
    if needs_start:
        subprocess.run(["systemctl", "start", "--wait", unit], check=False)
        return
    while read_state(unit) not in INACTIVE_STATES:
        time.sleep(1)


def install_stop_handlers(process: subprocess.Popen) -> None:
    """SIGTERM/SIGHUP stop the journal child and exit by the signal, like the bash trap."""
    def stop(signum: int, _frame: object) -> None:
        stop_journal(process)
        raise SystemExit(128 + signum)

    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, stop)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="uupd-update", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.parse_args(argv)
    process = None
    try:
        target, needs_start = pick_target(read_state(MAIN_SERVICE), read_state(MANUAL_SERVICE))
        since = "" if needs_start else inactive_exit_timestamp(target)
        process = stream_journal(target, since)
        install_stop_handlers(process)
        wait_for_service(target, needs_start)
        return exit_code(exec_status(target))
    except FileNotFoundError as error:
        print(f"uupd-update: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    finally:
        if process is not None:
            stop_journal(process)
```

- [x] **Step 4: Run the full suite to verify it passes**

Run: `cd ~/Git/halcyon/copr/python-packages && python3 -m unittest discover -s pkgs/uupd-update/src/tests -v`
Expected: PASS, all tests (23 total).

---

### Task 3: Spec, registry, references, CI wiring, push (repo A)

**Files:**
- Create: `pkgs/uupd-update/uupd-update.spec`
- Create: `references/uupd-update` (copy of the fork's current script)
- Modify: `ci/packages.toml` (entry + header comment)
- Modify: `README.md` (table row)
- Modify: `.github/workflows/copr-build.yml` (test package list)

**Interfaces:**
- Consumes: binary `uupd-update` (Task 2), package name `uupd-update`.
- Produces: the installable RPM consumed by Task 4, and the pushed commit whose Copr build gates the fork.

- [x] **Step 1: Write `pkgs/uupd-update/uupd-update.spec` exactly**

```spec
# uupd-update: halcyon-original Python helper; sources vendored under
# pkgs/uupd-update/src (no upstream tarball exists). Submitted to Copr
# aahsnr-work/python-packages. Bumps are manual: edit Version + changelog,
# push, the cascade rebuilds.
%define debug_package %{nil}

Name:           uupd-update
Version:        1.0.0
Release:        1%{?dist}
Summary:        Front-end for uupd: attach to or start the update service, stream its journal.
License:        Apache-2.0
URL:            https://github.com/halcyon-linux/python-packages
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel
Requires:       systemd
Requires:       uupd

%description
Front-end for uupd on bootc images: attaches to a running uupd.service or
uupd-manual.service and streams its journal, or starts uupd-manual.service
and waits; exits with the service's exit code.

%prep
%autosetup -p1

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -l uupd_update
install -Dpm644 LICENSE %{buildroot}%{_licensedir}/%{name}/LICENSE

%files -f %pyproject_files
%license %{_licensedir}/%{name}/LICENSE
%{_bindir}/uupd-update

%changelog
* Sat Oct 17 2026 halcyon-autoupdate <aahsnr041@proton.me> - 1.0.0-1
- initial packaging (vendored halcyon-original sources)
```

- [x] **Step 2: Copy the original into `references/`** (the repo's porting convention: the bash source a Python tool replaces stays on record)

```bash
cd ~/Git/halcyon/copr/python-packages
cp ~/Git/halcyon/bazzite-fork/system_files/desktop/usr/libexec/uupd-update references/uupd-update
chmod +x references/uupd-update
```

- [x] **Step 3: Register the package in `ci/packages.toml`**

Append after the `[ublue-motd]` table (end of file):

```toml
[uupd-update]
batch = 0
```

Update the header comment: "The sixteen leaf packages are batch 0." → seventeen, and append `uupd-update` to the batch-0 name list in the comment.

- [x] **Step 4: Add the README table row** (after the `ublue-motd` row; pad the columns to match it)

```
| `uupd-update`      | `uupd-update`      | Front-end for `ujust update`: attach to or start the uupd service, stream its journal. |
```

- [x] **Step 5: Add the package to the CI test list**

In `.github/workflows/copr-build.yml`, the "Python package tests" step:

```yaml
for package in bbrew-helper brh bruh crh gameclass ublue-motd uupd-update; do
```

- [x] **Step 6: Validate locally — tests and registry (no RPM builds)**

```bash
cd ~/Git/halcyon/copr/python-packages
python3 -m unittest discover -s pkgs/uupd-update/src/tests -v
python3 ci/matrix.py --list
```

Expected: unittest PASS; `ci/matrix.py --list` shows `uupd-update` in the batch-0 output.

- [x] **Step 7: Commit and push repo A**

```bash
cd ~/Git/halcyon/copr/python-packages
git add pkgs/uupd-update ci/packages.toml README.md .github/workflows/copr-build.yml references/uupd-update
git status --short        # only the intended paths
git commit -m "feat: package uupd-update; faithful Python port of the uupd front-end"
git push origin main
```

If no Copr build appears within a few minutes (the cascade is gated on the `CASCADE_ENABLED` repository variable), dispatch `copr-build.yml` manually (workflow_dispatch bypasses the kill-switch). Task 4 must not reach a published image until this build is green, or the image fails at the install step.

---

### Task 4: Image switch — consume the package (repo B)

**Files:**
- Delete: `system_files/desktop/usr/libexec/uupd-update`
- Modify: `system_files/desktop/usr/share/ublue-os/just/10-update.just`
- Modify: `build_files/packages/install-common-packages`
- Modify: `build_files/finalization/verify`

**Interfaces:**
- Consumes: package `uupd-update` (Task 3), binary `/usr/bin/uupd-update` (same stdout contract as the bash script).
- Produces: `ujust update` running the packaged tool; the fork carries no copy of the script.

- [x] **Step 1: Delete the replaced script**

```bash
cd ~/Git/halcyon/bazzite-fork
rm system_files/desktop/usr/libexec/uupd-update
```

- [x] **Step 2: Repoint the `ujust update` recipe** in `10-update.just` — only the path changes; the jq pipeline is unchanged:

```
    /usr/bin/uupd-update | jq -r -R 'fromjson? | [(.title, .msg, .description) | select(.)] | join(" ")'
```

- [x] **Step 3: Install the package in the image**

In `build_files/packages/install-common-packages`, add `uupd-update` to the `common_packages=(...)` array immediately after the `ublue-motd` entry (the `ublue-motd` fork tasks add it after `uld`).

- [x] **Step 4: Require it in the build verification**

In `build_files/finalization/verify`, add `uupd-update` to the `verify_packages` `require_rpms` list, next to `ublue-motd`.

- [x] **Step 5: Verify the edits**

```bash
cd ~/Git/halcyon/bazzite-fork
bash -n build_files/packages/install-common-packages
bash -n build_files/finalization/verify
grep -rn "libexec/uupd-update" system_files/ build_files/ || true   # expect no hits
git diff --stat
```

Expected: both scripts parse; no `libexec/uupd-update` references remain in `system_files/` or `build_files/`; the diff touches only the intended files on top of the pre-existing user work.

---

### Task 5: Documentation maps + fork checks (repo B)

**Files:**
- Modify: `tree.list` (remove `uupd-update` under `usr/libexec`; re-glyph its new last sibling)
- Modify: `system_files-desktop.md` (move the `uupd-update` row; complete the RPM bookkeeping for `ublue-motd` too)

**Interfaces:**
- Consumes: Tasks 4 (and the `ublue-motd` fork tasks, which run first).
- Produces: maps that match the tree.

- [x] **Step 1: Update `tree.list`**

The tree's prefixes contain non-breaking spaces, so **do not retype lines** — transform them byte-for-byte with this script:

```bash
cd ~/Git/halcyon/bazzite-fork
python3 - <<'PY'
import pathlib

p = pathlib.Path("tree.list")
lines = p.read_text(encoding="utf-8").splitlines()

# 1) libexec: drop the uupd-update line (ublue-motd's line was dropped by the
#    ublue-motd plan; ntfs-exfat-monitor-script is the last remaining sibling)
lines.remove(next(l for l in lines if l.endswith("uupd-update")))

# 2) the new last libexec sibling gets the closing glyph
i = next(n for n, l in enumerate(lines) if l.endswith("ntfs-exfat-monitor-script"))
lines[i] = lines[i].replace("├──", "└──")

p.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
sed -n '155,162p' tree.list   # eyeball the libexec block
```

Expected: `libexec` ends with `bazzite-user-setup`, `force-wol`, `hwsupport/sysid`, then `ntfs-exfat-monitor-script` carrying `└──`; `ublue-motd` and `uupd-update` are both gone; glyph columns still line up.

- [x] **Step 2: Update `system_files-desktop.md`**

- Remove the `uupd-update` row from the `usr/libexec` table (the script no longer ships in `system_files`).
- In the `usr/bin` table, append the two now RPM-provided commands (matching the `brh` (RPM) row style):
  `| `ublue-motd` (RPM) | Python login banner: image info, boot health, staged updates, tips | ✅ |`
  `| `uupd-update` (RPM) | Front-end for `ujust update`: attach to or start the uupd service, stream its journal | ✅ |`
  (the `ublue-motd` fork tasks removed its libexec row but did not add this one — complete it here)
- Update the `usr/bin` section's count line: "5 commands are RPM-provided (brh, bruh, crh, gameclass, bbrew-helper)" → "7 commands are RPM-provided (brh, bruh, crh, gameclass, bbrew-helper, ublue-motd, uupd-update)".

- [x] **Step 3: Run the fork's own check**

```bash
cd ~/Git/halcyon/bazzite-fork
just just-check
```

Expected: every `.just` file and the `Justfile` pass `just --fmt --check` (no diff printed, exit 0).

- [x] **Step 4: Final sweep**

```bash
cd ~/Git/halcyon/bazzite-fork
grep -rn "libexec/uupd-update" . --exclude-dir=.git --exclude-dir=docs || true   # expect no hits
git status --short | head -30
```

Expected: no stale path references outside the plan docs; the working tree shows only intended changes on top of the pre-existing user work.

---

## Final verification (after all tasks)

- [x] Repo A: full unittest run passes (23/23); `ci/matrix.py --list` includes `uupd-update` (batch 0); `git status` clean; pushed as `6074473`.
- [x] Copr: builds for `ublue-motd` (id 11164455) and `uupd-update` (id 11164458) both `succeeded` on fc44 + fc45 (checked via the Copr API; the web page itself is behind Anubis here).
- [x] Repo B: `just just-check` passes; no `libexec/uupd-update` references remain; `tree.list` and `system_files-desktop.md` match the tree; the diff is minimal on top of the user's in-flight work.
- [x] Repo B push is deliberately **not** part of this plan (upheld: repo B stays uncommitted; the Copr gate above is now green and the human decides when to push).
- [ ] Manual smoke (once deployed) — not run here: needs a booted image.

## Follow-ups (not part of this plan)

- If the `--lines=0` race ever loses the first journal lines of a freshly started service, revisit attach timing (the bash had the identical race).
- If Copr fails resolving `python3dist(setuptools) >= 77` for the dynamic BuildRequires, compare with the `ublue-motd` build — same pattern, same fix.
