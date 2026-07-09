# armhf Runner Image (arm64 boot + 32-bit runner payload) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the image-builder's `armhf` path build an **arm64 boot image** that boots on the ps7 arm64 hosts and carries the **32-bit `linux-arm` runner agent** plus armhf multiarch userland, so it runs via the hosts' native AArch32.

**Architecture:** Decouple *boot architecture* from *runner architecture* for `Arch.ARM`: boot/base image becomes arm64 (glance `architecture=aarch64`), while the runner payload stays 32-bit (`RUNNER_ARCH=arm`, armhf multiarch libs). Remove the obsolete virtio glance-property workaround. All changes are TDD with signed commits.

**Tech Stack:** Python 3.12, pytest, Jinja2 cloud-init template, OpenStack SDK. Unit tests run **from the `app/` directory**: `~/.venv-armhf/bin/python -m pytest tests/unit`. Line length 99 (black / isort profile=black / flake8 --max-line-length=99). Signed commits: `git commit -S`.

**Repo/branch:** `~/github-runner-image-builder-operator`, branch `feat/armhf-arch-support-isd-5856` (PR #233).

**Spec:** `docs/superpowers/specs/2026-07-09-armhf-arm64-multiarch-image-design.md`

**Baseline:** 135 unit tests pass today (`cd app && ~/.venv-armhf/bin/python -m pytest tests/unit -q`). After this plan there are 133 (two obsolete virtio tests removed).

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `app/src/github_runner_image_builder/config.py` | Arch enum, glance arch mapping, apt package lists | `Arch.ARM.to_openstack()` → `aarch64`; `ARM_ADDITIONAL_APT_PACKAGES` → armhf-qualified deps |
| `app/src/github_runner_image_builder/cloud_image.py` | Base cloud-image download | `_get_supported_runner_arch(Arch.ARM)` → `arm64` |
| `app/src/github_runner_image_builder/store.py` | Upload image to glance | Remove `_ARM_IMAGE_PROPERTIES` + ARM virtio block |
| `app/src/github_runner_image_builder/templates/cloud-init.sh.j2` | Runner image provisioning | Add `enable_armhf_multiarch` + guarded call |
| `app/tests/unit/test_config.py` | config unit tests | ARM → `aarch64` |
| `app/tests/unit/test_cloud_image.py` | cloud_image unit tests | ARM → `arm64` |
| `app/tests/unit/test_store.py` | store unit tests | Remove the 2 virtio tests |
| `app/tests/unit/test_openstack_builder.py` | cloud-init render tests | New arm packages + multiarch function in expected string |

Notes:
- The integration test (`app/tests/integration/commands.py`) already asserts the runner binary is `ELF 32-bit ARM` and runs `rustc`/`cargo`/`docker buildx` for armhf. No integration-code change is required; the armhf leg simply needs to boot now.
- Tasks are ordered so each leaves the unit suite green.
- All commands below assume you start each task at the repo root `~/github-runner-image-builder-operator` unless the command itself `cd`s into `app`.

---

## Task 1: Glance architecture for armhf → aarch64

**Files:**
- Modify: `app/src/github_runner_image_builder/config.py` (`Arch.to_openstack`)
- Test: `app/tests/unit/test_config.py` (`test_arch_openstack_conversion`, ARM param ~L25)

- [ ] **Step 1: Update the failing test**

In `app/tests/unit/test_config.py`, change the ARM param:

```python
        pytest.param(Arch.ARM, "aarch64", id="arm"),
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app && ~/.venv-armhf/bin/python -m pytest tests/unit/test_config.py::test_arch_openstack_conversion -q`
Expected: FAIL — `assert 'armv7l' == 'aarch64'` for the `arm` param.

- [ ] **Step 3: Update `to_openstack`**

In `app/src/github_runner_image_builder/config.py`, replace the `Arch.ARM` case in `to_openstack`:

```python
            case Arch.ARM:
                # The armhf runner image is an arm64 boot image (64-bit kernel) that carries a
                # 32-bit linux-arm runner payload. Native armhf images (32-bit kernel) do not boot
                # on the aarch64 "virt" machine, so the glance architecture is aarch64 so the base
                # image and snapshot schedule and boot on arm64 hosts. The 32-bit runner is
                # installed via multiarch (see cloud-init.sh.j2 and ARM_ADDITIONAL_APT_PACKAGES).
                return "aarch64"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd app && ~/.venv-armhf/bin/python -m pytest tests/unit/test_config.py::test_arch_openstack_conversion -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/github-runner-image-builder-operator
git add app/src/github_runner_image_builder/config.py app/tests/unit/test_config.py
git commit -S -m "fix(armhf): map Arch.ARM glance architecture to aarch64

The armhf runner image is an arm64 boot image carrying a 32-bit runner
payload; native armhf (32-bit kernel) images do not boot on the aarch64
hosts. Schedule/boot the base image and snapshot as aarch64.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: Base cloud-image download for armhf → arm64

**Files:**
- Modify: `app/src/github_runner_image_builder/cloud_image.py` (`_get_supported_runner_arch`)
- Test: `app/tests/unit/test_cloud_image.py` (`test__get_supported_runner_arch`, ARM param ~L182)

- [ ] **Step 1: Update the failing test**

In `app/tests/unit/test_cloud_image.py`, change the ARM param of `test__get_supported_runner_arch`:

```python
        pytest.param(Arch.ARM, "arm64", id="ARM"),
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app && ~/.venv-armhf/bin/python -m pytest tests/unit/test_cloud_image.py::test__get_supported_runner_arch -q`
Expected: FAIL — `assert 'armhf' == 'arm64'` for the `ARM` param.

- [ ] **Step 3: Update `_get_supported_runner_arch`**

In `app/src/github_runner_image_builder/cloud_image.py`, replace the `Arch.ARM` case:

```python
        case Arch.ARM:
            # Download the arm64 (64-bit) base cloud image, not armhf. The armhf runner image is
            # an arm64 boot image (64-bit kernel) that runs the 32-bit linux-arm runner via
            # multiarch; a native armhf (32-bit kernel) image does not boot on the aarch64 hosts.
            return "arm64"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd app && ~/.venv-armhf/bin/python -m pytest tests/unit/test_cloud_image.py::test__get_supported_runner_arch -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/github-runner-image-builder-operator
git add app/src/github_runner_image_builder/cloud_image.py app/tests/unit/test_cloud_image.py
git commit -S -m "fix(armhf): download arm64 base cloud image for Arch.ARM

The builder VM must boot a 64-bit kernel on the aarch64 hosts. Download the
arm64 base cloud image; the 32-bit runner payload is added via multiarch.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: Remove obsolete virtio glance properties

**Files:**
- Modify: `app/src/github_runner_image_builder/store.py` (`_ARM_IMAGE_PROPERTIES` dict + ARM branch in `upload_image`)
- Test: `app/tests/unit/test_store.py` (remove `test_upload_image_arm_uses_virtio_properties` and `test_upload_image_amd64_omits_virtio_properties`, ~L240-286)

- [ ] **Step 1: Remove the two virtio tests**

In `app/tests/unit/test_store.py`, delete both functions in their entirety:
- `test_upload_image_arm_uses_virtio_properties` (~L240-263)
- `test_upload_image_amd64_omits_virtio_properties` (~L266-286)

Delete the blank lines so the file goes directly from the preceding test to `@pytest.mark.usefixtures("mock_connection")` (the `test_get_latest_image_id` block at ~L289). Leave the `from github_runner_image_builder.config import Arch` import in place (other tests still use `Arch`).

- [ ] **Step 2: Run tests to verify the remaining store tests still pass**

Run: `cd app && ~/.venv-armhf/bin/python -m pytest tests/unit/test_store.py -q`
Expected: PASS — 13 tests (was 15).

- [ ] **Step 3: Remove `_ARM_IMAGE_PROPERTIES` and the ARM branch**

In `app/src/github_runner_image_builder/store.py`:

Delete the entire comment block and dict definition of `_ARM_IMAGE_PROPERTIES` (the block that begins with the comment about 32-bit ARM base images and ends at the closing `}`).

Then in `upload_image`, make the properties unconditional. Replace the block that builds `image_properties` and conditionally updates it for `Arch.ARM` with:

```python
            logger.info("Uploading image %s.", image_name)
            image_properties = {"architecture": arch.to_openstack()}
            # ignore type since the library does not provide correct type hinting but the docstring
            # does define the return type.
            image: Image = connection.create_image(
```

(i.e. remove the `if arch == Arch.ARM: image_properties.update(_ARM_IMAGE_PROPERTIES)` lines. The `properties=image_properties` argument passed to `create_image` stays.)

- [ ] **Step 4: Run store tests + lint**

Run:
```bash
cd app && ~/.venv-armhf/bin/python -m pytest tests/unit/test_store.py -q \
  && ~/.venv-armhf/bin/python -m flake8 --max-line-length=99 \
     src/github_runner_image_builder/store.py tests/unit/test_store.py
```
Expected: 13 passed; no flake8 output.

- [ ] **Step 5: Commit**

```bash
cd ~/github-runner-image-builder-operator
git add app/src/github_runner_image_builder/store.py app/tests/unit/test_store.py
git commit -S -m "fix(armhf): drop obsolete virtio glance properties

With the armhf runner image now built from an arm64 base (64-bit kernel), it
boots with the cloud's normal defaults. The virtio-scsi/machine-type
workaround for booting a native armhf (32-bit kernel) image is no longer
needed.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4: armhf-qualified runtime dependencies

**Files:**
- Modify: `app/src/github_runner_image_builder/config.py` (`ARM_ADDITIONAL_APT_PACKAGES`)
- Test: `app/tests/unit/test_openstack_builder.py` (`test__generate_cloud_init_script` ARM param, ~L679-683)

- [ ] **Step 1: Update the failing test**

In `app/tests/unit/test_openstack_builder.py`, change the ARM param's `additional_apt_packages` list:

```python
        pytest.param(
            openstack_builder.Arch.ARM,
            ["libc6:armhf", "libicu74:armhf", "libatomic1:armhf", "rustup", "docker-buildx"],
            id="arm",
        ),
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app && ~/.venv-armhf/bin/python -m pytest "tests/unit/test_openstack_builder.py::test__generate_cloud_init_script[arm]" -q`
Expected: FAIL — the rendered `apt_packages` string still contains `libicu74 libatomic1 rustup docker-buildx` (arm64), not the `:armhf` variants.

- [ ] **Step 3: Update `ARM_ADDITIONAL_APT_PACKAGES`**

In `app/src/github_runner_image_builder/config.py`, replace the definition:

```python
# The 32-bit linux-arm runner agent runs via the host's native AArch32 support on the arm64
# image. It needs the armhf loader (ld-linux-armhf.so.3 from libc6:armhf) and the armhf builds of
# its .NET runtime dependencies (libicu, libatomic). rustup and docker-buildx are additionally
# pre-installed (arm64 host tools) for arm32 build workloads.
ARM_ADDITIONAL_APT_PACKAGES = [
    "libc6:armhf",
    "libicu74:armhf",
    "libatomic1:armhf",
    "rustup",
    "docker-buildx",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd app && ~/.venv-armhf/bin/python -m pytest "tests/unit/test_openstack_builder.py::test__generate_cloud_init_script[arm]" -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/github-runner-image-builder-operator
git add app/src/github_runner_image_builder/config.py app/tests/unit/test_openstack_builder.py
git commit -S -m "fix(armhf): install armhf-qualified runtime deps for the 32-bit runner

The 32-bit linux-arm runner agent needs the armhf loader (libc6:armhf) and
armhf builds of its .NET runtime deps (libicu74:armhf, libatomic1:armhf) to
exec on the arm64 image via native AArch32.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: Enable armhf multiarch in cloud-init

The 32-bit runner and its `:armhf` packages can only be installed after `dpkg --add-architecture armhf`. armhf packages are served by `ports.ubuntu.com`, which the arm64 base image already uses as its apt mirror, so no apt-source edit is needed — just the dpkg foreign architecture plus the `apt-get update` that `install_apt_packages` already runs.

**Files:**
- Modify: `app/src/github_runner_image_builder/templates/cloud-init.sh.j2` (add `enable_armhf_multiarch` function before `function install_apt_packages()`; add guarded call before the `install_apt_packages "$apt_packages" "$hwe_version"` call)
- Test: `app/tests/unit/test_openstack_builder.py` (`test__generate_cloud_init_script` expected f-string: add function definition ~before L775, add guarded call ~before L931)

- [ ] **Step 1: Update the failing test — add the function definition**

In `app/tests/unit/test_openstack_builder.py`, in the big expected f-string of `test__generate_cloud_init_script`, add the new function definition immediately **before** the `function install_apt_packages() {{` line (~L775). Note the doubled braces `{{`/`}}` because this is an f-string:

```python
function enable_armhf_multiarch() {{
    echo "Enabling armhf multiarch"
    /usr/bin/dpkg --add-architecture armhf
}}

function install_apt_packages() {{
```

- [ ] **Step 2: Update the failing test — add the guarded call**

In the same expected f-string, change the call sequence (~L930-931) from:

```python
configure_proxy "$proxy"
install_apt_packages "$apt_packages" "$hwe_version"
```

to:

```python
configure_proxy "$proxy"
# Enable armhf multiarch before installing packages so the 32-bit linux-arm runner agent and
# its armhf runtime dependencies can be installed and executed via native AArch32.
if [ "$github_runner_arch" == "arm" ]; then
    enable_armhf_multiarch
fi
install_apt_packages "$apt_packages" "$hwe_version"
```

(No brace-escaping needed here — there are no literal `{`/`}` in these lines.)

- [ ] **Step 3: Run test to verify it fails**

Run: `cd app && ~/.venv-armhf/bin/python -m pytest tests/unit/test_openstack_builder.py::test__generate_cloud_init_script -q`
Expected: FAIL for all 5 params — the rendered template does not yet contain `enable_armhf_multiarch` (neither the definition nor the guarded call).

- [ ] **Step 4: Add the function to the template**

In `app/src/github_runner_image_builder/templates/cloud-init.sh.j2`, add the function immediately **before** `function install_apt_packages() {` (currently ~L55):

```bash
function enable_armhf_multiarch() {
    echo "Enabling armhf multiarch"
    /usr/bin/dpkg --add-architecture armhf
}

function install_apt_packages() {
```

- [ ] **Step 5: Add the guarded call in the template**

In the same file, change the call sequence at the bottom from:

```bash
configure_proxy "$proxy"
install_apt_packages "$apt_packages" "$hwe_version"
```

to:

```bash
configure_proxy "$proxy"
# Enable armhf multiarch before installing packages so the 32-bit linux-arm runner agent and
# its armhf runtime dependencies can be installed and executed via native AArch32.
if [ "$github_runner_arch" == "arm" ]; then
    enable_armhf_multiarch
fi
install_apt_packages "$apt_packages" "$hwe_version"
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd app && ~/.venv-armhf/bin/python -m pytest tests/unit/test_openstack_builder.py::test__generate_cloud_init_script -q`
Expected: PASS (all 5 params).

- [ ] **Step 7: Commit**

```bash
cd ~/github-runner-image-builder-operator
git add app/src/github_runner_image_builder/templates/cloud-init.sh.j2 app/tests/unit/test_openstack_builder.py
git commit -S -m "feat(armhf): enable armhf multiarch in cloud-init

Add dpkg --add-architecture armhf (guarded to the arm runner) before apt
install so the arm64 image can install and run the 32-bit linux-arm runner
and its armhf runtime deps via native AArch32. armhf packages are served by
ports.ubuntu.com, which the arm64 base already uses.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 6: Full verification and push

**Files:** none (verification only)

- [ ] **Step 1: Run the full unit suite**

Run: `cd app && ~/.venv-armhf/bin/python -m pytest tests/unit -q`
Expected: PASS — 133 tests (135 baseline minus the 2 removed virtio tests).

- [ ] **Step 2: Format**

Run:
```bash
cd app && ~/.venv-armhf/bin/python -m black --line-length 99 \
    src/github_runner_image_builder tests/unit \
  && ~/.venv-armhf/bin/python -m isort --profile black \
    src/github_runner_image_builder tests/unit
```
Expected: "All done" (files unchanged or reformatted).

- [ ] **Step 3: Lint**

Run:
```bash
cd app && ~/.venv-armhf/bin/python -m flake8 --max-line-length=99 \
    src/github_runner_image_builder tests/unit
```
Expected: no output.

- [ ] **Step 4: Commit any formatting-only changes (if any)**

```bash
cd ~/github-runner-image-builder-operator
git add -A app
git diff --cached --quiet || git commit -S -m "style(armhf): apply black/isort formatting

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

- [ ] **Step 5: Push**

```bash
cd ~/github-runner-image-builder-operator
git push "https://x-access-token:$(gh auth token)@github.com/canonical/github-runner-image-builder-operator.git" feat/armhf-arch-support-isd-5856
```
Expected: branch updated on origin; CI "Integration tests for application" starts.

- [ ] **Step 6: Verify the armhf integration legs boot**

After CI starts, confirm the armhf legs no longer fail at server-create/SSH. The armhf builder VM should now boot (64-bit kernel), cloud-init should install the 32-bit runner + armhf libs, and the `commands.py` armhf assertions (`file … Runner.Listener` = ELF 32-bit ARM, `rustc`/`cargo`/`docker buildx`) should pass.

Poll job statuses (replace `<RID>` with the run id):
```bash
gh api repos/canonical/github-runner-image-builder-operator/actions/runs/<RID>/jobs \
  --paginate --jq '.jobs[] | select(.name|test("arm")) | "\(.name)=\(.status)/\(.conclusion)"'
```
Expected: eventually `completed/success` for the armhf legs.

---

## Rollback / supersedes

This plan supersedes the two virtio commits already on the branch (`store.py` `_ARM_IMAGE_PROPERTIES`) and the `armv7l` glance arch / `armhf` base-image download. Those are removed/replaced by the arm64-boot + multiarch model. Runner PRs #155/#169/#171 are unchanged; this plan consumes their 32-bit `linux-arm` package.

## Open risks (validated during CI, not before)

- **armhf package names on noble arm64:** `libc6:armhf`, `libicu74:armhf`, `libatomic1:armhf` are assumed present on `ports.ubuntu.com` for noble/resolute. If a name differs on resolute, the armhf leg's apt install will fail with a clear "unable to locate package" error — adjust the name in `ARM_ADDITIONAL_APT_PACKAGES` and re-push.
- **apt sources architecture restriction:** if the arm64 base's deb822 sources ever pin `Architectures: arm64`, `dpkg --add-architecture armhf` alone won't fetch armhf lists. The default noble/resolute arm64 sources do NOT pin architectures, so this is expected to work; if apt update errors on missing armhf lists, add an armhf-scoped `ports.ubuntu.com` source in `enable_armhf_multiarch`.
