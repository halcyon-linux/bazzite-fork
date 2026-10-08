from itertools import product
import subprocess
import json
import os
import tempfile
import time
from typing import Any
import re
from collections import defaultdict

REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "halcyon-linux/bazzite-fork")
REGISTRY = f"ghcr.io/{REPOSITORY.split('/')[0].lower()}/"

IMAGES = [
    "bazzite-nvidia",
]

RETRIES = 3
RETRY_WAIT = 5
FEDORA_PATTERN = re.compile(r"\.fc\d\d")
EPOCH_PATTERN = re.compile(r"^\d+:")
STABLE_START_PATTERN = re.compile(r"\d\d\.\d")
OTHER_START_PATTERN = lambda target: re.compile(rf"{target}-\d\d\.\d")
TAG_NUM_PATTERN = re.compile(r"(\d+)")
PKGREL_PATTERN = re.compile(r"\{pkgrel:[^}]+\}")
PATTERN_ADD = "\n| ✨ | {name} | | {version} |"
PATTERN_CHANGE = "\n| 🔄 | {name} | {prev} | {new} |"
PATTERN_REMOVE = "\n| ❌ | {name} | {version} | |"
PATTERN_PKGREL_CHANGED = "{prev} ➡️ {new}"
PATTERN_PKGREL = "{version}"
COMMON_PAT = "### bazzite-nvidia\n| | Name | Previous | New |\n| --- | --- | --- | --- |{changes}\n\n"

COMMITS_FORMAT = (
    "### Commits\n| Hash | Subject | Author |\n| --- | --- | --- |{commits}\n\n"
)
COMMIT_FORMAT = f"\n| **[{{short}}](https://github.com/{REPOSITORY}/commit/{{hash}})** | {{subject}} | {{author}} |"

CHANGELOG_TITLE = "{tag}: {pretty}"
CHANGELOG_FORMAT = """\
{handwritten}

From previous `{target}` version `{prev}` there have been the following changes. **One package per new version shown.**

### Major packages
| Name | Version |
| --- | --- |
| **Kernel** | {pkgrel:kernel-core} |
| **Firmware** | {pkgrel:atheros-firmware} |
| **Mesa** | {pkgrel:mesa-filesystem} |
| **Gamescope** | {pkgrel:terra-gamescope} |
| **MangoHUD** | {pkgrel:terra-mangohud} |
| **UMU Launcher** | {pkgrel:umu-launcher} |
| **Bazaar** | {pkgrel:bazaar} |
| **Distrobox** | {pkgrel:distrobox} |
| **Waydroid** | {pkgrel:waydroid} |
| **Waydroid (Nvidia)** | {pkgrel:waydroid-nvidia} |
| **Nvidia Open** | {pkgrel:nvidia-kmod-common} |
{changes}

### How to rebase
For current users, type the following to rebase to this version:
```bash
# For this branch (if latest):
bazzite-rollback-helper rebase {target}
# For this specific image:
bazzite-rollback-helper rebase {curr}
```
"""
HANDWRITTEN_PLACEHOLDER = """\
This is an automatically generated changelog for release `{curr}`."""

BLACKLIST_VERSIONS = [
    "kernel",
    "kernel-core",
    "mesa-filesystem",
    "terra-gamescope",
    "bazaar",
    "atheros-firmware",
    "nvidia-kmod-common",
]

PKG_ALIAS = {
}


def get_images():
    for img in IMAGES:
        yield img


def get_manifests(target: str):
    out = {}
    imgs = list(get_images())
    for j, img in enumerate(imgs):
        output = None
        print(f"Getting {img}:{target} manifest ({j+1}/{len(imgs)}).")
        for i in range(RETRIES):
            try:
                output = subprocess.run(
                    ["skopeo", "inspect", "docker://" + REGISTRY + img + ":" + target],
                    check=True,
                    stdout=subprocess.PIPE,
                ).stdout
                break
            except subprocess.CalledProcessError:
                print(
                    f"Failed to get {img}:{target}, retrying in {RETRY_WAIT} seconds ({i+1}/{RETRIES})"
                )
                time.sleep(RETRY_WAIT)
        if output is None:
            print(f"Failed to get {img}:{target}, skipping")
            continue
        out[img] = json.loads(output)
    return out


def get_image_digest(image: str, tag: str) -> str:
    """Get image digest using skopeo."""
    result = subprocess.run(
        ["skopeo", "inspect", f"docker://{image}:{tag}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)["Digest"]


def get_sbom(image: str, digest: str) -> dict:
    """Fetch SBOM using ORAS."""
    full_ref = f"{image}@{digest}"

    result = subprocess.run(
        ["oras", "discover", "--format", "json", full_ref],
        capture_output=True,
        text=True,
        check=True,
    )
    discovered = json.loads(result.stdout)

    sbom_digest = None
    for referrer in discovered.get("referrers", []):
        if "spdx+json" in referrer.get("artifactType", ""):
            sbom_digest = referrer["digest"]
            break

    if sbom_digest is None:
        raise RuntimeError(f"No SBOM referrer found for {full_ref}")

    sbom_ref = f"{image}@{sbom_digest}"

    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            ["oras", "pull", sbom_ref],
            capture_output=True,
            check=True,
            cwd=tmpdir,
        )

        for fname in os.listdir(tmpdir):
            fpath = os.path.join(tmpdir, fname)
            if fname.endswith(".zst"):
                result = subprocess.run(
                    ["zstd", "-d", fpath, "--stdout"],
                    capture_output=True,
                    check=True,
                )
                return json.loads(result.stdout)
            elif fname.endswith(".json"):
                with open(fpath) as f:
                    return json.load(f)

    raise RuntimeError(f"No SBOM file found after pulling {sbom_ref}")


def parse_sbom_packages(sbom: dict) -> dict[str, str]:
    """Parse RPM packages from a Syft-format SBOM."""
    packages = {}
    for artifact in sbom.get("artifacts", []):
        if artifact.get("type") != "rpm":
            continue
        name = artifact.get("name")
        version = artifact.get("version")
        if name and version:
            if name not in packages or (":" in version and ":" not in packages[name]):
                packages[name] = version
    return packages


def tag_sort_key(tag: str):
    """Order tags numerically, so that e.g. `.10` sorts after `.2`."""
    return [
        int(part) if part.isdigit() else part
        for part in re.split(TAG_NUM_PATTERN, tag)
    ]


def get_release_tag(manifests: dict[str, Any]):
    versions = set()
    for img, manifest in manifests.items():
        version = manifest.get("Labels", {}).get("org.opencontainers.image.version")
        if version:
            versions.add(version)
        else:
            print(f"Warning: {img} has no version label")

    assert versions, "No image carries a version label"
    if len(versions) > 1:
        print(f"Warning: images disagree on the version tag: {sorted(versions)}")
    return max(versions, key=tag_sort_key)


def get_prev_tag(target: str, manifests: dict[str, Any], curr: str):
    tags = set()

    # Select random manifest to get reference tags from
    first = next(iter(manifests.values()))
    for tag in first["RepoTags"]:
        # Tags ending with .0 should not exist
        if tag.endswith(".0"):
            continue
        if target != "stable":
            if re.match(OTHER_START_PATTERN(target), tag):
                tags.add(tag)
        else:
            if re.match(STABLE_START_PATTERN, tag):
                tags.add(tag)

    # Remove tags not present in all images
    for manifest in manifests.values():
        for tag in list(tags):
            if tag not in manifest["RepoTags"]:
                tags.remove(tag)

    curr_key = tag_sort_key(curr)
    tags = sorted(
        (t for t in tags if tag_sort_key(t) < curr_key), key=tag_sort_key
    )
    assert tags, f"No tag older than {curr} found"
    return tags[-1]


def get_packages(tag: str):
    packages = {}
    imgs = list(get_images())
    for j, img in enumerate(imgs):
        print(f"Getting packages for {img}:{tag} via SBOM ({j+1}/{len(imgs)})")
        try:
            full_image = REGISTRY + img
            digest = get_image_digest(full_image, tag)
            sbom = get_sbom(full_image, digest)
            packages[img] = parse_sbom_packages(sbom)
            print(f"  Found {len(packages[img])} packages")
        except Exception as e:
            print(f"  Failed to get packages for {img}:{tag}: {e}")
            raise
    return packages


def get_package_groups(prev_tag: str, curr_ref: str):
    print(f"\nFetching current packages for {curr_ref}...")
    current_packages = get_packages(curr_ref)
    print(f"\nFetching previous packages for {prev_tag}...")
    previous_packages = get_packages(prev_tag)

    image = IMAGES[0]
    package_names = set(current_packages.get(image, {})) | set(
        previous_packages.get(image, {})
    )
    return sorted(package_names), current_packages, previous_packages


def get_versions(packages: dict[str, dict[str, str]]):
    versions = {}
    for image_packages in packages.values():
        for package, version in image_packages.items():
            version = re.sub(EPOCH_PATTERN, "", version)
            versions[package] = re.sub(FEDORA_PATTERN, "", version)
    return versions


def calculate_changes(pkgs: list[str], prev: dict[str, str], curr: dict[str, str]):
    added = []
    changed = []
    removed = []

    blacklist_ver = set([curr.get(v, None) for v in BLACKLIST_VERSIONS])

    for pkg in pkgs:
        # Clearup changelog by removing mentioned packages
        if pkg in BLACKLIST_VERSIONS:
            continue
        if pkg in curr and curr.get(pkg, None) in blacklist_ver:
            continue
        if pkg in prev and prev.get(pkg, None) in blacklist_ver:
            continue
        if pkg.endswith("-lts"):
            continue

        if pkg not in prev:
            added.append(pkg)
        elif pkg not in curr:
            removed.append(pkg)
        elif prev[pkg] != curr[pkg]:
            changed.append(pkg)

        blacklist_ver.add(curr.get(pkg, None))
        blacklist_ver.add(prev.get(pkg, None))

    out = ""
    for pkg in added:
        out += PATTERN_ADD.format(name=pkg, version=curr[pkg])
    for pkg in changed:
        out += PATTERN_CHANGE.format(name=pkg, prev=prev[pkg], new=curr[pkg])
    for pkg in removed:
        out += PATTERN_REMOVE.format(name=pkg, version=prev[pkg])
    return out


def get_commits(prev_manifests, manifests, workdir: str):
    try:
        start = next(iter(prev_manifests.values()))["Labels"][
            "org.opencontainers.image.revision"
        ]
        finish = next(iter(manifests.values()))["Labels"][
            "org.opencontainers.image.revision"
        ]

        commits = subprocess.run(
            [
                "git",
                "-C",
                workdir,
                "log",
                "--pretty=format:%H|%h|%an|%s",
                f"{start}..{finish}",
            ],
            check=True,
            stdout=subprocess.PIPE,
        ).stdout.decode("utf-8")

        out = ""
        for commit in commits.split("\n"):
            if not commit:
                continue
            parts = commit.split("|")
            if len(parts) < 4:
                continue
            commit_hash, short, author, subject = parts

            if subject.lower().startswith("merge"):
                continue

            out += (
                COMMIT_FORMAT.replace("{short}", short)
                .replace("{subject}", subject)
                .replace("{hash}", commit_hash)
                .replace("{author}", author)
            )

        if out:
            return COMMITS_FORMAT.format(commits=out)
        return ""
    except Exception as e:
        print(f"Failed to get commits:\n{e}")
        return ""


def generate_changelog(
    handwritten: str | None,
    target: str,
    pretty: str | None,
    workdir: str,
    prev_tag: str,
    curr_tag: str,
    prev_manifests,
    manifests,
):
    packages, curr_packages, prev_packages = get_package_groups(prev_tag, target)
    versions = get_versions(curr_packages)
    prev_versions = get_versions(prev_packages)

    prev, curr = prev_tag, curr_tag

    if not pretty:
        # Generate pretty version since we dont have it
        try:
            finish: str = next(iter(manifests.values()))["Labels"][
                "org.opencontainers.image.revision"
            ]
        except Exception as e:
            print(f"Failed to get finish hash:\n{e}")
            finish = ""

        # Remove .0 from curr
        curr_pretty = re.sub(r"\.\d{1,2}$", "", curr)
        # Remove target- from curr
        curr_pretty = re.sub(rf"^[a-z]+-", "", curr_pretty)
        pretty = target.capitalize() + " (F" + curr_pretty
        if finish and target != "stable":
            pretty += ", #" + finish[:7]
        pretty += ")"

    title = CHANGELOG_TITLE.format_map(defaultdict(str, tag=curr, pretty=pretty))

    changelog = CHANGELOG_FORMAT

    changelog = (
        changelog.replace(
            "{handwritten}", handwritten if handwritten else HANDWRITTEN_PLACEHOLDER
        )
        .replace("{target}", target)
        .replace("{prev}", prev)
        .replace("{curr}", curr)
    )

    for pkg, v in versions.items():
        if pkg not in prev_versions or prev_versions[pkg] == v:
            changelog = changelog.replace(
                "{pkgrel:" + (PKG_ALIAS.get(pkg, None) or pkg) + "}",
                PATTERN_PKGREL.format(version=v),
            )
        else:
            changelog = changelog.replace(
                "{pkgrel:" + (PKG_ALIAS.get(pkg, None) or pkg) + "}",
                PATTERN_PKGREL_CHANGED.format(prev=prev_versions[pkg], new=v),
            )

    changelog = re.sub(PKGREL_PATTERN, "N/A", changelog)

    changes = ""
    changes += get_commits(prev_manifests, manifests, workdir)
    image_changes = calculate_changes(packages, prev_versions, versions)
    if image_changes:
        changes += COMMON_PAT.format(changes=image_changes)

    changelog = changelog.replace("{changes}", changes)

    return title, changelog


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("target", help="Target tag")
    parser.add_argument("output", help="Output environment file")
    parser.add_argument("changelog", help="Output changelog file")
    parser.add_argument("--pretty", help="Subject for the changelog")
    parser.add_argument("--workdir", help="Git directory for commits")
    parser.add_argument("--handwritten", help="Handwritten changelog")
    args = parser.parse_args()

    # Remove refs/tags, refs/heads, refs/remotes e.g.
    # Tags cannot include / anyway.
    target = args.target.split("/")[-1]

    if target == "main":
        target = "stable"

    manifests = get_manifests(target)
    curr = get_release_tag(manifests)
    prev = get_prev_tag(target, manifests, curr)
    print(f"Previous tag: {prev}")
    print(f" Current tag: {curr}")

    prev_manifests = get_manifests(prev)
    title, changelog = generate_changelog(
        args.handwritten,
        target,
        args.pretty,
        args.workdir,
        prev,
        curr,
        prev_manifests,
        manifests,
    )

    print(f"Changelog:\n# {title}\n{changelog}")
    print(f'\nOutput:\nTITLE="{title}"\nTAG={curr}')

    with open(args.changelog, "w") as f:
        f.write(changelog)

    with open(args.output, "w") as f:
        f.write(f'TITLE="{title}"\nTAG={curr}\n')


if __name__ == "__main__":
    main()
