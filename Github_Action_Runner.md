# GITHUB ACTION RUNNER SETUP AND TROUBLESHOOTING

1. Initial setup (first time)
Go to the repo on GitHub → Settings → Actions → Runners → New self-hosted runner.
2. Follow the download/extract commands shown there for your OS/architecture (these create ~/Documents/actions-runner with
config.sh , run.sh , etc.).
3. Copy the registration token shown on that page — it is short-lived (~1 hour) and single-use. Grab it right before running config.sh ,
not in advance.
4. Register the runner:

```bash
cd ~/Documents/actions-runner
./config.sh --url https://github.com/<org-or-user>/<repo> --token <TOKEN>
```

5. Accept the interactive prompts (press Enter for defaults): - Runner group → Default - Runner name → hostname or custom name -
Runner labels → default ( self-hosted,Linux,X64 ) - Work folder → _work

6. Confirm it prints:

```bash
√ Connected to GitHub
√ Runner successfully added
√ Runner connection is good
```

7. Start the runner:

```bash
./run.sh
```

Should print √ Connected to GitHub and Listening for Jobs .

8. Verify on GitHub, not just locally: go to Settings → Actions → Runners on the repo — the runner should show as green / Idle. A
runner that "looks" like it's running in the terminal is not proof it's actually registered against that repo.


# Fix — re-register from a clean state

```bash
rm -f .runner .credentials .credentials_rsaparams .runner_migrated .env .path
```

Then get a brand new registration token from the correct repo's page:

[GitHub runner registration page](https://github.com/your-org/your-repo/settings/actions/runners/new)

And register immediately (tokens expire quickly — don't let it sit):

```bash
./config.sh --url https://github.com/<org-or-user>/<repo> --token <FRESH_TOKEN>
```

Step through the prompts, then:

```bash
./run.sh
```

Verify again on Settings → Actions → Runners — it should now show green/Idle.