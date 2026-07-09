# armhf Runner Image via arm64 Boot Image + 32-bit Runner Payload

- **Date:** 2026-07-09
- **Status:** Approved (design)
- **Related:** PR #233 (image-builder armhf support), runner PRs #155/#169/#171
- **Spec:** ISD-5856

> Note: this design runs 32-bit armhf userland **natively** via the hosts' AArch32
> support (AArch32@EL0) using Ubuntu multiarch — it does **not** use qemu emulation.

## Problem

The image-builder's `Arch.ARM` (armhf) path builds a **native armhf image** — it
downloads `<base>-server-cloudimg-armhf.img` (a 32-bit ARM kernel) and boots it as a
full VM on the ProdStack 7 (ps7) arm64 compute hosts. That VM never boots: Nova marks
it `ACTIVE` and neutron assigns an IP, but the serial console is **completely empty**
and SSH times out forever.

### Root cause

Booting a full armhf VM requires a **32-bit kernel** to start under the aarch64 `virt`
machine's 64-bit UEFI firmware (i.e. AArch32 at EL1 and/or a 32-bit boot chain). The
ps7 hosts do **not** provide this, so the 32-bit kernel never executes → empty console.

This is **not** a hardware limitation for armhf *workloads*. The same ps7 hosts do
support **AArch32 at EL0** (32-bit userland), proven by the merged runner work:

- PR #155: the runner was "Built and run on an arm64 VM with AArch32 (native 32-bit)
  userspace, inside an `arm32v7/ubuntu:noble` container … binaries run natively as
  armhf (no qemu)."
- PR #169/#171: the shipped `linux-arm` (armv7l, 32-bit) package is smoke-tested by
  running `./config.sh --version` inside an `arm32v7/ubuntu:noble` container on the
  arm64 self-hosted pool, "natively via the host's AArch32 support (no qemu)."

The proven-working model is therefore an **arm64 kernel (64-bit) running 32-bit armhf
userland**, which needs only AArch32@EL0 (available). The image-builder instead builds
a 32-bit-kernel image (needs AArch32@EL1 / 32-bit boot — unavailable). It builds the
wrong kind of image.

## Goal

Make the image-builder's "armhf runner" image reproduce the validated model: an
**arm64 boot image** that carries the **32-bit `linux-arm` runner agent** plus the
armhf multiarch userland it needs, running via the hosts' native AArch32. armhf jobs
build/test armhf binaries and run `linux/arm/v7` containers.

Non-goals: full-system emulation (`qemu-system-arm`); a qemu-user portability fallback
(all target hosts are verified AArch32-capable, so native execution is used).

## Design

### Core reframing: boot architecture vs runner architecture

For every architecture except armhf, the architecture the builder VM **boots** equals
the architecture of the **runner payload**. For `Arch.ARM` they diverge:

| Aspect | Current (broken) | New |
|---|---|---|
| Base cloud image | `…-cloudimg-armhf.img` (32-bit kernel) | `…-cloudimg-arm64.img` (64-bit kernel) |
| Glance `architecture` property | `armv7l` | `aarch64` |
| Builder / runner flavor | `shared.xsmall.arm64` | unchanged |
| Boots on ps7 hosts | No (empty console) | Yes (normal arm64 boot) |
| Runner agent installed | `linux-arm` (32-bit) | `linux-arm` (32-bit) — unchanged |
| armhf userland | none | armhf multiarch libs |
| virtio glance props | required (still failed) | removed |

`Arch.ARM` continues to mean "produce a 32-bit ARM runner"; it is now delivered as an
arm64 image carrying a 32-bit runner + armhf multiarch userland, executed via native
AArch32.

### Component changes

1. **`config.py`**
   - `Arch.ARM.to_openstack()` returns **`aarch64`** (was `armv7l`) so the base image
     and snapshot schedule/boot on arm64 hosts. Update the outdated `armv7l` comment.
   - `Arch.ARM.value` stays `"arm"` (drives the 32-bit runner tarball download and the
     `github_runner_arch` cloud-init variable).
   - `ARM_ADDITIONAL_APT_PACKAGES` becomes the **armhf-qualified** runtime deps for the
     32-bit runner agent plus arm64 host tools:
     `["libc6:armhf", "libicu74:armhf", "libatomic1:armhf", "rustup", "docker-buildx"]`.
     (`libc6:armhf` provides `/lib/ld-linux-armhf.so.3`; `libicu74:armhf` and
     `libatomic1:armhf` are the .NET runtime deps the armv7l runner needs — see #169.)

2. **`cloud_image.py`**
   - `_get_supported_runner_arch(Arch.ARM)` returns **`arm64`** (was `armhf`), so the
     builder VM boots a 64-bit kernel. This is the direct fix for the empty-console
     failure. Update the docstring/comment accordingly.

3. **`store.py`**
   - Remove `_ARM_IMAGE_PROPERTIES` and the `if arch == Arch.ARM` block; revert
     `upload_image` to `properties={"architecture": arch.to_openstack()}`. An arm64
     image boots with the cloud's normal defaults, so the IDE/virtio workaround is
     obsolete.

4. **`openstack_builder.py`**
   - `_generate_cloud_init_script` keeps `RUNNER_ARCH="arm"` and the noble+ base-image
     guard (`ARM_SUPPORTED_BASE_IMAGES`). The armhf multiarch enablement is expressed in
     the cloud-init template (below); no change to the flavor logic (already arm64).

5. **`templates/cloud-init.sh.j2`**
   - Add an armhf-only step, guarded by `[ "$github_runner_arch" == "arm" ]`, run
     **before** `install_apt_packages`:
     - `dpkg --add-architecture armhf`
     - Ensure the apt sources serve armhf. arm64 Ubuntu already uses
       `ports.ubuntu.com`, which also hosts armhf; add `armhf` to the sources'
       architectures (deb822 `Architectures:` on noble+, or an `[arch=armhf]` entry).
     - `apt-get update`
   - The armhf-qualified libs then install via the normal `install_apt_packages` path;
     the existing `install_github_runner` (arch `arm`) downloads the 32-bit tarball; the
     existing `rustup default stable` armhf block stays.

### Data flow

```
download arm64 cloud image ──▶ upload base (architecture=aarch64)
        │
        ▼
create builder VM (shared.xsmall.arm64)  ── boots 64-bit kernel ✅
        │
        ▼
cloud-init:
  enable armhf multiarch (dpkg --add-architecture armhf; apt update)
  install libc6:armhf + armhf runtime deps + host tools
  install linux-arm (32-bit) runner agent   ── runs via native AArch32@EL0
        │
        ▼
snapshot ──▶ upload runner image (architecture=aarch64)
```

### Error handling

- Non-noble bases for armhf still fail fast with `UnsupportedArchitectureError` (the
  armhf-qualified libs require noble/24.04+).
- If a host genuinely lacked AArch32, the 32-bit runner agent would fail to `exec`;
  since all target hosts are verified AArch32-capable, no fallback is provided (matches
  #169's stated assumption).

## Testing

### Unit
- `test_store.py`: revert/remove the two virtio-property tests; assert `upload_image`
  passes only `properties={"architecture": …}`.
- `test_cloud_image.py`: `Arch.ARM` downloads the `arm64` base image filename.
- `test_config.py`: `Arch.ARM.to_openstack()` returns `aarch64`;
  `ARM_ADDITIONAL_APT_PACKAGES` contains the armhf-qualified deps.
- `test_openstack_builder.py`: generated cloud-init for `Arch.ARM` enables armhf
  multiarch and still sets `RUNNER_ARCH=arm`; non-noble armhf base raises.

### Integration (ps7 arm64 tenant)
- The armhf leg now **boots** (previously the entire failure mode).
- Assert the produced image is arm64 and the baked 32-bit runner agent is armv7l and
  executable — e.g. `file .../bin/Runner.Listener` reports "ARM, EABI5 32-bit" and/or
  `./config.sh --version` runs (mirroring #169's container smoke test).

## Rollback / supersedes

This supersedes the native-armhf commits on branch `feat/armhf-arch-support-isd-5856`
(virtio glance properties in `store.py`, `armv7l` glance arch, `armhf` base-image
download). Those are reverted/replaced by the arm64-boot + multiarch model here. The
runner-side PRs (#155/#169/#171) are unchanged — this design consumes their 32-bit
`linux-arm` package exactly as they built it.
