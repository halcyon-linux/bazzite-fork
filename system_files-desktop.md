# `system_files/desktop/` — file audit

Every file under `system_files/desktop/` listed with its purpose and whether it is needed in this fork.
`system_files/desktop/` is copied onto `/` early in the `bazzite` stage (`Containerfile:52`). These are
upstream-Bazzite integration files: configs and helpers that make the installed packages behave like Bazzite.
Since this fork currently ships **no desktop session and no waydroid**, some files are dead weight here.

**Scale:** 134 files, ~4.1 MB.

**Legend:** ✅ active in this image · ⚠️ conditional (needs a graphical session, an optional package, or a kernel arg) · ❌ dormant/dead in this fork

## Index

| Section | Contents |
|---|---|
| [Audit summary](#audit-summary) | Counts and trim candidates |
| [etc](#etc) | System-wide defaults (20 files) |
| [usr/bin](#usrbin) | User-facing CLI tools (15 entries) |
| [usr/libexec](#usrlibexec) | Privileged/background helpers (20 files) |
| [systemd, udev, sysctl and plumbing](#systemd-udev-sysctl-and-plumbing) | Units, udev rules, sysctls, tuned profiles, modprobe/dracut/sysusers/tmpfiles |
| [usr/share](#usrshare) | Desktop entries, art, polkit, cockpit, bazaar, share/ublue-os, yafti |
| [usr/share/ublue-os/just](#usrshareublue-osjust) | The 16 `ujust` recipe files |

## Audit summary

| Class | Count | Notes |
|---|---|---|
| ✅ Active | ~60 | Core Bazzite behavior: hardware setup, user setup, updates (uupd), brew/bbrew, Bazaar, cockpit, tuned, sysctls, udev rules, MOTD, docs, most ujust recipes |
| ⚠️ Conditional | ~45 | Light up only with a graphical session, opt-in package, or kernel arg — correct to keep (Hyprland is planned) |
| ❌ Dead weight | ~18 | Removed from the repository (see below) |

**Removed deadweight (this cleanup):**

1. **Waydroid family (15 files)** — image deliberately ships no Waydroid:
   `etc/default/waydroid-launcher`, `usr/bin/waydroid-launcher`,
   `usr/libexec/waydroid-container-{start,stop,restart}`, `usr/libexec/waydroid-fix-controllers`,
   `usr/share/ublue-os/just/82-bazzite-waydroid.just`,
   `usr/share/polkit-1/actions/org.bazzite.waydroid.policy`, `usr/share/polkit-1/rules.d/30-waydroid.rules`,
   `usr/share/applications/waydroid-container-restart.desktop`,
   `usr/share/applications/Waydroid/{capsule,hero,icon,logo,store-capsule}.png`.
   The matching `import` line was dropped from `build_files/import-bazzite-justfiles`.
2. `usr/bin/edit` symlink + `etc/profile.d/ms-edit-default-editor.sh` — `msedit` is commented out of the package list.
3. `etc/systemd/system/beesd@.service.d/override.conf` — byte-identical duplicate of `bees-timeout.conf`.
4. `usr/share/polkit-1/rules.d/90-corectrl.rules` — CoreCtrl isn't installed by this fork.
5. **Offline docs bundle** (per maintainer decision): `usr/share/ublue-os/docs/serve`, the CI "Download offline docs" step, and `build_files/label-ublue-docs` — this bundle was also the only source of the Roboto/Roboto Mono webfonts.
6. **Device-specific trim** (per maintainer decision): the akmods install list was reduced to `nct6687d` only (MSI Z790 sensor chip); removed `usr/lib/modprobe.d/fw-charge-control.conf`, `usr/lib/modprobe.d/new-lg4ff.conf`, `usr/lib/udev/rules.d/90-dolphin-motion.rules`; dropped the `iio-sensor-proxy`, `usbip`, and `obs-studio-plugin-vkcapture-hook-libs` packages.

Remaining waydroid mentions left in place deliberately (all guarded or inert): the `waydroid-container.service`
disable no-op in `build_files/finalize-nvidia`, the guarded cleanup block in `bazzite-hardware-setup`,
the commented package entries in `install-common-packages`, the `waydroid-choose-gpu` download in
`install-system-integration-files`, and the Waydroid entries in `yafti.yml`.

## etc

System-wide defaults. 20 files.

| File | Why it exists | Needed? |
|---|---|---|
| `conf.d/btrfs-dedup` | Config for BTRFS dedup tooling; `RMLINT_SKIP=1` selects the duperemove path | ⚠️ policy file; image's active dedup path is `bees` |
| `default/waydroid-launcher` | Per-handheld Waydroid resolution/density defaults (Deck, Ally, AYANEO…), consumed by the waydroid scripts | ❌ waydroid not installed |
| `distrobox/distrobox.ini` | Declarative `distrobox assemble` presets (Arch/Debian/Fedora/openSUSE/Ubuntu toolbx) | ⚠️ user-invoked, distrobox in base |
| `dnf/dnf.conf` | System default `install_weak_deps=False` — keeps atomic image lean | ✅ |
| `environment` | `HOMEBREW_NO_AUTO_UPDATE=1` — brew updates handled explicitly, not per-shell | ✅ (brew shipped) |
| `geoclue/conf.d/99-beacondb.conf` | Point WiFi geolocation at BeaconDB instead of Mozilla/MLS (which was shut down); fixes broken location (ublue-os/bazzite#1897) | ✅ |
| `profile.d/askpass.sh` | Expose `SUDO_ASKPASS` (ssh-askpass) so GUI prompts from polkit wrappers work | ⚠️ |
| `profile.d/ms-edit-default-editor.sh` | Default `EDITOR=/usr/bin/msedit` | ❌ `msedit` is commented out in the package list → points at nothing |
| `profile.d/open.sh` | `open` alias → `xdg-open` (muscle memory from other OSes) | ✅ trivial |
| `security/limits.d/memlock.conf` | Raise memlock limit to ~2 GiB — some Proton/Wine games and VFIO need locked memory | ✅ |
| `skel/.config/autostart/bazzite-portal.desktop` | First-login autostart of the "Bazzite Portal" (yafti-based welcome/setup app) for new users | ⚠️ needs a desktop session |
| `skel/.config/user-tmpfiles.d/discord-rpc.conf` | Symlinks the Discord IPC socket into the user runtime dir so native games can talk RPC to the **Flatpak** Discord | ⚠️ |
| `systemd/system/beesd@.service.d/bees-timeout.conf` | Caps `beesd` (BTRFS dedup) at 30 min, idle I/O, low OOM score | ✅ |
| `systemd/system/beesd@.service.d/override.conf` | **Byte-identical** to the file above | ❌ pure duplicate → trim candidate |
| `systemd/system.conf.d/timeout.conf` | `DefaultTimeoutStopSec=15s` — snappier shutdown/restart on atomic systems | ✅ |
| `systemd/user.conf.d/timeout.conf` | Same, for the user manager | ✅ |
| `systemd/zram-generator.conf` | zram swap: zstd, `min(ram/2, 16GiB)` — memory pressure relief | ✅ |
| `ublue-os/topgrade.toml` | Adds the "Third Party CSS Loader Themes" custom command to topgrade | ⚠️ only matters if user uses topgrade |
| `uupd/config.json` | Disables uupd's `distrobox` module (don't auto-update user distroboxes) | ✅ (uupd.timer enabled) |
| `xdg/mimeapps.list` | Makes `.flatpakref` links open in Bazaar (the Flathub-first store, Bazzite's default app store) | ✅ |

## usr/bin

User-facing CLI tools. 15 entries (12 scripts + 3 symlinks).

| File | Why it exists | Needed? |
|---|---|---|
| `bazzite-rollback-helper` | Interactive rpm-ostree rollback/rebase helper: lists image tags from GHCR, verifies signature scheme | ✅ |
| `brh` (symlink) / `bruh` (wrapper) | Short aliases for the above ("bruh moment" = instant rollback) | ✅ |
| `bazzite-steam` | Steam launcher wrapper: NVIDIA env fix (`__GL_CONSTANT_FRAME_RATE_HINT`), first-run notice, dGPU blank-window workaround (via `cardwire`), shader-precache thread tuning, extest for Steam Controller on Wayland | ✅ (steam installed) |
| `bazzite-steam-bpm` | Relaunch Steam into Big Picture Mode; workaround for a sluggish BPM switch (ublue-os/bazzite#1675) | ⚠️ |
| `bazzite-steam-firstrun` | Localized "first start downloads Steam" notice | ✅ |
| `bbrew-helper` | Wraps `brew` to bootstrap and launch **bbrew** (TUI Homebrew manager) | ✅ (brew shipped) |
| `boot-windows` | Sets next EFI boot to Windows + reboots — dual-boot convenience (paired with a ujust recipe that adds a Steam shortcut + sudoers rule) | ✅ |
| `copr` | One-word `dnf5 copr` wrapper | ✅ |
| `custom-resolution-helper` + `crh` symlink | Manage custom display modes via modedb kernel args (for awkward panels) | ✅ |
| `edit` (symlink → `/usr/bin/msedit`) | Friendly editor default | ❌ dangling (msedit not installed) |
| `gameclass` | Sets the window class of a launched game (`GAMECLASS=exe=class gameclass …`) so compositors/Steam can identify windows correctly | ⚠️ needs a compositor (planned Hyprland) |
| `mesa-git` | Run apps against a user-installed Mesa Git build (LD_LIBRARY_PATH wrapper), paired with ujust recipes | ⚠️ opt-in |

## usr/libexec

Privileged/background helpers. 20 files.

| File | Why it exists | Needed? |
|---|---|---|
| `bazzite-boot-remount` | Remount `/boot` read-write for updates then back to read-only (bootc/rpm-ostree boot partition handling) | ✅ |
| `bazzite-dynamic-fixes` | Per-session GPU workarounds — e.g. sets `GSK_RENDERER=gl` on Intel i915/xe to avoid GTK4 glitches; removes it when not needed | ✅ (user service, enabled globally) |
| `bazzite-fetch-image` | Prints `image-name:branch` + signed/unsigned marker — used in prompts/scripts | ⚠️ cosmetic |
| `bazzite-hardware-setup` | Versioned one-shot hardware setup at boot/update: handheld quirks, Deck tweaks, fixes stale configs (incl. a Waydroid apparmor cleanup line) | ✅ (system service, enabled) |
| `bazzite-iwd-migration` | Migrates WiFi backend away from iwd: re-enables `wpa_supplicant`, removes stale NetworkManager drop-ins | ✅ (oneshot) |
| `bazzite-powersave` | Sets the power profile over DBus (`power-saver`/`balanced`) — used by ujust/ppd integration | ✅ |
| `bazzite-privileged-user-setup` | Root-side user setup: enable NTP, allow Tailscale operator; invoked via polkit from user-setup | ✅ |
| `bazzite-snapper-config` | Snapper defaults (retention disabled; user opts in) — ujust wrappers | ✅ (snapper installed) |
| `bazzite-user-setup` | Per-user first-login setup (versioned): config markers, Templates symlinks (vkBasalt/dxvk/MangoHud examples), triggers the privileged helper | ✅ (user service, enabled) |
| `force-wol` | Forces Wake-on-LAN on wired NICs; service ships **disabled**, toggled via ujust | ⚠️ disabled by default |
| `hwsupport/sysid` | Normalizes DMI product names (e.g. truncates ROG Ally revisions) — shared by hardware setup and old waydroid defaults | ✅ for hardware setup |
| `ntfs-exfat-monitor-script` | Desktop notification nagging when game libraries are on NTFS/exFAT (unsupported for Proton) — links to docs | ⚠️ graphical session |
| `topgrade/third-party-css-loader-update` | topgrade custom command: git-pull user Steam theme repos (Adwaita-for-Steam etc.) | ⚠️ |
| `ublue-motd` | Renders the MOTD banner (image name, Greenboot health, random tip) via `glow` | ✅ |
| `uupd-update` | Front-end for `ujust update`: starts/attaches to `uupd-manual.service`, passes through exit code | ✅ |
| `waydroid-container-{start,stop,restart}`, `waydroid-fix-controllers` | Polkit-invoked privileged Waydroid container control + controller fix | ❌ waydroid absent |

## systemd, udev, sysctl and plumbing

### System units

| File | Why it exists | Needed? |
|---|---|---|
| `usr/lib/systemd/system/bazzite-hardware-setup.service` | Runs the hardware setup oneshot; ordering vs rpm-ostree/tuned | ✅ |
| `…/bazzite-iwd-migration.service` | Runs the WiFi migration before NetworkManager | ✅ |
| `…/bazzite-libvirtd-setup.service` | One-shot: enables libvirtd once after first boot then self-disables (permissions fix) | ⚠️ virt users |
| `…/beesd@.timer` | Daily timed beesd (dedup) run | ✅ |
| `…/cockpit.service` | Gate unit `Requires=` the podman cockpit container; toggled by ujust | ✅ |
| `…/dev-hugepages1G.mount` | Mounts 1G hugepages **when** `hugepagesz=1G` kernel arg is present (gaming/VM perf) | ✅ conditional |
| `…/force-wol.service` | Wires `force-wol` on network-online; disabled by default | ⚠️ |
| `…/fstrim.service.d/workaround-no-root-trim.conf` | fstrim workaround for immutable/atomic root (Fedora tracker #81) | ✅ |
| `…/incus-workaround.service` | SELinux label workaround for incus binaries: copy → bind-mount → restorecon (Universal Blue discourse) | ✅ (conditions on incus) |
| `…/kmod-sleep-workaround@.service` | Template to unload/reload a named module around sleep for devices with suspend bugs | ⚠️ opt-in template |
| `…/mcelog.service.d/override.conf` | Prevents mcelog running inside VMs (no MC errors there) | ✅ if mcelog present |
| `usr/lib/systemd/user/bazzite-user-setup.service` | Runs user setup at login | ✅ |
| `usr/lib/systemd/user/bazzite-dynamic-fixes.service` | Runs GPU workaround logic at login | ✅ |
| `usr/lib/systemd/user/ntfs-nag.service` | Starts the NTFS/exFAT notification at graphical session | ⚠️ |
| `usr/lib/systemd/user/steam-icons-cleanup.service` | One-shot each session: `ujust steam-icons remove` to prune dead Steam shortcuts (ublue-os/bazzite#3280) | ⚠️ |

### Sysctls

| File | Why it exists | Needed? |
|---|---|---|
| `usr/lib/sysctl.d/60-kernel.conf` | `split_lock_mitigate=0` — gaming performance | ✅ |
| `usr/lib/sysctl.d/70-gaming.conf` | `vm.max_map_count` raised — Proton/Wine large-memory games | ✅ |
| `usr/lib/sysctl.d/75-networking.conf` | BBR congestion control, MTU probing, IPv6 privacy addresses | ✅ |
| `usr/lib/sysctl.d/80-inotify.conf` | Higher inotify watch limits — dev tools, launchers, game file watchers | ✅ |

### udev, sysusers, tmpfiles, modprobe, dracut

| File | Why it exists | Needed? |
|---|---|---|
| `usr/lib/udev/rules.d/60-schedulers.rules` | I/O scheduler policy: kyber for SSD/NVMe, bfq for SD/HDD | ✅ |
| `usr/lib/udev/rules.d/90-dolphin-motion.rules` | `uaccess` tag for motion-sensor input devices | ❌ removed (device trim: no motion-sensor devices) |
| `usr/lib/sysusers.d/plugdev.conf` | Creates the `plugdev` group (46) that some device-access udev rules reference | ✅ |
| `usr/lib/tmpfiles.d/bazzite-libvirt.conf` | Persistent correct perms for `/var/log/libvirt` | ⚠️ virt |
| `usr/lib/tmpfiles.d/incus-workaround.conf` | Runtime copies backing the incus bind-mount workaround | ✅ |
| `usr/lib/modprobe.d/fw-charge-control.conf` | Framework charge-control probing | ❌ removed (device trim: not a Framework) |
| `usr/lib/modprobe.d/new-lg4ff.conf` | Blacklisted stock `hid_logitech` so the `new-lg4ff` kmod could take over | ❌ removed (device trim: no wheel, kmod dropped) |
| `usr/lib/modules-load.d/wine-ntsync.conf` | Loads the `ntsync` module (Wine NT synchronization primitives) | ✅ |
| `usr/lib/dracut/dracut.conf.d/80-vfio.conf` | Force-loads `vfio*` in initramfs (GPU passthrough setups) | ⚠️ harmless default |

### Tuned profiles

| File | Why it exists | Needed? |
|---|---|---|
| `usr/lib/tuned/profiles/balanced-bazzite/{tuned.conf,script.sh}` | "Balanced" PPD profile: inherits balanced, switches scx scheduler to auto on start | ✅ (wired via `ppd.conf` mappings in `configure-system-policy`) |
| `usr/lib/tuned/profiles/powersave-bazzite/{tuned.conf,script.sh}` | Power-saver profile + `panel_power_savings=0` tweak | ✅ |
| `usr/lib/tuned/profiles/throughput-performance-bazzite/{tuned.conf,script.sh}` | Performance profile with Bazzite summary/tweaks | ✅ |

## usr/share

Desktop entries, art, polkit, cockpit, bazaar, share/ublue-os, yafti.

| File | Why it exists | Needed? |
|---|---|---|
| `applications/bazzite-steam-bpm.desktop` | Menu entry launching Steam in Big Picture Mode (translated) | ⚠️ |
| `applications/bbrew.desktop` | Menu entry opening the bbrew TUI in a terminal | ⚠️ |
| `applications/waydroid-container-restart.desktop` | Menu entry: restart Waydroid container via pkexec | ❌ |
| `applications/Waydroid/{capsule,hero,icon,logo,store-capsule}.png` | Steam-library artwork so Waydroid looks native in Steam | ❌ |
| `containers/systemd/cockpit-container.container` | Podman Quadlet running the upstream `cockpit/ws` container (web admin UI) with host mounts | ✅ (cockpit pkgs installed) |
| `plymouth/themes/spinner/watermark.png` | Brand watermark on the boot splash | ✅ cosmetic |
| `polkit-1/actions/org.bazzite.privileged.user.setup.policy` | Defines the pkexec action for the privileged user-setup helper | ✅ |
| `polkit-1/actions/org.bazzite.waydroid.policy` | pkexec actions for Waydroid container control | ❌ |
| `polkit-1/rules.d/20-privileged-ruser.rules` | Lets `wheel` group run the setup helper without a prompt | ✅ |
| `polkit-1/rules.d/30-waydroid.rules` | Same for Waydroid actions | ❌ |
| `polkit-1/rules.d/90-corectrl.rules` | Passwordless CoreCtrl helper for `wheel` (fan control) | ❌ CoreCtrl isn't installed by this fork |
| `wireplumber/wireplumber.conf.d/51-disable-suspension.conf` | Disables ALSA node auto-suspension — prevents audio pops/latency for gamers | ⚠️ needs session |
| `firefox-config/01-bazzite-global.js` | Firefox defaults: hardware video decode on, ML/chat/reader features off (also reused by the Flatpak Firefox) | ⚠️ no RPM Firefox in image |
| `ublue-os/motd/env` + `motd/template.md` | MOTD banner data (image/ref, Greenboot health, random tip) and its template | ✅ |
| `ublue-os/topgrade.toml` | Main topgrade config: system (rpm-ostree) + brew + firmware + custom commands, assume-yes | ⚠️ |
| `ublue-os/bbrew.png` | Icon for the bbrew launcher | ⚠️ |
| `ublue-os/docs/serve` | Served the downloadable offline docs (`python -m http.server`) | ❌ removed (offline-docs feature dropped) |
| `ublue-os/bazaar/blocklist.yaml` | Hides from Bazaar what's already provided/replaced (Steam, Lutris, editors; DE-specific apps per session) | ✅ |
| `ublue-os/bazaar/content.yaml` | Curated Bazaar storefront (banner rows for gaming/music/office/streaming/utilities) | ✅ |
| `ublue-os/bazaar/{gaming,music,office,streaming,utilities}.jxl` | Banner images used by `content.yaml` | ✅ |
| `ublue-os/bazaar/hooks.py` | Bazaar transaction hooks (e.g. JetBrains "not supported in this format" dialog) | ✅ |
| `ublue-os/bazaar/main.yaml` | Bazaar main config: blocklist path, EOL override for OBS, hook registration | ✅ |
| `yafti/yafti.yml` | "Bazzite Portal" first-run flow definition (welcome, docs links, curated install scripts via flatpak/brew) | ⚠️ portal pkg present, needs session |

## usr/share/ublue-os/just

The 16 `ujust` recipe files — each ships one command group.

| File | Purpose | Needed? |
|---|---|---|
| `10-update.just` | `ujust update` (via uupd), changelogs | ✅ |
| `80-bazzite.just` | Big grab-bag: ssh toggle, snapper config, ramoops, watchdog, ntfs service toggle, etc. | ✅ |
| `81-bazzite-fixes.just` | Game/Steam fixes: GMod patch, kill Wine/Proton, WoL toggle | ✅ |
| `82-bazzite-apps.just` | Install/manage GUI apps via layering (CoolerControl, …) | ⚠️ |
| `82-bazzite-beesd.just` | `configure-beesd` — sized BTRFS dedup config per filesystem | ✅ |
| `82-bazzite-cockpit.just` | enable/disable/status Cockpit | ✅ |
| `82-bazzite-waydroid.just` | `configure-waydroid` helpers (init/gpu/reset) | ❌ |
| `83-bazzite-audio.just` | Create virtual PipeWire channels (Game/Voice/Browser/Music) for OBS | ⚠️ |
| `84-bazzite-virt.just` | `setup-virtualization` (libvirt/incus setup flows) | ✅ |
| `85-bazzite-image.just` | `restore-input-remapper` for non-desktop images | ⚠️ |
| `86-bazzite-windows.just` | Adds "boot Windows" shortcut to Steam (sudoers + nonsteam game) | ✅ |
| `87-bazzite-framegen.just` | Installs LSFG-VK (Lossless Scaling frame gen) | ⚠️ |
| `89-bazzite-mesa-git.just` | Fetch/install Mesa Git builds from mesa-maker | ⚠️ |
| `90-bazzite-picker.just` | Installs/runs the `ujust` interactive picker | ✅ |
| `92-bazzite-verify.just` | `verify-image` — rebases unverified images to the signed reference | ✅ |
| `93-bazzite-update.just` | Adds the updater to Steam BPM via `steamos-add-to-steam` | ⚠️ |
