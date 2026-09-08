# AESD `aeld-assignment-4` — CI Deploy Key Setup Procedure

This document records the procedure for resolving the missing `SSH_PRIVATE_KEY`
GitHub Actions secret on `aeld-assignment-4`, including generating a dedicated
CI deploy keypair, registering it on the repo, provisioning the secret, and
verifying it before trusting CI.

**Repo:** `github.com/prashantgautamofficial/aeld-assignment-4`
**Context:** Self-hosted GitHub Actions runner executes the workflow inside a
persistent Docker container (`cuaesd/aesd-autotest:24-assignment4-buildroot`).
The workflow step `Run full test` uses `webfactory/ssh-agent@v0.5.3` with
`ssh-private-key: ${{ secrets.SSH_PRIVATE_KEY }}`, which was missing prior to
this procedure.

---

## Background: local re-clone first

Before addressing the CI secret, the local working copy was suspected to be in
a corrupted `.git` state. Diagnosis showed the repo itself was fine — a fresh
clone succeeded cleanly:

```bash
cd ~/Documents
git clone https://github.com/prashantgautamofficial/aeld-assignment-4.git
cd aeld-assignment-4
git submodule update --init --recursive
```

This surfaced two separate issues instead of a real corruption:

1. **Branch name mismatch** — local branch was `main`, but a push was
   attempted against `master`. Confirmed via:
   ```bash
   git branch
   ```
   Resolution: push to the correct branch name (`main`).

2. **Deploy key permission error** on push:
   ```
   ERROR: Permission to prashantgautamofficial/aeld-assignment-4.git denied to deploy key
   fatal: Could not read from remote repository.
   ```
   This indicated a deploy key was in play for this remote but either didn't
   exist yet or lacked the right access — distinct from the personal SSH key
   used for terminal pushes.

---

## 1. Personal SSH key for terminal pushes (one-time, per machine)

This is **separate** from the CI deploy key below — it authenticates
`prashant-virtual-machine`'s terminal to GitHub for normal `git push` use.

```bash
ssh-keygen -t ed25519 -C "your-github-email@example.com" -f ~/.ssh/id_ed25519_github
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519_github
cat ~/.ssh/id_ed25519_github.pub
```

Add the public key output at `https://github.com/settings/ssh/new`
(Title: `prashant-virtual-machine`, Key type: **Authentication Key**).

Ensure the remote uses SSH, not HTTPS:

```bash
git remote -v
git remote set-url origin git@github.com:prashantgautamofficial/aeld-assignment-4.git
```

Verify and push:

```bash
ssh -T git@github.com
git push origin main
```

---

## 2. Generate a dedicated CI deploy keypair

Purpose-scoped, read-only key for the self-hosted runner — never reuse a
personal key for CI.

```bash
cd ~/Documents/aeld-assignment-4
ssh-keygen -t ed25519 -f ./aeld-assignment-4-deploy-key -C "aeld-assignment-4-ci" -N ""
chmod 600 aeld-assignment-4-deploy-key
chmod 644 aeld-assignment-4-deploy-key.pub
```

Produces:
- `aeld-assignment-4-deploy-key` (private)
- `aeld-assignment-4-deploy-key.pub` (public)

---

## 3. Register the public key as a repo Deploy Key

```bash
cat aeld-assignment-4-deploy-key.pub
```

1. Go to `https://github.com/prashantgautamofficial/aeld-assignment-4/settings/keys`
2. Click **Add deploy key**
3. Title: `aeld-assignment-4-ci-runner`
4. Paste the public key contents
5. Leave **Allow write access** unchecked unless the workflow needs to push
   back to the repo (not required for a read/checkout + test pipeline)
6. Click **Add key**

---

## 4. Provision the `SSH_PRIVATE_KEY` GitHub Actions secret

```bash
cat aeld-assignment-4-deploy-key
```

Copy the **entire** output, including the
`-----BEGIN OPENSSH PRIVATE KEY-----` / `-----END OPENSSH PRIVATE KEY-----`
header/footer lines, with no extra whitespace.

1. Go to `https://github.com/prashantgautamofficial/aeld-assignment-4/settings/secrets/actions`
2. Click **New repository secret**
3. Name: `SSH_PRIVATE_KEY` — must exactly match the workflow YAML reference:
   ```yaml
   - uses: webfactory/ssh-agent@v0.5.3
     with:
       ssh-private-key: ${{ secrets.SSH_PRIVATE_KEY }}
   ```
4. Value: paste the full private key
5. Click **Add secret**

---

## 5. Verify the deploy key locally before trusting CI

```bash
GIT_SSH_COMMAND="ssh -i ./aeld-assignment-4-deploy-key -o IdentitiesOnly=yes" \
  git ls-remote git@github.com:prashantgautamofficial/aeld-assignment-4.git
```

A successful ref listing confirms both the key pairing and repo access work
before relying on it inside the automated pipeline.

---

## 6. Clean up the private key locally

Once confirmed and stored as a GitHub secret, remove the local copies so they
can't accidentally be committed:

```bash
rm aeld-assignment-4-deploy-key aeld-assignment-4-deploy-key.pub
```

---

## Incident: private deploy key accidentally committed, blocked by push protection

While completing the steps above, the private deploy key file was committed to
the repo (skipped ahead of the cleanup in §6) and a `git push` was attempted.
GitHub's **secret scanning push protection** caught it and rejected the push
before the key ever reached the remote:

```
remote: error: GH013: Repository rule violations found for refs/heads/master.
remote:
remote: - GITHUB PUSH PROTECTION
remote:   -----------------------------------------------------------
remote:     Resolve the following violations before pushing again
remote:
remote:     - Push cannot contain secrets
remote:
remote:     —— GitHub SSH Private Key ——————————————————
remote:      locations:
remote:        - commit: f2d6ba5642880ac88408f5975b941695f109f3c7
remote:          path: aeld-assignment-4-deploy-key:1
```

**This is a good outcome, not a bad one** — push protection did its job. The
key never left the local machine or reached GitHub's servers, so no rotation
would strictly be required to stop an *active* leak. Even so, once a private
key has touched any git commit (even one that never pushed successfully), the
safest practice is to treat that keypair as no longer trustworthy and
generate a fresh one — which is why §5 below ends in a full key rotation.

### 1. First attempt: amend the latest commit (incomplete fix)

```bash
git rm --cached aeld-assignment-4-deploy-key aeld-assignment-4-deploy-key.pub
rm -f aeld-assignment-4-deploy-key aeld-assignment-4-deploy-key.pub
git commit --amend --no-edit
```

**Explanation:** `git rm --cached` unstages the files from the *index* while
leaving nothing behind to re-add, and `commit --amend --no-edit` rewrites the
most recent commit to no longer include them. This is the correct fix **only
if the flagged commit is the current `HEAD`**. Here it wasn't — running
`git push origin master` again still failed, and the error still pointed at
the exact same commit hash (`f2d6ba5...`) as before. That was the signal the
amend hadn't touched the actual offending commit at all: the key had been
introduced two commits *earlier*, in a merge commit (`f2d6ba5`, "Merge
buildroot-assignments-base starter code"), and simply carried forward
unchanged into the newer commits. Amending `HEAD` can only rewrite `HEAD`
itself — it cannot reach back and scrub a file that was introduced further
down the branch's history.

### 2. Locate exactly which commit(s) introduced the key

```bash
git log --oneline -5
```

Output:
```
9fdc1f3 (HEAD -> master) Ignore deploy key files
f2d6ba5 Merge buildroot-assignments-base starter code
fe82512 (origin/master, ...) Go to f24 container version
cda31b4 Merge pull request #30 from cu-ecen-aeld/s23-updates
c4acde3 (buildroot-assignments-base/s23-updates) assignment-autotest: Go to latest
```

**Explanation:** This confirmed the key was introduced in `f2d6ba5`, which
sits **two commits behind** `HEAD` (`9fdc1f3`). Since `f2d6ba5` is an ancestor
of `HEAD`, its content is still fully reachable by git even though later
commits (like `9fdc1f3`, which added `.gitignore` entries) don't reference the
key files anymore — git history is additive; deleting a file in a later
commit doesn't erase it from earlier commits still in the branch's chain.
This is exactly why GitHub's scanner kept flagging the same commit hash: that
commit, unchanged, was still part of what `git push` was trying to send.

### 3. Rewrite history with an interactive rebase

```bash
git rebase -i f2d6ba5^
```

**Explanation:** `f2d6ba5^` refers to the parent of the offending commit —
i.e., "start the rebase just before the bad commit exists." This opens an
editor listing every commit from `f2d6ba5` through `HEAD`:
```
pick f2d6ba5 Merge buildroot-assignments-base starter code
pick 9fdc1f3 Ignore deploy key files
```

The first line was changed from `pick` to `edit`:
```
edit f2d6ba5 Merge buildroot-assignments-base starter code
pick 9fdc1f3 Ignore deploy key files
```

Marking a commit `edit` tells git to stop and hand control back once it
replays that specific commit, so its contents can be modified before
continuing — unlike `pick`, which just replays the commit as-is.

### 4. Remove the key files from the flagged commit itself

```bash
git rm --cached aeld-assignment-4-deploy-key aeld-assignment-4-deploy-key.pub
git commit --amend --no-edit
git rebase --continue
```

**Explanation:** After saving the rebase plan, git paused with `f2d6ba5`
checked out as the working commit. Running `git rm --cached` here removes the
key files from *that specific commit's* snapshot, and `commit --amend
--no-edit` rewrites `f2d6ba5` itself (producing a new commit hash) without
them, keeping the original commit message. `git rebase --continue` then
replays the remaining commit (`9fdc1f3`, the `.gitignore` addition) on top of
the newly rewritten commit. The practical effect: the entire branch is
rebuilt from that point forward with new commit hashes, and the private key
no longer exists in any commit's snapshot, anywhere in the branch.

### 5. Verify the key is completely gone from history

```bash
git log --all --oneline -- aeld-assignment-4-deploy-key
git log -p --all | grep -i "BEGIN OPENSSH PRIVATE KEY"
```

**Explanation:** The first command searches every commit reachable from any
ref (`--all`) for ones that touched that specific file path — an empty result
confirms no commit in local history references the file anymore. The second
command is a stronger, path-independent check: it searches the full patch
content of every commit for the literal private-key header text, in case the
key was ever added under a different filename. Both returning nothing is the
confirmation needed before trusting a push.

### 6. Push the rewritten history

```bash
git push origin master
```

**Explanation:** Since the remote (`origin/master`) never successfully
accepted the commit containing the secret (the push was rejected by push
protection, not merely warned-and-allowed), this is not a case of rewriting
history other collaborators have already pulled — a plain push works without
needing `--force`. If the remote had already accepted the bad commit in an
earlier, different push, `git push origin master --force-with-lease` would be
required instead, since the rewritten commit hashes wouldn't fast-forward
from what the remote has. `--force-with-lease` is preferred over a bare
`--force` because it aborts if the remote has moved in a way the local repo
doesn't know about — protecting against silently overwriting someone else's
work.

### 7. Rotate the deploy key

Because the private key touched a git commit at any point, treat it as
compromised regardless of whether the push protection blocked it from
reaching GitHub. Repeat §2–§5 above (generate a **new** keypair, register the
new public key as the repo's deploy key, add the new private key as the
`SSH_PRIVATE_KEY` secret, verify with `git ls-remote`) and then remove the old
deploy key from **Settings → Deploy keys** on the repo so it can no longer be
used even if a copy exists somewhere outside git.

---

## 7. Pass `SKIP_BUILD` and `DO_VALIDATE` through the workflow

`full-test.sh` does not itself define `SKIP_BUILD` / `DO_VALIDATE` — it only
echoes them and invokes `assignment-test.sh`, which reads them directly as
environment variables. Since exported env vars propagate to child processes,
add them to the workflow step's `env:` block alongside the existing entries:

```yaml
      - name: Run full test
        env:
          GIT_SSH_COMMAND: "ssh -o StrictHostKeyChecking=no"
          FORCE_UNSAFE_CONFIGURE: 1
          SKIP_BUILD: 1
          DO_VALIDATE: 1
        run: ./full-test.sh
```

GitHub Actions `env:` values are always treated as strings, so `1` becomes
`"1"` — this matches what `assignment-test.sh` expects
(`${SKIP_BUILD} -eq 1`).

---

## 8. Trigger and verify a CI run

```bash
git commit --allow-empty -m "trigger CI: verify SSH_PRIVATE_KEY secret"
git push origin main
```

Then check the repo's **Actions** tab and confirm:
- The **Checkout submodules** step succeeds (no permission errors)
- The **Run full test** step succeeds using the `SSH_PRIVATE_KEY` secret via
  `webfactory/ssh-agent`
- `SKIP_BUILD` / `DO_VALIDATE` are honored if a validate-only run was intended

---

## Troubleshooting reference

| Symptom | Cause | Fix |
|---|---|---|
| `Permission ... denied to deploy key` on push | Deploy key not registered, or personal push attempted with wrong remote/key | Confirm remote uses SSH; use personal key (§1) for terminal pushes, not the CI deploy key |
| `Your branch is based on 'origin/main', but the upstream is gone` | Local branch renamed (`main`↔`master`) without matching remote tracking | `git branch -vv` to check tracking; push to the actual current branch name |
| CI step fails at checkout/submodule update with SSH error | `SSH_PRIVATE_KEY` secret missing or doesn't match deploy key on repo | Re-run §2–§5; confirm secret name matches workflow YAML exactly |
| `git ls-remote` fails locally with the deploy key | Public key not yet added under **Settings → Deploy keys**, or added to wrong repo | Re-check §3; confirm key appears under the correct repo's Deploy keys page |
| Deploy key works locally but fails in CI | Secret value has extra whitespace or missing header/footer lines | Re-copy full `cat` output exactly; re-paste into the secret with no trailing newline issues |
| `GH013: Repository rule violations found` / `Push cannot contain secrets` | A private key (or other secret) was committed and push protection caught it before reaching GitHub | Do **not** use the "allow this secret" URL; instead remove the key from the offending commit — `git commit --amend` if it's `HEAD`, or an interactive rebase (`git rebase -i <bad-commit>^`) if it's further back — then verify with `git log -p --all \| grep -i "BEGIN OPENSSH PRIVATE KEY"` before pushing again |
| Same commit hash keeps getting flagged after `git commit --amend` | The secret was introduced in an *older* commit than `HEAD`; amending `HEAD` only rewrites the latest commit, not its ancestors | Run `git log --oneline -5` to find the actual commit that introduced the file, then rebase from that commit's parent (`git rebase -i <commit>^`) and mark it `edit` to remove the file from that specific snapshot |
| Deploy key was ever staged/committed to git, even briefly | Any key that touched a commit should be treated as no longer trustworthy, even if the push itself was blocked | Generate a fresh keypair, register the new public key, update the `SSH_PRIVATE_KEY` secret, then remove the old public key from the repo's Deploy keys page |
