# Circuit-Synth + KiCad E2E runner

The regular CI verifies PCB Forge's Python tests and MCP import. The real
Circuit-Synth E2E has two execution paths:

- **Hosted Linux (recommended first):** workflow
  [Circuit-Synth + KiCad E2E (hosted Linux)](../.github/workflows/circuit-synth-e2e-hosted.yml)
  installs KiCad CLI on a disposable GitHub-hosted Ubuntu 24.04 runner, installs
  Circuit-Synth, generates the reference project, runs ERC/DRC, and uploads
  artifacts. It runs on relevant pushes to `main` and can also be dispatched
  manually. No self-hosted runner registration is needed.
- **Self-hosted Linux (optional):** workflow
  [Circuit-Synth + KiCad E2E](../.github/workflows/circuit-synth-e2e.yml)
  targets a trusted runner labeled `self-hosted`, `linux`, and
  `pcb-forge-e2e`. Use this path if you need a pinned/local KiCad environment.

## 1. Hosted Linux run

Open the repository's **Actions** tab and select **Circuit-Synth + KiCad E2E
(hosted Linux)**. Click **Run workflow** to start it manually. The workflow
installs KiCad using Ubuntu's package manager and installs PCB Forge with its
development and Circuit-Synth extras. The job has a 45-minute timeout.

When it finishes, download the artifact named
`pcb-forge-circuit-synth-e2e-hosted` from the run's **Artifacts** section.
GitHub retains it for 14 days. Inspect `e2e-summary.json`, the generated
`.kicad_sch` and `.kicad_pcb` files, and each ERC/DRC report. A failed run
should be debugged from the first failing workflow step; do not suppress the
failure just to turn CI green.

## 2. Prepare a dedicated self-hosted runner (optional)

Use a dedicated Linux VM or disposable machine that you control. Do not register
a self-hosted runner on a workstation containing personal files, credentials,
SSH keys, production access, or other sensitive data. Treat generated designs
and dependencies as untrusted until reviewed.

Requirements:

- Linux supported by the installed KiCad package.
- Python 3.12 and pip.
- `kicad-cli` available on PATH; verify with `kicad-cli version`.
- Outbound network access to GitHub and Python package indexes during setup/job.
- Enough disk space for Python packages and generated KiCad files.

Install KiCad using the official instructions for your Linux distribution:
https://www.kicad.org/download/linux/

## 3. Register the self-hosted runner

In GitHub, open **melo1015/pcb-forge → Settings → Actions → Runners → New self-hosted runner**.

1. Choose Linux and the architecture matching the machine.
2. Follow the commands GitHub displays to download, configure, and test the
   runner. Use the current one-time registration token shown by GitHub; never
   copy it into this repository or commit it.
3. During configuration, add the custom label `pcb-forge-e2e`. Keep the standard
   `self-hosted` and `linux` labels.
4. Start the runner and confirm GitHub shows it as **Idle** and online.

The self-hosted workflow requires all three labels:
`self-hosted`, `linux`, and `pcb-forge-e2e`. A runner without these labels
will leave that job queued.

## 4. Run the self-hosted E2E workflow

1. Open the repository's **Actions** tab.
2. Select **Circuit-Synth + KiCad E2E** (without the hosted Linux suffix).
3. Click **Run workflow**, select `main`, and dispatch it.
4. Watch the job logs. It verifies Python and KiCad, installs PCB Forge with its
   development and Circuit-Synth extras, checks the Circuit-Synth import, then
   generates the reference 5 V regulator project and invokes KiCad ERC/DRC.

This workflow is manual-only and targets the dedicated runner labels above.

## 5. Expected outputs and review

Expected contents under `artifacts/e2e/` include:

- `regulator_5v/`: generated KiCad project files and the copied source.
- `*.erc.rpt`: electrical-rule-check reports for generated schematics.
- `*.drc.rpt`: design-rule-check reports for generated boards.
- `e2e-summary.json`: generation result, command return codes, report paths,
  and captured command output.

Review the reports rather than relying only on the job's exit code. A successful
KiCad CLI invocation does not itself prove that the design has zero violations,
is electrically correct, or is ready to manufacture. The example is a starting
point for integration testing, not a production-ready power supply.

## 6. Run locally

From the repository root, in an environment with the project dependencies,
Circuit-Synth, and KiCad CLI installed:

~~~bash
python -m pip install -e ".[dev,circuit-synth]"
kicad-cli version
python scripts/run_circuit_synth_e2e.py examples/circuit_synth/regulator_5v.py --output-dir artifacts/e2e
~~~

The script recreates only `artifacts/e2e/regulator_5v/` on each run. Keep any
other files in the output directory backed up if they matter.

## Security and troubleshooting

- The hosted workflow uses a fresh GitHub-hosted runner and avoids exposing a
  personal workstation to repository code.
- Do not use a persistent self-hosted runner for untrusted pull-request code.
  Keep that workflow manual and run it only against reviewed code on a trusted
  branch. Prefer an ephemeral VM and destroy/rebuild it after the run.
- If the self-hosted job remains queued, verify that the runner is online and
  has all three required labels.
- If `kicad-cli version` fails, fix the system installation/PATH before rerunning.
- If package installation fails, inspect the pip output and verify Python 3.12
  and network access.
- If generation fails or no `.kicad_sch`/`.kicad_pcb` files appear, inspect
  the generation result in the logs and the downloaded artifact, if present.
- If ERC/DRC returns nonzero or a report is missing, inspect
  `e2e-summary.json` and the individual reports. Fix the underlying design or
  environment issue; do not suppress the failure merely to turn CI green.
