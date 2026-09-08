# Case Report: Buildroot Submodule SHA Drift Breaking CI (`aeld-assignment-4`)

**Repo:** `github.com/prashantgautamofficial/aeld-assignment-4`
**Environment:** Self-hosted GitHub Actions runner, Docker container
**Failing step:** `Checkout submodules` (`git submodule update --init --recursive`)
**Status:** Resolved

---

## 1. Symptom

The `Checkout submodules` step failed with exit code 128, causing every
downstream step (`webfactory/ssh-agent`, `Run full test`) to be skipped
entirely:

```
Run git submodule update --init --recursive
  git submodule update --init --recursive
  shell: sh -e {0}

fatal: remote error: upload-pack: not our ref bd668a433be69dd098f82b8694861d77b0d2327
fatal: Fetched in submodule path 'buildroot', but it did not contain
bd668a433be69dd098f82b8694861d77b0d2327. Direct fetching of that commit failed.
fatal:
Error: Process completed with exit code 128.
```

`Cleanup` also reported a secondary failure (`ssh-add -D`: could not open a
connection to your authentication agent), which is a downstream side effect
of `ssh-agent` never having run — not an independent bug.

---

## 2. Root Cause

The `buildroot` submodule pointer recorded in the parent repo had drifted
from the known-good pinned commit to a new, uncommitted-upstream SHA:

- **Expected pin:** `e687e3815f76c1c5ea9fb52b6558bedfe53ab117` (tag `2024.02.13`)
- **Actual recorded pointer:** `bd668a433be69dd098f82b8694861d77b0d2327`
  (local commit message: `"reconfig buildroot changes"`)

The `bd668a433` commit was created **inside the submodule's own working
tree** (likely during a local `menuconfig` / config session), then that
change was committed and pushed from the *parent* repo without re-checking
out the submodule back to its intended tag commit first. This is the same
underlying class of issue documented previously for this pipeline
(GitLab's `uploadpack.allowReachableSHA1InWant` blocking direct SHA
fetches) — but this time the trigger was a genuinely different, non-tagged
commit rather than a config-only re-fetch problem.

GitLab's default server-side git config does not serve arbitrary
reachable-but-unadvertised SHAs via `upload-pack`. Since `bd668a433` was
never pushed as (or associated with) an advertised ref/tag on the
`buildroot.org` GitLab mirror, CI's shallow submodule fetch for that exact
SHA was rejected outright.

---

## 3. Diagnosis Steps

```bash
# Confirm what the submodule pointer currently resolves to, and diff
# against the intended pinned tag commit
cd ~/Documents/aeld-assignment-4
git submodule status buildroot
```

Output confirmed the drifted SHA and its origin:

```
 bd668a433be69dd098f82b8694861d77b0d2327 buildroot (2024.02.13-1-gbd668a433)
```

The `-1-g<sha>` suffix (git describe format) confirmed this was **one
commit ahead** of the `2024.02.13` tag — i.e. a local commit layered on
top of the correct pin, not a corrupted or unrelated ref.

---

## 4. Resolution

Re-point the submodule back to the exact tagged, upstream-fetchable
commit, then commit that pointer change in the parent repo.

```bash
# 1. Enter the submodule and fetch the known-good tag
cd ~/Documents/aeld-assignment-4/buildroot
git fetch origin tag 2024.02.13

# 2. Checkout the exact pinned commit for that tag
git checkout e687e3815f76c1c5ea9fb52b6558bedfe53ab117

# 3. Return to the parent repo and confirm the submodule pointer changed
cd ~/Documents/aeld-assignment-4
git status
git diff HEAD -- '*defconfig'   # sanity check: confirm no local config
                                 # changes are lost by abandoning bd668a433

# 4. Stage, commit, and push the corrected submodule pointer
git add buildroot
git commit -m "fix(buildroot): re-pin submodule to 2024.02.13 (e687e381...)"
git push origin master
```

If the assignment submission convention requires a tag, re-point and
force-push it after the fix:

```bash
git tag -f <assignment-submission-tag>
git push origin <assignment-submission-tag> --force
```

---

## 5. Verification

After pushing, re-run CI and confirm:

```bash
# Locally, before triggering CI
cd ~/Documents/aeld-assignment-4
git submodule status buildroot
# Expect: e687e3815f76c1c5ea9fb52b6558bedfe53ab117 buildroot (2024.02.13)
# (no "-N-g<sha>" suffix — exact tag match)
```

On GitHub Actions, confirm:
- `Checkout submodules` completes successfully (exit 0)
- `webfactory/ssh-agent` runs (no longer skipped)
- `Run full test` runs (no longer skipped)
- `Cleanup` no longer reports the `ssh-add -D` agent-connection error

---

## 6. Preventive Measures

- **Never commit inside the `buildroot/` submodule's own working tree**
  as a way of capturing configuration changes. Buildroot config changes
  belong exclusively in the tracked defconfig
  (`base_external/configs/*_defconfig` or equivalent), captured via
  `./save-config.sh`, never as a submodule-internal commit.
- **Always pin the submodule to a tag commit, never a branch or an
  ad-hoc local commit.** Branches and untagged commits are not guaranteed
  to be fetchable by CI under GitLab's default `upload-pack` restrictions;
  release tags are.
- **Before every push that touches the parent repo, check submodule
  drift explicitly:**
  ```bash
  git submodule status buildroot
  ```
  A `-N-g<sha>` suffix in the output is the signal that the submodule has
  moved past its intended pinned tag and needs to be re-checked-out before
  committing.
- Consider adding an automated guard at the top of `build.sh` (or as an
  early CI step) that fails fast with a clear message if the submodule SHA
  does not exactly match the expected pinned commit, rather than letting
  the failure surface indirectly via a cryptic `upload-pack: not our ref`
  error later in the pipeline.

---

## 7. Related Prior Issue

This is related to, but distinct from, an earlier resolved issue in the
same pipeline where `uploadpack.allowReachableSHA1InWant` blocked direct
SHA fetches generally. That issue was fixed by re-pinning the submodule to
the correct tag commit. This case confirms that **any** future drift off
that tagged commit — regardless of cause — will reproduce the same class
of failure, and reinforces that the submodule pointer must always resolve
exactly to a tagged, upstream-advertised commit before pushing.
