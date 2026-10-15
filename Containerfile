# Bazzite is a Fedora Atomic system built and deployed as a complete bootable OCI image,
# rather than updated package-by-package on the live host. This recipe builds one DE-free
# gaming image with the NVIDIA open kernel modules; bootc and rpm-ostree provide staged updates
# and rollback.
# Keep the Containerfile build: the image uses multi-stage akmods inputs, bind mounts,
# package swaps, and one published NVIDIA image built from an internal common stage.
# Upstream Fedora release number
ARG FEDORA_VERSION="${FEDORA_VERSION:-44}"
# CPU target architecture
ARG ARCH="${ARCH:-x86_64}"

# Full registry URL to the upstream Universal Blue base image
ARG BASE_IMAGE="${BASE_IMAGE:-ghcr.io/ublue-os/base-main:${FEDORA_VERSION}}"
# Kernel modification flavor (ogc = Open Gaming Collective / fsync gaming kernel)
ARG KERNEL_FLAVOR="${KERNEL_FLAVOR:-ogc}"
# Exact kernel version matching pre-built akmods images
ARG KERNEL_VERSION="${KERNEL_VERSION:-7.2.7-ogc1.1.fc${FEDORA_VERSION}}"

# Pull pre-compiled out-of-tree hardware kernel modules (xone, v4l2loopback, openrazer, kvmfr)
FROM ghcr.io/ublue-os/akmods:${KERNEL_FLAVOR}-${FEDORA_VERSION}-${KERNEL_VERSION} AS akmods
# Pull extra hardware kernel modules (ryzen_smu, evdi, racing wheel drivers)
FROM ghcr.io/ublue-os/akmods-extra:${KERNEL_FLAVOR}-${FEDORA_VERSION}-${KERNEL_VERSION} AS akmods-extra
# Pull pre-compiled NVIDIA proprietary/open drivers matching this specific kernel
FROM ghcr.io/ublue-os/akmods-nvidia-open:${KERNEL_FLAVOR}-${FEDORA_VERSION}-${KERNEL_VERSION} AS akmods-nvidia
# Pull the latest pre-packaged Homebrew standalone root
FROM ghcr.io/ublue-os/brew:latest AS brew

# Build context helper: isolates build scripts so they can be bind-mounted without polluting image layers
FROM scratch AS ctx
COPY build_files /

################
# BAZZITE BASE
################

FROM ${BASE_IMAGE} AS bazzite

# Image name identifier
ARG IMAGE_NAME="${IMAGE_NAME:-bazzite-nvidia}"
# Image vendor namespace
ARG IMAGE_VENDOR="${IMAGE_VENDOR:-ublue-os}"
# Image release branch (stable, testing, unstable)
ARG IMAGE_BRANCH="${IMAGE_BRANCH:-stable}"
# Fedora release number (redeclared in this stage so RUN instructions can use it)
ARG FEDORA_VERSION="${FEDORA_VERSION:-44}"
# Build version tag
ARG VERSION_TAG="${VERSION_TAG}"
# Formatted user-facing version string
ARG VERSION_PRETTY="${VERSION_PRETTY}"
# Kernel version (redeclared so RUN steps can verify against it; empty on local builds)
ARG KERNEL_VERSION

# Keep the shared Bazzite configuration in the common stage.
COPY system_files/desktop/ /

# Use the standalone files exposed by the Homebrew image's /system_files tree.
COPY --from=brew /system_files/ /tmp/brew_files/
RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    /ctx/install-brew-files

# Install kernel
RUN --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/log \
    --mount=type=bind,from=akmods,src=/kernel-rpms,dst=/tmp/kernel-rpms \
    --mount=type=bind,from=akmods-extra,src=/rpms/kmods,dst=/tmp/rpms/kmods-extra \
    --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=tmpfs,dst=/tmp \
    /ctx/install-kernel-akmods && \
    KERNEL_VERSION="${KERNEL_VERSION}" /ctx/verify kernel && \
    /ctx/cleanup


# Configure repositories and package version locks used by later build steps.
RUN --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/cache/libdnf5 \
    --mount=type=cache,dst=/var/log \
    --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=tmpfs,dst=/tmp \
    /ctx/setup-repositories && \
    /ctx/verify repos && \
    /ctx/cleanup

# Install the patched gaming stack and its supporting codecs.
RUN --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/cache/libdnf5 \
    --mount=type=cache,dst=/var/log \
    --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=tmpfs,dst=/tmp \
    /ctx/install-gaming-stack && \
    /ctx/cleanup

# Remove packages superseded by image tooling.
RUN --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/cache/libdnf5 \
    --mount=type=cache,dst=/var/log \
    --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=tmpfs,dst=/tmp \
    /ctx/global-remove && \
    /ctx/cleanup

# Install shared gaming, hardware, and system utilities.
RUN --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/log \
    --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=tmpfs,dst=/tmp \
    --mount=type=secret,id=GITHUB_TOKEN \
    /ctx/install-common-packages && \
    /ctx/cleanup

# Install Steam, Lutris, gaming middleware, and Winetricks.
RUN --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/cache/libdnf5 \
    --mount=type=cache,dst=/var/log \
    --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=tmpfs,dst=/tmp \
    --mount=type=secret,id=GITHUB_TOKEN \
    /ctx/install-steam-lutris && \
    /ctx/verify packages && \
    /ctx/cleanup

# Install ujust-picker from the latest GitHub release.
RUN --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/cache/libdnf5 \
    --mount=type=cache,dst=/var/log \
    --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=tmpfs,dst=/tmp \
    --mount=type=secret,id=GITHUB_TOKEN \
    /ctx/install-ujust-picker && \
    /ctx/cleanup

# ublue-os-media-automount-udev, mount non-removable device partitions automatically under /media/media-automount/
RUN --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/cache/libdnf5 \
    --mount=type=cache,dst=/var/log \
    --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=tmpfs,dst=/tmp \
    /ctx/install-media-automount && \
    /ctx/cleanup

# Cleanup & Finalize
# Copy final system file overrides into root
COPY system_files/overrides/ /

# This pass applies shared defaults after packages and overlays are present, disables build-only
# repositories, and configures the services shipped in the image. Metadata, initramfs,
# and account finalization run last so they include all preceding changes.
RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    /ctx/configure-desktop-integration

RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    /ctx/import-bazzite-justfiles

RUN --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/log \
    --mount=type=bind,from=ctx,source=/,target=/ctx \
    /ctx/configure-system-policy

RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    /ctx/configure-system-services

RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=secret,id=GITHUB_TOKEN \
    /ctx/install-system-integration-files

RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    /ctx/image-info

RUN --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/log \
    --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=tmpfs,dst=/tmp \
    /ctx/build-initramfs

RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=tmpfs,dst=/tmp \
    /ctx/finalize

########################
# PUBLISHED NVIDIA IMAGE
########################

FROM bazzite AS bazzite-nvidia
# hadolint shell=bash

# Add NVIDIA driver packages matched to the kernel artifacts.

# NVIDIA image name identifier
ARG IMAGE_NAME="${IMAGE_NAME:-bazzite-nvidia}"
# NVIDIA image vendor namespace
ARG IMAGE_VENDOR="${IMAGE_VENDOR:-ublue-os}"
# NVIDIA image release branch
ARG IMAGE_BRANCH="${IMAGE_BRANCH:-stable}"
# Build version tag
ARG VERSION_TAG="${VERSION_TAG}"
# Formatted user-facing version string
ARG VERSION_PRETTY="${VERSION_PRETTY}"
# Kernel modification flavor
ARG KERNEL_FLAVOR="${KERNEL_FLAVOR:-ogc}"

# Fetch NVIDIA driver
# Copy NVIDIA driver configuration files into root.
COPY system_files/nvidia/ /

# Remove everything that doesn't work well with NVIDIA, unset skip_if_unavailable option if was set beforehand
RUN --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/log \
    --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=tmpfs,dst=/tmp \
    /ctx/configure-nvidia && \
    /ctx/cleanup

# Install NVIDIA driver
RUN --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/log \
    --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=bind,from=akmods-nvidia,src=/rpms,dst=/tmp/rpms/nvidia \
    --mount=type=tmpfs,dst=/tmp \
    --mount=type=secret,id=GITHUB_TOKEN \
    /ctx/install-nvidia-driver && \
    /ctx/verify nvidia && \
    /ctx/cleanup

# Cleanup & Finalize
RUN --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/log \
    --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=tmpfs,dst=/tmp \
    /ctx/finalize-nvidia

RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    /ctx/image-info

RUN --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/log \
    --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=tmpfs,dst=/tmp \
    /ctx/build-initramfs

RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=tmpfs,dst=/tmp \
    /ctx/finalize

# Verify the published image before the final lint gate.
RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    /ctx/verify final

RUN --mount=type=tmpfs,target=/run --network=none bootc container lint
