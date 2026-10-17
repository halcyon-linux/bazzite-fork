# AGENTS.md

## Project

This repo builds **`bazzfin-nvidia`** (branded "Halcyon"): a bootable OCI image for Fedora Atomic (bootc/rpm-ostree), forked from [Bazzite](https://github.com/ublue-os/bazzite).

- Base `ghcr.io/ublue-os/base-main:44`, no desktop environment (Hyprland planned).
- Pinned OGC gaming kernel plus NVIDIA open kernel modules, taken from pre-built `akmods*` images.
- Published to `ghcr.io/halcyon-linux/bazzfin-nvidia:stable` and signed with cosign.
- Single target, single machine (MSI Z790-P; only the `nct6687d` kmod is installed).

There is no application code or unit-test suite. The "code" is bash scripts, systemd units, config files, and a `Containerfile`. The CI image build plus `build_files/finalization/verify` is the test suite.

## Commands

```bash
just build          # build locally with podman
just run            # build if missing, then open a shell in the image
just just-check     # validate Just syntax (CI runs this too)
shellcheck <file>   # run on any shell script you change
```

Full builds are slow (CI timeout: 90 min). Make small, reviewable edits, run `just just-check` and `shellcheck`, and treat the CI build as authoritative.

## Layout

- `Containerfile`: the whole image recipe.
- `build_files/`: build-time scripts, bind-mounted at `/ctx` and never shipped. Subdirs: `kernel/`, `packages/`, `system/`, `nvidia/`, `finalization/`, `just/`, `shared/`.
- `system_files/desktop/`: copied onto `/` early. Mirrors installed paths.
- `system_files/nvidia/`: copied onto `/` in the NVIDIA section only.
- `system_files/overrides/`: copied onto `/` late, to replace files that packages ship.
- `just_scripts/`, `Justfile`: local build helpers.
- `.github/workflows/build.yml`: build, rechunk, push, and sign (on push to `main`, daily, manual).
- `system_files-desktop.md`: hand-written payload map. It can drift, so trust the tree over it.

## Build order

The order in the `Containerfile` is load-bearing:

1. Desktop files and Homebrew files, then kernel, repos, gaming stack, packages.
2. `system_files/overrides/` is copied only after packages are installed.
3. `image-info`, `build-initramfs`, and `finalize` run once after the main section and **again** after the NVIDIA section. The last pass must include everything.
4. `verify final` and `bootc container lint` run last.

Each package-installing `RUN` ends with `/ctx/shared/cleanup`. Keep that.

## Conventions

**Shell scripts** (most have no extension; the shebang identifies them)
- Start with `#!/usr/bin/env bash` and `set -Eeuo pipefail`. Existing kernel and finalization scripts use `set -eoux pipefail`; leave those as they are.
- Install packages with `dnf5 --setopt=install_weak_deps=False --setopt='*.skip_if_unavailable=False' -y ...`.
- Download from GitHub through `/ctx/shared/ghcurl`, not bare `curl`. The `Containerfile` step must mount `--mount=type=secret,id=GITHUB_TOKEN`.
- Tag downloaded binaries with `setfattr -n user.component -v <name> <file> 2>/dev/null || true`.
- Quote variables, prefer `printf` to `echo`, use 4-space indentation in new code.
- New executables in `system_files/` need the executable bit set in git.

**Immutable-image rules**
- Ship static content under `/usr`. `/etc` is for defaults only.
- Do not ship anything under `/var`. `finalize` deletes everything in `/var` except `cache`.
- The build ends with `bootc container lint`. Anything it rejects fails the build.

**Repos, packages, services**
- Repo priorities and excludes live in `packages/setup-repositories`. Build-only repos are disabled again in `system/configure-system-policy`. A new repo needs changes in both.
- Kernel, Mesa, bluez, Xwayland, and NetworkManager are `dnf5 versionlock`ed. Don't unlock them as a side effect of another change.
- Enable and disable services in `system/configure-system-services`. NVIDIA services are handled in `nvidia/finalize-nvidia`.
- Runtime helpers are `halcyon-*` RPMs from the `aahsnr-work/python-packages` Copr (sources: the `halcyon-linux/python-packages` repo). `install-common-packages` must install them before `configure-system-services`/`finalize-nvidia` enable their units.

**ujust recipes**
- Recipes live in `system_files/desktop/usr/share/ublue-os/just/`. A new `.just` file must be added to the list in `build_files/just/import-bazzite-justfiles`.
- `yafti.yml` calls many `ujust` recipes. Update it if you rename or remove one.

## Values that must change together

- **Kernel version:** `KERNEL_VERSION` is set in both `Containerfile` and `.github/workflows/build.yml`. Matching tags must exist for `akmods`, `akmods-extra`, and `akmods-nvidia-open`.
- **Fedora version:** set in `Containerfile`, `build.yml`, and `Justfile` (`latest`).
- **One-shot setup scripts:** `HWS_VER` (`halcyon-hardware-setup`) and `setup_version` (`halcyon-user-setup`) live in the `halcyon-linux/python-packages` repo; bump them there and release the package so changed logic reruns on existing installs.
- **GitHub Actions** are pinned by commit SHA with a version comment. Keep that format.

## Verification

`build_files/finalization/verify` has groups `kernel | repos | packages | nvidia | final`. When you add or remove something the image depends on, update the matching group (`require_rpms`, `forbid_rpms`, `require_repos`).

`verify final` forbids Waydroid, bundled fonts, the offline docs bundle, and the trimmed device kmods, guards the `halcyon-*` migration (old `bazzite-*`/`ublue-nvidia-*` scripts and units must stay absent; their replacements must be present and enabled), and it checks that the combined justfile parses.

## Boundaries

**Always**
- Update `system_files-desktop.md` and `tree.list` when you add or remove files.
- Match existing patterns in neighboring scripts before inventing new ones.

**Ask first**
- Adding a repo, a COPR, or a kernel module.
- Changing signing, publishing, or cleanup behavior in `.github/workflows/`.
- Removing a versionlock or changing the base image.

**Never**
- Commit secrets or keys. CI uses `GITHUB_TOKEN` and `SIGNING_SECRET`; only `cosign.pub` belongs in the repo.
- Re-add what `verify final` forbids without changing `verify` deliberately and saying so.
- Rename `bazzite-*` scripts, paths, or `ujust` recipes in bulk. Other files reference them.

## Known quirks

- A push to `main` builds and publishes the image that installed systems pull, so treat `main` as a release branch.
- `.github/pull.yml` merges `ublue-os:main` into this trimmed fork. After a sync, check that removed files and packages haven't come back.
- `just build` tags with `IMAGE_NAME=bazzfin-nvidia-build`, while CI uses `bazzfin-nvidia`. `just_scripts/manage-images` filters on `localhost/bazzite*-build`, which doesn't match the local tag, so `list-images` and `clean-images` may find nothing.
- `just_scripts/get-defaults` rejects any target other than `bazzfin-nvidia`.
- Changes to `*.md` and `*.txt` files don't trigger CI (`paths-ignore`). `tree.list` does.
