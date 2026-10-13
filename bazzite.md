# Build walkthrough

This repository builds one published image, `bazzite-nvidia`, from Universal Blue's `base-main`. The Containerfile's `bazzite` stage is an internal common stage; only the final NVIDIA target is published. The image currently has no desktop environment or compositor, with Hyprland planned later.

## Build flow

1. `Containerfile` pulls the OGC kernel module inputs and starts the internal `bazzite` stage from `base-main`.
2. It installs shared Bazzite packages and system integration files by running the focused scripts in `build_files/`.
3. The base stage runs `image-info`, `build-initramfs`, and `finalize` in order.
4. The `bazzite-nvidia` target applies the shared NVIDIA overlay, prepares the repositories, installs the `nvidia-open` driver, and applies NVIDIA-specific final configuration.
5. The final target writes image metadata, rebuilds the initramfs, finalizes accounts, and runs `bootc container lint`.

## Build scripts

Scripts under `build_files/` are mounted into individual Containerfile `RUN` steps from the temporary `ctx` stage. They do not call one another as section orchestrators. The common stage groups package installation, repository setup, system policy, service configuration, and integration downloads. The NVIDIA stage uses `configure-nvidia`, `install-nvidia-driver`, and `finalize-nvidia`.

## Local defaults and CI

`Justfile` and `just_scripts/get-defaults` select `bazzite-nvidia` by default and reject other image targets. The GitHub build and cleanup workflows both refer to that same image.

Build the image locally with:

```bash
just build
```

The repository builds and publishes the custom `bazzite-nvidia` container image; it has no ISO build path, desktop-environment selection, or variant-specific overlay.
