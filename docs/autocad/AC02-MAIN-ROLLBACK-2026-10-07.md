# AC02 MAIN integration and recovery
Local integration was approved on 2026-10-07. GitHub publishing and official release remain separate.

## Exact recovery point
Previous MAIN: `30d6f23996035784154f3c306641488bcd2879bf`.
Backup branch: `codex/backup-main-before-ac02-20261007`.
Recovery tag: `rollback-main-before-ac02-20261007`.
Integration tag: `ac02-main-integration-20261007` (created after local merge).
Reviewed product source: `ca11b14c6123fa952f999c0d4bf2b0f444f4c70b`.

The rollback kit preserves the previous MAIN source and tracked materials, its exact tracked `releases/windows/dwg-to-pdf-validation.zip`, a Git bundle carrying baseline and candidate history, and SHA256 checksums. The old tracked ZIP is the baseline's existing validation runtime; it is not asserted to contain the new AutoCAD improvements. Never overwrite an existing installation with the candidate before acceptance.

## Other PC: retain two environments
Copy the complete recovery kit to the other PC BEFORE trying the candidate. Keep the known previous installation, its full runtime folder and local CAD configuration unchanged. Use a separate candidate folder and fresh output directory. Save candidate SHA, configuration, input hashes, failure logs and outputs locally; never upload customer drawings or private logs without approval.

If the candidate fails, stop new conversions. Do not kill CAD by name or save/close user drawings. Preserve failure evidence and use the previous runtime folder again. Output PDFs already generated are retained. The bottom-right text overlap is accepted/ignored by the user; it is not a rollback trigger. Other conversion errors, changed inputs, user-CAD interference or unacceptable output are rollback triggers.

## Prepare previous source without overwriting
Git and PowerShell are needed for source preparation. No PowerShell script execution-policy change is required: paste these commands into the PowerShell console from the offline kit root. Do not run terminal commands through Computer Use.
```powershell
$ErrorActionPreference = 'Stop'
$kit = (Get-Location).Path
$manifest = Get-Content -LiteralPath (Join-Path $kit 'recovery-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$bundle = Join-Path $kit 'previous-and-candidate.bundle'
if ($manifest.BaselineSHA -ne '30d6f23996035784154f3c306641488bcd2879bf') { throw 'Unexpected baseline' }
if ((Get-FileHash -LiteralPath $bundle -Algorithm SHA256).Hash -ne $manifest.BundleSHA256) { throw 'Bundle checksum mismatch' }
$destination = 'D:\DWG test\previous MAIN' # Choose a NEW directory on this PC.
if (Test-Path -LiteralPath $destination) { throw 'Destination exists; nothing overwritten' }
git clone --branch rollback-main-before-ac02-20261007 -- $bundle $destination
if ($LASTEXITCODE -ne 0) { throw 'Clone failed; preserve partial directory and error' }
$actual = git -C $destination rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $actual.Trim() -ne $manifest.BaselineSHA) { throw 'Recovered HEAD mismatch' }
```
The recovery clone has a detached HEAD at the baseline tag; this is intentional. It does not change current MAIN, CAD, installed runtime, configuration or existing Git history.

If Git is unavailable, verify the source ZIP hash against recovery-manifest.json and extract previous-main-source.zip into a NEW folder. For runtime recovery, verify/extract previous-main-runtime.zip into another NEW folder, keep the entire dwg-to-pdf-validation tree, and run its dwg-to-pdf.exe --self-check before using it. Do not overwrite existing output directories. A self-check does not prove CAD conversion compatibility on that PC.

## Undo the integrated source in shared MAIN
Prefer a revert commit, not reset/force-push. First preserve local edits and ensure the repository is clean; keep the offline kit and failure evidence. After confirming the integration tag points to the expected merge, run:
```powershell
git switch main
if ($LASTEXITCODE -ne 0) { throw 'Cannot switch to main' }
git status --short
# Continue only with a clean tree. Review later dependent changes first.
git revert -m 1 ac02-main-integration-20261007
if ($LASTEXITCODE -ne 0) { throw 'Revert conflict: stop and inspect; do not reset or clean' }
```
With no later dependent changes, this restores the tracked pre-merge MAIN tree while retaining the merge and rollback history. Run the previous baseline's tests and CAD validation before distributing a rollback. Pushing the revert to shared GitHub requires authorization. Local tags/bundles are portable recovery artifacts; this local integration does not make them available remotely.

## Validation and limits
Current-PC offline: 947 pass /4 symlink skips /9 CAD deselected. AutoCAD2021 source OFF43/ON43 and ordinary frozen43 succeeded; ordinary GUI7 and diagnostic GUI4x7 succeeded. Additional CLI7 passed. Original/user-CAD protection passed.
Historical GUI first-file E203 failures remain unconfirmed; later success does not establish a fix. Native LISP success and other-PC acceptance remain unverified. Codex elevated Computer Use setup-refresh failure is separate from this product.
