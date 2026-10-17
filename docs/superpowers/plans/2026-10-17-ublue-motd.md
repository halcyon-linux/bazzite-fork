# ublue-motd (comprehensive Python MOTD) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fork's 10-line sh MOTD with a comprehensive, fast Python tool (`ublue-motd`) packaged in the halcyon `python-packages` COPR repo and consumed by the halcyon image.

**Architecture:** One stdlib-only Python console script renders a markdown banner: it reads `image-info.json`, greenboot boot status, staged `rpm-ostree` deployments, root disk pressure, the running kernel and NVIDIA driver, and a rotating tip; substitutes a template with `string.Template.safe_substitute`; pipes the result through `glow` (raw markdown when glow or a TTY is absent). The image keeps ownership of the visible content (template + tips under `/usr/share/ublue-os/motd/`); the package owns behavior. The image installs the RPM from the `aahsnr-work/python-packages` Copr it already enables.

**Tech Stack:** Python 3.13, stdlib only; setuptools + pyproject; Fedora RPM (pyproject-rpm-macros); Copr; just/ujust; fish.

**Spec:** No separate design doc — the approved conversation design of 2026-10-17 is restated in "Decisions locked" and "Review Focus" below.

**Repos:**
- A (behavior + packaging): `~/Git/halcyon/copr/python-packages` (the user said `~/Git/halcyon/python-packages`; the real COPR repo is under `copr/`).
- B (image payload): `~/Git/halcyon/bazzite-fork`.

## Decisions locked

- Banner = title + `image:branch` (+ `(build N)`) + conditional status lines + kernel/NVIDIA line + commands table + random tip + links.
- Status lines, each emitted only when true: greenboot health; staged update → "reboot to apply"; root disk ≥90% full.
- Facts come only from fast local reads plus one `rpm-ostree status --json` subprocess (1.5 s timeout; failure ⇒ line omitted).
- The tool owns enable/disable: `ublue-motd toggle` flips `~/.config/no-show-user-motd` (the same file the fish greeting historically checked). No args renders the banner; root is skipped (prints nothing).
- Login shells show the banner in every shell: fish via `fish_greeting`, bash and zsh via `/etc/profile.d/user-motd.sh` (Bazzite's existing hook — the fork overrides that file to call `/usr/bin/ublue-motd`). The shell layer only guards interactivity and a TTY; the tool owns the disable flag and the root skip.
- glow renders when present and stdout is a TTY (`-w <cols>`); otherwise raw markdown to stdout. Missing template ⇒ built-in fallback template. Unknown `${VARS}` survive (`safe_substitute`).
- Content is image-owned: `template.md` + `tips/*.md`, one tip per line. No locale handling; English only.
- Package: `ublue-motd`, module `ublue_motd`, console script `/usr/bin/ublue-motd`, first version 1.0.0, `Requires: glow rpm-ostree`.
- Template variables: `MOTD_IMAGE_NAME`, `MOTD_IMAGE_BRANCH`, `MOTD_IMAGE_BUILD`, `MOTD_STATUS`, `MOTD_SYSTEM`, `MOTD_TIP`.
- Non-goals: locale translations, glow themes, Flatpak counts, network update checks, cache files or systemd units, non-login interactive shells (same limitation as upstream Bazzite).

## Global Constraints

- **Do not commit or push anything.** The human reviews and commits; standing rule.
- Both repos carry uncommitted in-flight work (bazzite-fork: 23 dirty paths; python-packages: untracked `TODO.md` + `references/`). **Read every target file immediately before editing it; edit on top of the working tree, never from an earlier snapshot.**
- python-packages conventions: stdlib-only; `from __future__ import annotations`; 4-space indentation; unittest (never pytest); sources vendored under `pkgs/<pkg>/src/`; manual `Release: N%{?dist}` + written `%changelog`; never mention rpm macros textually in comments; `%pyproject_save_files -l <import-name>`; console script claimed explicitly in `%files`; `%define debug_package %{nil}`.
- fork conventions: content under `/usr` only; keep the file-local indentation style (the fish function uses tabs).
- Python code must run on the CI runner's `python3` (ubuntu-latest) and Fedora — keep runtime syntax ≥3.10-compatible (`from __future__ import annotations` for annotations).
- No new dependencies. `glow` and `rpm-ostree` are hard RPM `Requires`; `glow` is a Fedora package (2.1.2 in F44).
- Every test runs with: `cd ~/Git/halcyon/copr/python-packages && python3 -m unittest discover -s pkgs/ublue-motd/src/tests -v`

## Review Focus

1. Missing/corrupt `image-info.json` → banner still renders with blank fields, exit 0. (Task 1, Task 2)
2. `rpm-ostree` missing, slow, or erroring → update line omitted; render never hangs; timeout pinned by test. (Task 1)
3. Non-TTY stdout or missing `glow` → plain markdown to stdout, no traceback, exit 0. (Task 2)
4. `HOME`/`XDG_CONFIG_HOME` unset → flag check silent (no flag), `toggle` fails with a clear message and exit 1, never creates a literal `~` dir. (Task 2)
5. Missing/empty tips dir, empty or missing template, unknown `${VAR}` in template → omissions only, never an exception. (Task 1, Task 2)

---

### Task 1: Package skeleton + fact gathering (repo A)

**Files:**
- Create: `pkgs/ublue-motd/src/pyproject.toml`
- Create: `pkgs/ublue-motd/src/src/ublue_motd/__init__.py`
- Create: `pkgs/ublue-motd/src/tests/test_ublue_motd.py`
- Copy: `pkgs/dump-to-markdown/src/LICENSE` → `pkgs/ublue-motd/src/LICENSE`

**Interfaces — produces (Task 2 consumes all of these):**

```python
IMAGE_INFO_FILE = Path("/usr/share/ublue-os/image-info.json")
TEMPLATE_FILE = Path("/usr/share/ublue-os/motd/template.md")
TIPS_DIR = Path("/usr/share/ublue-os/motd/tips")
BOOT_STATUS_FILE = Path("/etc/motd.d/boot-status")
NVIDIA_VERSION_FILE = Path("/proc/driver/nvidia/version")
RPM_OSTREE_TIMEOUT = 1.5
DISK_WARN_PERCENT = 90
__version__ = "1.0.0"

def read_image_info(path: Path) -> dict[str, str]   # {} on any failure
def strip_image_ref(ref: str) -> str                 # removes "ostree-image-signed:docker://"
def boot_status_lines(path: Path) -> list[str]       # [] | ["󰟀 `...`"]
def rpm_ostree_status(timeout: float = RPM_OSTREE_TIMEOUT) -> str
def staged_update_lines(raw: str) -> list[str]
def disk_usage_percent(path: str = "/") -> int       # df semantics, 0..100
def disk_lines(percent: int) -> list[str]
def nvidia_version(path: Path) -> str                # "" when absent/unparseable
def system_line(kernel: str, nvidia: str) -> str
def pick_tip(tips_dir: Path) -> str                  # "" when nothing to pick
```

- [x] **Step 1: Create the tree and copy the license**

```bash
cd ~/Git/halcyon/copr/python-packages
mkdir -p pkgs/ublue-motd/src/src/ublue_motd pkgs/ublue-motd/src/tests
cp pkgs/dump-to-markdown/src/LICENSE pkgs/ublue-motd/src/LICENSE
```

- [x] **Step 2: Write `pkgs/ublue-motd/src/pyproject.toml` exactly**

```toml
[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[project]
name = "ublue-motd"
version = "1.0.0"
description = "Login banner for ublue-based bootc images: image info, boot health, staged updates, tips."
requires-python = ">=3.13"
license = "Apache-2.0"

[project.scripts]
ublue-motd = "ublue_motd:main"

[tool.setuptools.packages.find]
where = ["src"]
```

- [x] **Step 3: Write the failing tests in `pkgs/ublue-motd/src/tests/test_ublue_motd.py`**

```python
"""Tests for the ublue-motd package."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

import ublue_motd


def require(name: str):
    value = getattr(ublue_motd, name, None)
    if value is None:
        raise AssertionError(f"ublue_motd.{name} is not implemented")
    return value


class PackageTests(unittest.TestCase):
    def test_package_exposes_only_ublue_motd_command(self):
        project = tomllib.loads(
            (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
        )["project"]
        self.assertEqual(project["name"], "ublue-motd")
        self.assertEqual(project["scripts"], {"ublue-motd": "ublue_motd:main"})

    def test_module_is_importable(self):
        self.assertIsNotNone(importlib.util.find_spec("ublue_motd"))


class ImageInfoTests(unittest.TestCase):
    def test_reads_fields_and_strips_ostree_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "image-info.json")
            path.write_text(json.dumps({
                "image-ref": "ostree-image-signed:docker://ghcr.io/halcyon-linux/bazzfin-nvidia",
                "image-branch": "stable",
                "version": "44.20261017",
            }))
            info = require("read_image_info")(path)
        self.assertEqual(
            require("strip_image_ref")(info["image-ref"]),
            "ghcr.io/halcyon-linux/bazzfin-nvidia",
        )
        self.assertEqual(info["image-branch"], "stable")
        self.assertEqual(info["version"], "44.20261017")

    def test_missing_or_corrupt_file_returns_empty_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(require("read_image_info")(Path(tmp, "missing.json")), {})
            bad = Path(tmp, "bad.json")
            bad.write_text("{not json")
            self.assertEqual(require("read_image_info")(bad), {})


class BootStatusTests(unittest.TestCase):
    def test_healthy_green_yellow_and_missing(self):
        lines = require("boot_status_lines")
        with tempfile.TemporaryDirectory() as tmp:
            green = Path(tmp, "green")
            green.write_text("boot status is GREEN\n")
            self.assertEqual(lines(green), ["󰟀 `Boot Status: Healthy 󰄳`"])
            yellow = Path(tmp, "yellow")
            yellow.write_text("boot status is YELLOW\nwarning one\nmore\n")
            self.assertEqual(lines(yellow), ["󰟀 `boot status is YELLOW warning one more`"])
            self.assertEqual(lines(Path(tmp, "missing")), [])


class StagedUpdateTests(unittest.TestCase):
    def test_detects_staged_deployment_only(self):
        staged = json.dumps({"deployments": [{"booted": True, "staged": False}, {"staged": True}]})
        self.assertEqual(len(require("staged_update_lines")(staged)), 1)
        not_staged = json.dumps({"deployments": [{"booted": True, "staged": False}]})
        self.assertEqual(require("staged_update_lines")(not_staged), [])
        self.assertEqual(require("staged_update_lines")(""), [])
        self.assertEqual(require("staged_update_lines")("not json"), [])


class DiskTests(unittest.TestCase):
    def test_percent_matches_df_semantics(self):
        fake = os.statvfs_result((4096, 4096, 1000, 100, 50, 0, 0, 0, 0, 255))
        with patch.object(ublue_motd.os, "statvfs", return_value=fake):
            self.assertEqual(require("disk_usage_percent")("/"), 95)

    def test_warning_only_at_threshold(self):
        self.assertEqual(require("disk_lines")(89), [])
        self.assertEqual(len(require("disk_lines")(90)), 1)


class NvidiaTests(unittest.TestCase):
    NVRM = (
        "NVRM version: NVIDIA UNIX Open Kernel Module for x86_64  "
        "590.48.01  Release Build  (dvs-builder@build)  Tue Jan 1 00:00:00 UTC 2026\n"
    )

    def test_parses_version_and_tolerates_absence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "version")
            path.write_text(self.NVRM)
            self.assertEqual(require("nvidia_version")(path), "590.48.01")
            self.assertEqual(require("nvidia_version")(Path(tmp, "missing")), "")

    def test_system_line_includes_nvidia_only_when_present(self):
        line = require("system_line")
        self.assertEqual(line("7.2.7-ogc1.1.fc44", "590.48.01"),
                         "󰒓 `Kernel 7.2.7-ogc1.1.fc44 · NVIDIA 590.48.01`")
        self.assertEqual(line("7.2.7-ogc1.1.fc44", ""), "󰒓 `Kernel 7.2.7-ogc1.1.fc44`")


class TipTests(unittest.TestCase):
    def test_picks_only_nonempty_lines_and_tolerates_absence(self):
        with tempfile.TemporaryDirectory() as tmp:
            tips = Path(tmp)
            (tips / "10-a.md").write_text("first\n\n  second  \n")
            (tips / "20-b.md").write_text("third\n")
            seen = {require("pick_tip")(tips) for _ in range(50)}
            self.assertTrue(seen)
            self.assertTrue(seen <= {"first", "second", "third"})
            self.assertEqual(require("pick_tip")(Path(tmp, "missing")), "")


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 4: Run the tests to verify they fail**

Run: `cd ~/Git/halcyon/copr/python-packages && python3 -m unittest discover -s pkgs/ublue-motd/src/tests -v`
Expected: FAIL — `ImportError: cannot import name 'ublue_motd'` / missing attribute errors.

- [x] **Step 5: Implement the fact functions in `pkgs/ublue-motd/src/src/ublue_motd/__init__.py`**

Module docstring plus `from __future__ import annotations`, imports (`json`, `os`, `random`, `re`, `subprocess`, `Path`). Signatures are pinned in the Interfaces block above. Bodies:

- `read_image_info`: `json.loads(path.read_text(encoding="utf-8"))`, keep only `str` values; any exception → `{}`.
- `strip_image_ref`: `ref.removeprefix("ostree-image-signed:docker://")`.
- `boot_status_lines`: missing file → `[]`; `"status is GREEN" in content` → the healthy line; else `` [f"󰟀 \`{collapsed}\`"] `` with `collapsed = " ".join(content.split())` (multiline content must not break the code span).
- `rpm_ostree_status`: `subprocess.run(["rpm-ostree", "status", "--json"], capture_output=True, text=True, timeout=timeout, check=False)`; return stdout when returncode is 0 else `""`; `FileNotFoundError`/`TimeoutExpired` → `""`. One-line comment: `# shortcut: single fixed timeout; if this ever feels slow on a machine, add a cache file — not a daemon.`
- `staged_update_lines`: `""` → `[]`; parse JSON, `any(d.get("staged") for d in data.get("deployments", []))` → `["󰚰 `Update staged — reboot to apply`"]`; any exception → `[]`.
- `disk_usage_percent`: `st = os.statvfs(path); used = st.f_blocks - st.f_bfree; total = used + st.f_bavail; return round(100 * used / total) if total else 0` (df semantics).
- `disk_lines`: `[f"󰋊 `Root filesystem {percent}% full — free space before updating`"]` when `percent >= DISK_WARN_PERCENT`, else `[]`.
- `nvidia_version`: missing file → `""`; `re.search(r"NVRM version:.*?(\d+\.\d+(?:\.\d+)?)", text)` → group 1, else `""`.
- `system_line`: as asserted in the tests.
- `pick_tip`: lines from `sorted(tips_dir.glob("*.md"))`, stripped, non-empty; `random.choice(lines)` or `""`; wrap file reads so a missing dir yields `""` (glob on a missing dir is already empty).

- [x] **Step 6: Run the tests to verify they pass**

Run: `cd ~/Git/halcyon/copr/python-packages && python3 -m unittest discover -s pkgs/ublue-motd/src/tests -v`
Expected: PASS (all tests, 0 failures).

---

### Task 2: Banner assembly + CLI (repo A)

**Files:**
- Modify: `pkgs/ublue-motd/src/src/ublue_motd/__init__.py` (append)
- Modify: `pkgs/ublue-motd/src/tests/test_ublue_motd.py` (append)

**Interfaces:**
- Consumes: every function from Task 1.
- Produces (Task 3 packages these names; Task 4 relies on the binary + `toggle`):
  ```python
  FALLBACK_TEMPLATE: str
  def render(template_text: str, values: dict[str, str]) -> str
  def banner() -> str
  def show_banner(text: str) -> None
  def disable_flag_path() -> Path
  def toggle_flag() -> int
  def main(argv: list[str] | None = None) -> int
  ```
- Environment overrides honored by `banner()`: `MOTD_IMAGE_INFO_FILE`, `MOTD_TEMPLATE_FILE`, `MOTD_TIP_DIRECTORY`.
- `FALLBACK_TEMPLATE` (used when the template file is missing):
  ```
  # Welcome to Halcyon 󰊴
  󱋩 `${MOTD_IMAGE_NAME}:${MOTD_IMAGE_BRANCH}`${MOTD_IMAGE_BUILD}
  ${MOTD_STATUS}
  ${MOTD_SYSTEM}
  ```

- [x] **Step 1: Append the failing tests**

```python
class RenderTests(unittest.TestCase):
    def test_substitutes_known_vars_and_leaves_unknown(self):
        out = require("render")(
            "A ${MOTD_IMAGE_NAME} B $MOTD_TIP C ${UNKNOWN}",
            {"MOTD_IMAGE_NAME": "img", "MOTD_TIP": "tip"},
        )
        self.assertEqual(out, "A img B tip C ${UNKNOWN}")


class BannerTests(unittest.TestCase):
    def test_assembles_image_status_system_and_tip(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "image.json").write_text(json.dumps({
                "image-ref": "ostree-image-signed:docker://ghcr.io/x/y",
                "image-branch": "stable",
                "version": "44.1",
            }))
            (tmp / "template.md").write_text(
                "${MOTD_IMAGE_NAME}:${MOTD_IMAGE_BRANCH}${MOTD_IMAGE_BUILD}|"
                "${MOTD_STATUS}|${MOTD_SYSTEM}|${MOTD_TIP}"
            )
            (tmp / "tips").mkdir()
            (tmp / "tips" / "10.md").write_text("the tip\n")
            env = {
                "MOTD_IMAGE_INFO_FILE": str(tmp / "image.json"),
                "MOTD_TEMPLATE_FILE": str(tmp / "template.md"),
                "MOTD_TIP_DIRECTORY": str(tmp / "tips"),
            }
            with patch.dict(os.environ, env, clear=False), \
                 patch.object(ublue_motd, "boot_status_lines", return_value=[]), \
                 patch.object(ublue_motd, "rpm_ostree_status", return_value=""), \
                 patch.object(ublue_motd, "disk_usage_percent", return_value=10), \
                 patch.object(ublue_motd, "nvidia_version", return_value="590.48.01"), \
                 patch.object(ublue_motd.os, "uname", return_value=Mock(release="6.1")):
                text = require("banner")()
        self.assertEqual(text, "ghcr.io/x/y:stable (build 44.1)||󰒓 `Kernel 6.1 · NVIDIA 590.48.01`|the tip")

    def test_missing_template_falls_back_and_missing_image_stays_silent(self):
        env = {"MOTD_TEMPLATE_FILE": "/nonexistent/template.md",
               "MOTD_IMAGE_INFO_FILE": "/nonexistent/image.json",
               "MOTD_TIP_DIRECTORY": "/nonexistent/tips"}
        with patch.dict(os.environ, env, clear=False), \
             patch.object(ublue_motd, "boot_status_lines", return_value=[]), \
             patch.object(ublue_motd, "rpm_ostree_status", return_value=""):
            text = require("banner")()
        self.assertIn("Welcome to Halcyon", text)


class CliTests(unittest.TestCase):
    def test_toggle_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp}, clear=False):
            flag = require("disable_flag_path")()
            self.assertEqual(require("main")(["toggle"]), 0)
            self.assertTrue(flag.exists())
            self.assertEqual(require("main")(["toggle"]), 0)
            self.assertFalse(flag.exists())

    def test_banner_silent_when_flag_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "no-show-user-motd").touch()
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp}, clear=False), \
                 contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(require("main")([]), 0)
            self.assertEqual(out.getvalue(), "")

    def test_banner_silent_for_root(self):
        with patch.object(ublue_motd.os, "geteuid", return_value=0), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(require("main")([]), 0)
        self.assertEqual(out.getvalue(), "")

    def test_show_banner_prints_markdown_without_glow(self):
        with patch.object(ublue_motd.shutil, "which", return_value=None), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            require("show_banner")("hello ${x}")
        self.assertEqual(out.getvalue(), "hello ${x}\n")

    def test_toggle_without_home_errors_cleanly(self):
        with patch.dict(os.environ, {}, clear=True), \
             contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(require("main")(["toggle"]), 1)
        self.assertTrue(err.getvalue())

    def test_banner_without_home_renders(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(ublue_motd, "show_banner") as show, \
             patch.object(ublue_motd, "banner", return_value="text"):
            self.assertEqual(require("main")([]), 0)
        show.assert_called_once_with("text")
```

Add `import contextlib`, `import io` to the test imports and `Mock` to the `unittest.mock` import.

- [x] **Step 2: Run the new tests to verify they fail**

Run: `cd ~/Git/halcyon/copr/python-packages && python3 -m unittest discover -s pkgs/ublue-motd/src/tests -v`
Expected: FAIL on the new `render`/`banner`/`main`/`show_banner`/`disable_flag_path` names.

- [x] **Step 3: Implement rendering + CLI (append to `__init__.py`)**

Bodies:

- `render`: `string.Template(template_text).safe_substitute(values)`.
- `banner()`:
  - `info = read_image_info(Path(os.environ.get("MOTD_IMAGE_INFO_FILE", IMAGE_INFO_FILE)))`
  - `version = info.get("version", "")`; `MOTD_IMAGE_BUILD` = `f" (build {version})"` when version else `""`.
  - `MOTD_STATUS` = `"\n".join(boot_status_lines(BOOT_STATUS_FILE) + staged_update_lines(rpm_ostree_status()) + disk_lines(disk_usage_percent()))`.
  - `MOTD_SYSTEM` = `system_line(os.uname().release, nvidia_version(NVIDIA_VERSION_FILE))`.
  - `MOTD_TIP` = `pick_tip(Path(os.environ.get("MOTD_TIP_DIRECTORY", TIPS_DIR)))`.
  - template: read `MOTD_TEMPLATE_FILE` (or `TEMPLATE_FILE`) if it exists, else `FALLBACK_TEMPLATE`; then `render(...)`.
- `show_banner(text)`: `glow = shutil.which("glow")`; no glow → `print(text)`; else `args = ["glow"] + (["-w", str(shutil.get_terminal_size((80, 24)).columns)] if sys.stdout.isatty() else []) + ["-"]`, `subprocess.run(args, input=text, text=True, check=False)`; nonzero returncode → `print(text)`.
- `disable_flag_path()`: `base = os.environ.get("XDG_CONFIG_HOME")`; if unset, `home = os.path.expanduser("~")` and **raise `RuntimeError`** when `home == "~"` (no HOME); return `Path(base or Path(home, ".config")) / "no-show-user-motd"`.
- `toggle_flag()`: try `disable_flag_path()`; `RuntimeError` → message to stderr, return 1. Exists → unlink + `print("MOTD banner enabled.")`; else `mkdir(parents=True, exist_ok=True)` + `touch()` + `print("MOTD banner disabled.")`; return 0.
- `main(argv=None)`: `argparse.ArgumentParser(prog="ublue-motd")`, `--version` action (`%(prog)s {__version__}`), subcommand `toggle`; toggle → `toggle_flag()`; then root skip (`os.geteuid() == 0` → 0); then the flag check — a `RuntimeError` from `disable_flag_path()` (no HOME) counts as “no flag”; flag exists → 0; else `show_banner(banner())`; return 0. Extend the module imports with `argparse`, `shutil`, `string`, `sys`.

- [x] **Step 4: Run the tests to verify they pass**

Run: `cd ~/Git/halcyon/copr/python-packages && python3 -m unittest discover -s pkgs/ublue-motd/src/tests -v`
Expected: PASS (all tests).

- [x] **Step 5: Eyeball the real banner once**

Run:
```bash
cd ~/Git/halcyon/copr/python-packages/pkgs/ublue-motd/src
PYTHONPATH=src python3 -c "from ublue_motd import banner; print(banner())"
```
Expected: the fallback template rendered with this host's real values (image ref, kernel/NVIDIA line when present). This machine is not the target image, so treat it as a smoke test, not the final look.

---

### Task 3: Spec, registry, references, CI wiring (repo A)

**Files:**
- Create: `pkgs/ublue-motd/ublue-motd.spec`
- Create: `references/ublue-motd` (copy of the fork's current script), `references/motd-env.sh` (copy of the fork's current `motd/env`)
- Modify: `ci/packages.toml` (entry + header comment)
- Modify: `README.md` (table row)
- Modify: `.github/workflows/copr-build.yml` (test package list)

**Interfaces:**
- Consumes: binary `ublue-motd` (Task 2), package name `ublue-motd`.
- Produces: the installable RPM consumed by Task 4.

- [x] **Step 1: Write `pkgs/ublue-motd/ublue-motd.spec` exactly**

```spec
# ublue-motd: halcyon-original Python helper; sources vendored under
# pkgs/ublue-motd/src (no upstream tarball exists). Submitted to Copr
# aahsnr-work/python-packages. Bumps are manual: edit Version + changelog,
# push, the cascade rebuilds.
%define debug_package %{nil}

Name:           ublue-motd
Version:        1.0.0
Release:        1%{?dist}
Summary:        Login banner for bootc images: image info, boot health, staged updates, tips.
License:        Apache-2.0
URL:            https://github.com/halcyon-linux/python-packages
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel
Requires:       glow
Requires:       rpm-ostree

%description
Renders the login MOTD banner for ublue-based bootc images. Reads
image-info.json, greenboot boot status, staged rpm-ostree deployments, disk
pressure and rotating tips; renders a markdown template through glow, falling
back to plain markdown when glow or a terminal is unavailable.

%prep
%autosetup -p1

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -l ublue_motd
install -Dpm644 LICENSE %{buildroot}%{_licensedir}/%{name}/LICENSE

%files -f %pyproject_files
%license %{_licensedir}/%{name}/LICENSE
%{_bindir}/ublue-motd

%changelog
* Sat Oct 17 2026 halcyon-autoupdate <aahsnr041@proton.me> - 1.0.0-1
- initial packaging (vendored halcyon-original sources)
```

- [x] **Step 2: Copy the originals into `references/`** (the repo's porting convention: the bash source a Python tool replaces stays on record)

```bash
cd ~/Git/halcyon/copr/python-packages
cp ~/Git/halcyon/bazzite-fork/system_files/desktop/usr/libexec/ublue-motd references/ublue-motd
cp ~/Git/halcyon/bazzite-fork/system_files/desktop/usr/share/ublue-os/motd/env references/motd-env.sh
chmod +x references/ublue-motd
```

- [x] **Step 3: Register the package in `ci/packages.toml`**

Add, in alphabetical position among the batch-0 tables (after `[se]`):

```toml
[ublue-motd]
batch = 0
```

Update the header comment: "The fifteen leaf packages are batch 0." → sixteen, and append `ublue-motd` to the batch-0 name list in the comment.

- [x] **Step 4: Add the README table row** (keep column alignment)

```
| `ublue-motd`       | `ublue-motd`       | Login banner: image info, boot health, staged updates, tips. |
```

- [x] **Step 5: Add the package to the CI test list**

In `.github/workflows/copr-build.yml`, the "Python package tests" step:

```yaml
for package in bbrew-helper brh bruh crh gameclass ublue-motd; do
```

- [x] **Step 6: Validate locally — tests, registry, spec**

```bash
cd ~/Git/halcyon/copr/python-packages
python3 -m unittest discover -s pkgs/ublue-motd/src/tests -v
python3 ci/matrix.py --list
ver=$(sed -n 's/^Version:[[:space:]]*//p' pkgs/ublue-motd/ublue-motd.spec)
mkdir -p "_srpms/ublue-motd/ublue-motd-$ver"
cp -a pkgs/ublue-motd/src/. "_srpms/ublue-motd/ublue-motd-$ver/"
tar czf "_srpms/ublue-motd/ublue-motd-$ver.tar.gz" -C "_srpms/ublue-motd" "ublue-motd-$ver"
podman run --rm -v "$PWD:/work:Z" -w /work registry.fedoraproject.org/fedora:44 bash -c \
  'dnf install -y rpm-build pyproject-rpm-macros python3-devel >/dev/null && rpmbuild -bs --define "_sourcedir /work/_srpms/ublue-motd" --define "_srcrpmdir /work/_srpms" --define "_specdir /work/pkgs/ublue-motd" /work/pkgs/ublue-motd/ublue-motd.spec'
```

Expected: unittest PASS; `ci/matrix.py --list` shows `ublue-motd` in the batch-0 output; rpmbuild prints `Wrote:` for a SRPM that lands in `_srpms/` on the host (that dir is gitignored).

Also run the repo's own local check the workflow runs before submission:

```bash
shopt -s nullglob; for f in pkgs/*/*.sh; do bash -n "$f"; done
```

(Expected: no output — no `.sh` helper scripts exist here yet.)

- [x] **Step 7: Hand off to the human**

Tell the human: push repo A when ready; the COPR cascade builds `ublue-motd`; Task 4 must not be merged/deployed until the Copr build is green, or the image build fails at the install step.

---

### Task 4: Image switch — consume the package (repo B)

**Files:**
- Delete: `system_files/desktop/usr/libexec/ublue-motd`
- Delete: `system_files/desktop/usr/share/ublue-os/motd/env`
- Modify: `system_files/desktop/usr/share/ublue-os/motd/template.md` (replace entirely)
- Create: `system_files/desktop/usr/share/ublue-os/motd/tips/10-halcyon.md`, `.../tips/20-tools.md`
- Modify: `system_files/overrides/usr/share/fish/functions/fish_greeting.fish`
- Create: `system_files/overrides/etc/profile.d/user-motd.sh` (bash/zsh/sh login shells)
- Modify: `build_files/packages/install-common-packages`
- Modify: `build_files/finalization/verify`

**Interfaces:**
- Consumes: package `ublue-motd` (Task 3, must be live in Copr), binary `/usr/bin/ublue-motd`, subcommand `toggle`, template variables from Task 2.
- Produces: the image's banner content and shell wiring (`fish_greeting`, `/etc/profile.d/user-motd.sh`) consumed by Task 5's recipe/docs.

- [x] **Step 1: Delete the replaced files**

```bash
cd ~/Git/halcyon/bazzite-fork
rm system_files/desktop/usr/libexec/ublue-motd
rm system_files/desktop/usr/share/ublue-os/motd/env
```

- [x] **Step 2: Replace `template.md` exactly**

```markdown
# Welcome to Halcyon 󰊴
󱋩 `${MOTD_IMAGE_NAME}:${MOTD_IMAGE_BRANCH}`${MOTD_IMAGE_BUILD}
${MOTD_STATUS}
${MOTD_SYSTEM}

|  Command | Description |
| ------- | ----------- |
| `ujust --choose`  | List all available commands |
| `ujust toggle-user-motd` | Toggle this banner on/off |
| `ujust update` | Update system and installed apps |
| `fastfetch` | View system information |
| `brew help` | Manage command line packages |

${MOTD_TIP}

- [Repository](https://github.com/halcyon-linux/bazzite-fork) · [Report an issue](https://github.com/halcyon-linux/bazzite-fork/issues)
```

- [x] **Step 3: Write the tips (one tip per line, markdown)**

`system_files/desktop/usr/share/ublue-os/motd/tips/10-halcyon.md`:

```markdown
*Updates are staged, not live.* `ujust update` fetches the next image; reboot to apply it — the banner tells you when one is waiting.
*Broke something?* `brh` walks you through rolling back to an older deployment or rebasing.
*The kernel and the NVIDIA driver are pinned together.* If `uname -r` surprises you after an update, they moved as one.
*Keep the image clean.* Apps go in Homebrew, Flatpak, or containers — layered packages can pin your deployment.
*Root is Btrfs with zstd compression and bees dedup.* `compsize` measures what they save.
*Tailscale is built in.* `sudo tailscale up` joins your tailnet; `tailscale status` lists your machines.
*Snapper and Btrfs Assistant are installed* if you want snapshots before risky changes.
*Everything about this image is public.* `ujust verify-image` runs its integrity check.
```

`system_files/desktop/usr/share/ublue-os/motd/tips/20-tools.md`:

```markdown
*Homebrew lives outside the image.* `bbrew-helper` opens the Homebrew TUI; `brew` manages packages directly.
*Game won't start?* `ujust fix-proton-hang` and `ujust fix-gmod` repair the two most common offenders.
*Steam misbehaving?* `ujust fix-reset-steam` rebuilds its runtime state without touching your library.
*Filing a bug?* `ujust get-logs` collects system information and uploads it as a paste link.
*Displays misbehaving?* `crh` walks you through custom resolutions and EDID fixes.
*Live stats:* `btop` for CPU and memory, `duf` for filesystems, `mission-center` for the GUI view.
*`ujust --choose` lists every recipe* with a description — the fastest way to see what the image can do.
*`ls-iommu` prints your IOMMU groups* — handy before passing hardware through to a VM.
*`ujust benchmark` runs the built-in benchmark* to score the machine and catch misconfiguration.
```

Constraint: before finalizing, read `system_files/desktop/usr/share/ublue-os/just/maintenance.just` (`verify-image`) and `80-bazzite.just` (`benchmark`) to confirm the wording matches what those recipes actually do; adjust the two tip lines if not.

- [x] **Step 4: Replace `fish_greeting.fish` exactly** (tab indentation, as the current file uses; the tool now owns the disable flag, so the `no-show-user-motd` check moves out of fish)

```fish
function fish_greeting
	if test -x /usr/bin/ublue-motd
		/usr/bin/ublue-motd
	end

	if set -q fish_private_mode
		echo "fish is running in private mode, history will not be persisted."
	end
end
```

- [x] **Step 5: Add the bash/zsh login hook**

Create `system_files/overrides/etc/profile.d/user-motd.sh` exactly. It must live under `overrides/`, not `desktop/`: base packages ship a file at this path, and `overrides/` is copied last so ours wins and survives base-image updates.

```sh
# Show the MOTD banner in bash and zsh login shells. fish uses fish_greeting.
if [ -z "$USERMOTDSOURCED" ]; then
  USERMOTDSOURCED="Y"
  case $- in
  *i*) ;;
  *) return 0 ;;
  esac
  if test -t 1 && test -d "$HOME"; then
    if test -x "/usr/bin/ublue-motd"; then
      /usr/bin/ublue-motd
    elif test -s "/etc/user-motd"; then
      cat /etc/user-motd
    fi
  fi
fi
```

The guards are deliberate: `case $-` and `test -t 1` keep the banner out of `ssh host cmd`, redirected, and non-interactive login shells (upstream's copy lacks these); the disable flag and root skip live in the tool.

- [x] **Step 6: Install the package in the image**

In `build_files/packages/install-common-packages`, add `ublue-motd` to the `common_packages=(...)` array (after `uld`, alphabetical-ish neighbors are fine).

In `build_files/finalization/verify`, add `ublue-motd` to the `verify_packages` `require_rpms` list (next to `brh bruh crh gameclass bbrew-helper`).

- [x] **Step 7: Verify the edits**

```bash
cd ~/Git/halcyon/bazzite-fork
git diff --stat
grep -rn "no-show-user-motd" system_files/ build_files/   # expect no hits: the flag lives in repo A now
bash -n build_files/packages/install-common-packages
bash -n build_files/finalization/verify
shellcheck -S warning system_files/overrides/etc/profile.d/user-motd.sh   # shellcheck lives in Homebrew on this host
for s in bash zsh sh; do "$s" -c '. system_files/overrides/etc/profile.d/user-motd.sh'; done
```

Expected: only intended files changed; no `no-show-user-motd` references remain in the fork; both bash scripts parse; shellcheck is clean (the `return 0` in a sourced file is normal for profile.d scripts); sourcing under bash, zsh and sh produces no errors — on this host `/usr/bin/ublue-motd` is absent, so the guard skips silently.

---

### Task 5: Toggle recipe + documentation maps (repo B)

**Files:**
- Modify: `system_files/desktop/usr/share/ublue-os/just/80-bazzite.just` (append a recipe)
- Modify: `tree.list` (remove `ublue-motd` under `usr/libexec`; rework the `motd` subtree; add `overrides/etc/profile.d/user-motd.sh`)
- Modify: `system_files-desktop.md` (the `ublue-motd` row and the `motd/env + template.md` row)
- Also check: does `system_files-desktop.md` list halcyon COPR packages elsewhere (search `crh`, `brh`)? If yes, add `ublue-motd` there in the same style.

**Interfaces:**
- Consumes: `/usr/bin/ublue-motd toggle` (Task 4).
- Produces: a real `ujust toggle-user-motd` recipe, replacing the dangling reference that shipped in the old template.

- [x] **Step 1: Append the recipe** at the end of `80-bazzite.just`:

```just
# Toggle the login MOTD banner on or off
[group("system")]
toggle-user-motd:
    @/usr/bin/ublue-motd toggle
```

- [x] **Step 2: Update `tree.list`**

The tree's prefixes contain non-breaking spaces, so **do not retype lines** — transform them byte-for-byte with this script:

```bash
cd ~/Git/halcyon/bazzite-fork
python3 - <<'PY'
import pathlib

p = pathlib.Path("tree.list")
lines = p.read_text(encoding="utf-8").splitlines()

# 1) libexec: drop the ublue-motd line (uupd-update is already "└──")
lines.remove(next(l for l in lines if l.endswith("├── ublue-motd")))

# 2) motd subtree: env + template.md -> template.md + tips/{10,20}
i = next(n for n, l in enumerate(lines) if l.endswith("├── motd"))
prefix = lines[i + 1][: lines[i + 1].index("├──")]   # depth of the env/template.md lines
deep = prefix + "    "                                # one column further, for tips children
lines[i + 1 : i + 3] = [
    prefix + "├── template.md",
    prefix + "└── tips",
    deep + "├── 10-halcyon.md",
    deep + "└── 20-tools.md",
]

# 3) overrides: profile.d gains user-motd.sh after dnf-dummy.sh
i = next(n for n, l in enumerate(lines) if l.endswith("└── dnf-dummy.sh"))
lines[i] = lines[i].replace("└──", "├──")
lines.insert(i + 1, lines[i].replace("├── dnf-dummy.sh", "└── user-motd.sh"))

p.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
sed -n '158,162p;200,208p;240,246p' tree.list   # eyeball all three regions
```

Expected: `ublue-motd` gone from libexec (ntfs-exfat-monitor-script `├──`, uupd-update `└──`); `motd` shows `template.md` + `tips/{10-halcyon,20-tools}.md`; `overrides/etc/profile.d` lists `dnf-dummy.sh` then `user-motd.sh`; glyph columns still line up (compare against any untouched line).

- [x] **Step 3: Update `system_files-desktop.md`**

- Remove the `ublue-motd` row from the `usr/libexec` table (the script no longer ships in `system_files`).
- Replace the `ublue-os/motd/env` + `motd/template.md` row with one naming the new payload, e.g.:
  `| `ublue-os/motd/template.md` + `motd/tips/` | MOTD banner layout (image/build, status lines, system line) and rotating tips | ✅ |`
- If the file documents COPR-installed halcyon tools (it names `brh`/`crh` etc. somewhere), add `ublue-motd` in the same style; if it does not, leave it. **Verified:** `system_files-desktop.md` never mentions `overrides/` (it documents `system_files/desktop` only), so the new `user-motd.sh` needs no row there; `tree.list` covers it.

- [x] **Step 4: Run the fork's own checks**

```bash
cd ~/Git/halcyon/bazzite-fork
just just-check
```

Expected: every `.just` file and the `Justfile` pass `just --fmt --check` (no diff printed, exit 0).

---

## Final verification (after all tasks)

- [x] Repo A: full unittest run passes (20/20); `ci/matrix.py --list` includes `ublue-motd` (batch 0). The local SRPM-build step was skipped under the no-local-builds ruling — Copr is the judge, and its build (id 11164455, fc44+fc45) succeeded.
- [x] Repo A: `git status` shows only the intended new/modified files (verified at commit time; clean and in sync after the push).
- [x] Repo B: `just just-check` passes; `git status`/`git diff` show only intended changes on top of the pre-existing user work; no `motd/env` references remain; `libexec/ublue-motd` survives only in the inert `fish_greeting.fish` override (accepted, fish ruling).
- [x] Repo B: `system_files/overrides/etc/profile.d/user-motd.sh` sources cleanly under `bash`, `zsh`, and `sh`, and passes `shellcheck -S warning` (with the `# shellcheck shell=sh` directive the plan's expectation required).
- [x] Repo A pushed (`6074473`); Copr build for `ublue-motd` succeeded (id 11164455, fc44+fc45) — the repo B image build is unblocked (repo B itself stays uncommitted by design).

## Follow-ups (not part of this plan)

- If shell startup ever measures slow, add a cache file for the rpm-ostree line (the shortcut comment in `rpm_ostree_status` points at this).
- Locale templates, glow themes, non-login interactive shells: revisit only if asked.
