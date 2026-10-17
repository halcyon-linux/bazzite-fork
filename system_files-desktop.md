# `system_files/desktop/` — payload map

`system_files/desktop/` is copied onto `/` by the `Containerfile`. Its layout mirrors installed paths;
keep it path-based rather than bundling assets into an opaque archive. This is a map of the upstream
Bazzite integrations retained by this single-image fork.

**Current scale:** 74 files across 55 directories.

**Legend:** ✅ active in this image · ⚠️ conditional (needs a graphical session, an optional package, or a kernel arg) · ❌ dormant/dead in this fork

## Index

| Section | Contents |
|---|---|
| [Audit summary](#audit-summary) | Current scope and trim history |
| [etc](#etc) | System-wide defaults (10 files) |
| [usr/bin](#usrbin) | User-facing CLI tools — intentionally empty |
| [usr/libexec](#usrlibexec) | Privileged/background helpers (8 files) |
| [systemd, udev, sysctl and plumbing](#systemd-udev-sysctl-and-plumbing) | Units, sysctls, udev, sysusers, tmpfiles, modules-load, dracut, tuned |
| [usr/share](#usrshare) | Desktop entries, containers, plymouth, polkit, ublue-os, wireplumber, yafti |
| [usr/share/ublue-os/just](#usrshareublue-osjust) | The 8 `ujust` source files |

## Audit summary

This map reflects the working tree as of 2026-10-18. `system_files-desktop.md` is maintained as a
grouping guide, not as generated build metadata.

**Trim history (deliberate removals):**

1. **Waydroid family (~15 files)** — the image deliberately ships no Waydroid:
   `etc/default/waydroid-launcher`, `usr/bin/waydroid-launcher`,
   `usr/libexec/waydroid-container-{start,stop,restart}`, `usr/libexec/waydroid-fix-controllers`,
   `usr/share/ublue-os/just/82-bazzite-waydroid.just`,
   `usr/share/polkit-1/actions/org.bazzite.waydroid.policy`, `usr/share/polkit-1/rules.d/30-waydroid.rules`,
   `usr/share/applications/waydroid-container-restart.desktop`,
   `usr/share/applications/Waydroid/{capsule,hero,icon,logo,store-capsule}.png`.
   The matching `import` line was dropped from `build_files/just/import-bazzite-justfiles`.
2. **`usr/bin` purge** — every in-tree CLI command was removed. User-facing commands now come from
   RPMs: `brh`, `bruh`, `crh`, `gameclass`, `bbrew-helper` (halcyon COPR builds), plus `ublue-motd`
   and `uupd-update` (Universal Blue). Removed: `bazzite-rollback-helper`, `bazzite-steam`,
   `bazzite-steam-bpm`, `bazzite-steam-firstrun`, `bbrew-helper`, `boot-windows`, `brh`, `bruh`,
   `copr`, `crh`, `custom-resolution-helper`, `gameclass`, `mesa-git`. Reference bash
   implementations live in `references/` at the repo root. Dangling references were cleaned:
   the Steam-launcher `sed` block in `configure-desktop-integration`,
   `usr/share/applications/bazzite-steam-bpm.desktop`, the `ujust setup-boot-windows-steam` recipe
   + yafti entry, and the `bazzite-steam --disable-firstrun` relaunch in `fix-reset-steam`.
3. **Wake-on-LAN family** — `usr/libexec/force-wol`, `usr/lib/systemd/system/force-wol.service`,
   its entry in `build_files/system/configure-system-services`, the `ujust wol` recipe +
   `toggle-wol` alias, and the yafti Wake-on-LAN action.
4. **Incus** — `usr/lib/systemd/system/incus-workaround.service`,
   `usr/lib/tmpfiles.d/incus-workaround.conf`, its `configure-system-services` entry, and the incus
   `distrobox.ini` download in `install-system-integration-files`.
5. **NTFS/exFAT nag** — `usr/lib/systemd/user/ntfs-nag.service`,
   `usr/libexec/ntfs-exfat-monitor-script`, its `configure-system-services` entry, and the
   `_disable-ntfs-service` recipe.
6. **Mesa-git tooling** — `usr/bin/mesa-git` (earlier) and
   `usr/share/ublue-os/just/89-bazzite-mesa-git.just` + its import line; Mesa Git builds are the
   maintainer's own COPR now.
7. **`hwsupport/sysid`** — ROG Ally/Flow DMI-name normalization helper; unreferenced after the
   Waydroid and hardware-setup cleanups.
8. **Earlier trims** — `bazzite-iwd-migration` (unit + script; NetworkManager/wpa_supplicant is
   used), `bazzite-bling-fastfetch` (bling is RPM-provided), `usr/share/ublue-os/motd/env`,
   `etc/profile.d/ms-edit-default-editor.sh` + `usr/bin/edit` symlink (msedit not installed),
   `etc/systemd/system/beesd@.service.d/override.conf` (byte-identical duplicate),
   `usr/share/polkit-1/rules.d/90-corectrl.rules` (CoreCtrl not installed).
9. **Offline docs bundle** (per maintainer decision): `usr/share/ublue-os/docs/serve`, the CI
   "Download offline docs" step, and `build_files/label-ublue-docs` — this bundle was also the only
   source of the Roboto/Roboto Mono webfonts.
10. **Device-specific trim** (per maintainer decision): the akmods install list was reduced to
    `nct6687d` only (MSI Z790 sensor chip); removed `usr/lib/modprobe.d/fw-charge-control.conf`,
    `usr/lib/modprobe.d/new-lg4ff.conf`, `usr/lib/udev/rules.d/90-dolphin-motion.rules`; dropped the
    `iio-sensor-proxy`, `usbip`, and `obs-studio-plugin-vkcapture-hook-libs` packages.
11. **`bazzite-libvirtd-setup.service`** — one-shot that enabled libvirtd after the next reboot,
    needed only for the old `ujust`-driven `rpm-ostree install` flow. Removed now that virtualization
    ships enabled by default; the recipe no longer references it.

`bazzite-hardware-setup` was rewritten on 2026-10-18: dropped the zram `vm.min_free_kbytes` tweak and
the inert Waydroid apparmor cleanup; kept the karg handling (bluetooth/nomodeset, reboot-if-changed)
and the distrobox hostname/`/etc/hostname` fix. The state gate is now `HWS_VER=81` (80 for the
rewrite, 81 for the KVM kargs).

**Virtualization is enabled by default (2026-10-18):** the image bakes in `virt-manager`,
`virt-install`, `libvirt-daemon`, `libvirt-daemon-kvm`, `libvirt-daemon-config-{network,nwfilter}`,
and `virtiofsd`; `libvirtd.service` is enabled at build time by `configure-system-services`;
`bazzite-hardware-setup` applies the `kvm.ignore_msrs=1`/`kvm.report_ignored_msrs=0` kargs;
`bazzite-libvirt.conf` recreates the libvirt/swtpm `/var` directories at boot (the packaged payload
is stripped by `finalize`); and the privileged user-setup helper adds the login user to the `libvirt`
group. `ujust setup-virtualization` remains as the repair/disable path.

Remaining Waydroid mentions, left in place deliberately (all guarded or inert): the
`waydroid-container.service` disable no-op in `build_files/nvidia/finalize-nvidia`, the commented
package entries in `install-common-packages`, the `forbid_rpms` guard in `verify`, and the Waydroid
section in `yafti.yml` — note its `configure-waydroid` recipes were removed with
`82-bazzite-waydroid.just`, so those buttons now report an unknown recipe.

## etc

System-wide defaults. 10 files.

| File | Why it exists | Needed? |
|---|---|---|
| `conf.d/btrfs-dedup` | Config for BTRFS dedup tooling; `RMLINT_SKIP=1` selects the duperemove path | ⚠️ policy file; image's active dedup path is `bees` |
| `geoclue/conf.d/99-beacondb.conf` | Point WiFi geolocation at BeaconDB instead of Mozilla/MLS (which was shut down); fixes broken location (ublue-os/bazzite#1897) | ✅ |
| `profile.d/99-custom-env.sh` | Halcyon user shell environment: XDG base directories, terminal/browser/editor defaults, `pathprepend` for user toolchains (`~/.local/bin`, cargo, go, bun, npm, emacs) | ✅ |
| `security/limits.d/memlock.conf` | Raise memlock limit to ~2 GiB — some Proton/Wine games and VFIO need locked memory | ✅ |
| `systemd/system/beesd@.service.d/bees-timeout.conf` | Caps `beesd` (BTRFS dedup) at 30 min, idle I/O, low OOM score | ✅ |
| `systemd/system.conf.d/timeout.conf` | `DefaultTimeoutStopSec=15s` — snappier shutdown/restart on atomic systems | ✅ |
| `systemd/user.conf.d/timeout.conf` | Same, for the user manager | ✅ |
| `systemd/zram-generator.conf` | zram swap: zstd, `min(ram/2, 16GiB)` — memory pressure relief | ✅ |
| `ublue-os/.gitkeep` | Keeps the `etc/ublue-os` directory present; topgrade's include path (`/etc/ublue-os/topgrade.toml`) lives here at runtime | ⚠️ |
| `uupd/config.json` | Disables uupd's `distrobox` module (don't auto-update user distroboxes) | ✅ (uupd.timer enabled) |

## usr/bin

Intentionally empty: the in-tree scripts were replaced by RPM-provided commands (`brh`, `bruh`,
`crh`, `gameclass`, `bbrew-helper`, `ublue-motd`, `uupd-update`). Keep new PATH commands out of this
tree; build-time downloads and internal helpers belong in `usr/libexec`.

## usr/libexec

Privileged/background helpers. 8 files.

| File | Why it exists | Needed? |
|---|---|---|
| `bazzite-boot-remount` | Remount `/boot` read-write for updates then back to read-only (bootc/rpm-ostree boot partition handling) | ✅ |
| `bazzite-dynamic-fixes` | Per-session GPU workarounds — sets `GSK_RENDERER=gl` on Intel i915/xe to avoid GTK4 glitches; removes it when not needed | ✅ (user service, enabled globally) |
| `bazzite-fetch-image` | Prints `image-name:branch` + signed/unsigned marker — used in prompts/scripts | ⚠️ cosmetic |
| `bazzite-hardware-setup` | Versioned one-shot hardware setup (`HWS_VER=81`): applies the bluetooth/nomodeset/KVM kargs (reboot if changed), fixes over-long hostnames and missing `/etc/hostname` for distrobox; state in `/etc/bazzite` | ✅ (system service, enabled) |
| `bazzite-powersave` | Sets the power profile over DBus (`power-saver`/`balanced`) — used by ujust/ppd integration | ✅ |
| `bazzite-privileged-user-setup` | Root-side user setup: enable NTP, allow Tailscale operator, add the user to the `libvirt` group; invoked via polkit from user-setup | ✅ |
| `bazzite-snapper-config` | Snapper defaults (retention disabled; user opts in) — ujust wrappers | ✅ (snapper installed) |
| `bazzite-user-setup` | Per-user first-login setup (versioned): config markers, Templates symlinks (vkBasalt/dxvk/MangoHud examples), triggers the privileged helper | ✅ (user service, enabled) |

## systemd, udev, sysctl and plumbing

### System units

| File | Why it exists | Needed? |
|---|---|---|
| `usr/lib/systemd/system/bazzite-hardware-setup.service` | Runs the hardware setup oneshot; ordering vs rpm-ostree/tuned | ✅ |
| `…/beesd@.timer` | Daily timed beesd (dedup) run | ✅ |
| `…/cockpit.service` | Gate unit `Requires=` the podman cockpit container; toggled by ujust | ✅ |
| `…/dev-hugepages1G.mount` | Mounts 1G hugepages **when** `hugepagesz=1G` kernel arg is present (gaming/VM perf) | ✅ conditional |
| `…/fstrim.service.d/workaround-no-root-trim.conf` | fstrim workaround for immutable/atomic root (Fedora tracker #81) | ✅ |
| `…/kmod-sleep-workaround@.service` | Template to unload/reload a named module around sleep for devices with suspend bugs; needs `kmod` (`rmmod`/`modprobe`), pinned in `verify` | ⚠️ opt-in template |
| `…/mcelog.service.d/override.conf` | Prevents mcelog running inside VMs (no MC errors there) | ✅ if mcelog present |

### User units

| File | Why it exists | Needed? |
|---|---|---|
| `usr/lib/systemd/user/bazzite-user-setup.service` | Runs user setup at login | ✅ |
| `usr/lib/systemd/user/bazzite-dynamic-fixes.service` | Runs GPU workaround logic at login | ✅ |
| `usr/lib/systemd/user/steam-icons-cleanup.service` | One-shot each session: `ujust steam-icons remove` to prune dead Steam shortcuts (ublue-os/bazzite#3280) | ⚠️ |

### Sysctls

| File | Why it exists | Needed? |
|---|---|---|
| `usr/lib/sysctl.d/60-kernel.conf` | `split_lock_mitigate=0` — gaming performance | ✅ |
| `usr/lib/sysctl.d/70-gaming.conf` | `vm.max_map_count` raised — Proton/Wine large-memory games | ✅ |
| `usr/lib/sysctl.d/75-networking.conf` | BBR congestion control, MTU probing, IPv6 privacy addresses | ✅ |
| `usr/lib/sysctl.d/80-inotify.conf` | Higher inotify watch limits — dev tools, launchers, game file watchers | ✅ |

### udev, sysusers, tmpfiles, modules-load, dracut

| File | Why it exists | Needed? |
|---|---|---|
| `usr/lib/udev/rules.d/60-schedulers.rules` | I/O scheduler policy: kyber for SSD/NVMe, bfq for SD/HDD | ✅ |
| `usr/lib/sysusers.d/plugdev.conf` | Creates the `plugdev` group (46) that some device-access udev rules reference | ✅ |
| `usr/lib/tmpfiles.d/bazzite-libvirt.conf` | Recreates libvirt/swtpm runtime state under `/var` at boot: `libvirt` tree, `libvirt` log dir, and `swtpm-localca` owned by `tss` (packaged `/var` payload is stripped by `finalize`) | ✅ (virt default-on) |
| `usr/lib/modules-load.d/wine-ntsync.conf` | Loads the `ntsync` module (Wine NT synchronization primitives) | ✅ |
| `usr/lib/dracut/dracut.conf.d/80-vfio.conf` | Force-loads `vfio*` in initramfs (GPU passthrough setups) | ⚠️ harmless default |

### Tuned profiles

| File | Why it exists | Needed? |
|---|---|---|
| `usr/lib/tuned/profiles/balanced-bazzite/{tuned.conf,script.sh}` | "Balanced" PPD profile: inherits balanced, switches scx scheduler to auto on start | ✅ (wired via `ppd.conf` mappings in `configure-system-policy`) |
| `usr/lib/tuned/profiles/powersave-bazzite/{tuned.conf,script.sh}` | Power-saver profile + `panel_power_savings=0` tweak | ✅ |
| `usr/lib/tuned/profiles/throughput-performance-bazzite/{tuned.conf,script.sh}` | Performance profile with Bazzite summary/tweaks | ✅ |

## usr/share

Desktop entries, containers, plymouth, polkit, ublue-os, wireplumber, yafti.

| File | Why it exists | Needed? |
|---|---|---|
| `applications/bbrew.desktop` | Menu entry opening the bbrew TUI in a terminal | ⚠️ |
| `containers/systemd/cockpit-container.container` | Podman Quadlet running the upstream `cockpit/ws` container (web admin UI) with host mounts | ✅ (cockpit pkgs installed) |
| `plymouth/themes/spinner/watermark.png` | Brand watermark on the boot splash | ✅ cosmetic |
| `polkit-1/actions/org.bazzite.privileged.user.setup.policy` | Defines the pkexec action for the privileged user-setup helper | ✅ |
| `polkit-1/rules.d/20-privileged-ruser.rules` | Lets `wheel` group run the setup helper without a prompt | ✅ |
| `wireplumber/wireplumber.conf.d/51-disable-suspension.conf` | Disables ALSA node auto-suspension — prevents audio pops/latency for gamers | ⚠️ needs session |
| `ublue-os/motd/template.md` + `motd/tips/{10-halcyon,20-tools}.md` | Halcyon MOTD banner layout (image/build, status, system lines) and rotating tips | ✅ |
| `ublue-os/topgrade.toml` | Main topgrade config: system (rpm-ostree) + brew + firmware; includes `/etc/ublue-os/topgrade.toml`, assume-yes | ⚠️ |
| `ublue-os/bbrew.png` | Icon for the bbrew launcher | ⚠️ |
| `ublue-os/firefox-config/01-bazzite-global.js` | Firefox defaults: hardware video decode on, ML/chat/reader features off (also reused by the Flatpak Firefox) | ⚠️ no RPM Firefox in image |
| `ublue-os/bazaar/blocklist.yaml` | Hides from Bazaar what's already provided/replaced (Steam, Lutris, editors; DE-specific apps per session) | ✅ |
| `ublue-os/bazaar/content.yaml` | Curated Bazaar storefront (banner rows for gaming/music/office/streaming/utilities) | ✅ |
| `ublue-os/bazaar/{gaming,music,office,streaming,utilities}.jxl` | Banner images used by `content.yaml` | ✅ |
| `ublue-os/bazaar/hooks.py` | Bazaar transaction hooks (e.g. JetBrains "not supported in this format" dialog) | ✅ |
| `ublue-os/bazaar/main.yaml` | Bazaar main config: blocklist path, EOL override for OBS, hook registration | ✅ |
| `yafti/yafti.yml` | "Bazzite Portal" first-run flow definition (welcome, docs links, curated install scripts via flatpak/brew) | ⚠️ portal pkg present, needs session |
| `zsh-preexec.sh` | bash-preexec-compatible `preexec_functions`/`precmd_functions` hooks for zsh (zsh has the hooks natively; this file exposes the bash-preexec interface for drop-in substitution) | ⚠️ user-sourced from `.zshrc` |

## usr/share/ublue-os/just

The 8 `ujust` source files preserve the same recipe names. Small related groups are combined; the
large upstream feature files remain separate for easier updates.

| File | Purpose |
|---|---|
| `10-update.just` | `ujust update` (via uupd), changelogs |
| `80-bazzite.just` | Core system toggles and helpers |
| `81-bazzite-fixes.just` | Game/Steam fixes |
| `82-bazzite-apps.just` | Install/manage GUI apps via layering |
| `83-bazzite-audio.just` | Virtual PipeWire channels for OBS |
| `87-bazzite-framegen.just` | LSFG-VK frame generation |
| `system-tools.just` | Beesd, Cockpit, virtualization, input-remapper |
| `maintenance.just` | Picker, image verification, and updater-to-Steam recipes |
