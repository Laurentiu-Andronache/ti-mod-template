# Maintenance acceptance note

Implement reliable recovery, independent compilation/test-helper options, reusable
journaled interactive sessions, accurate diagnostics and IL scope, and practical
UI guidance for the recorded game build. This workspace remains an uninitialized
template. Preserve the AGENTS.md resource-icon rule and all dependency pins.

Acceptance includes injected cleanup failures, configuration and command-replay
regressions, a multi-type IL fixture, and offline repository validation. In a
disposable initialized clone, verify Debug, Release with external DevTools and no
mod test hooks, archived vanilla-state save loading with the project mod absent,
and interrupted-session recovery. Compare packaged/tested DLL hashes and original
saves, settings, PlayerPrefs and installed files after recovery. Keep raw evidence
ignored; report actual scenario and UI interaction coverage and any blocked checks.

## Reproduce maintenance checks

Run `ti.ps1 test -Offline` in the template. With installed tooling configured,
`py -3 tests/inspection_acceptance.py` compiles a tiny authored fixture and checks
actual IL scope. Run `py -3 tests/live_acceptance.py` only in a disposable clone
initialized with a `TemplateMaintenance.*` code starter. It checks Debug/UI,
Release plus helper, an archived save with an installed project temporarily
removed, and interrupted-worker recovery. Run `ti.ps1 restore` afterward to
reverse setup and deliberately seeded project deployments. Keep the clone and
its evidence until recovery and the original-file hash audit are complete.

## Verification on 2026-09-07

The final offline suite passed **43 tests** and repository validation. Coverage
includes simultaneous cleanup failures, real file restoration after log failure,
external-edit refusal, the build-option matrix, package guards, durable command
deduplication/uncertain outcomes, fixture collisions, installation locking,
duplicate-worker refusal, and PowerShell quoted/Unicode JSON forwarding.

The installed fingerprint remained
`ff7916c2085ddbafa5acf1e8ea185d37e629096752be388ba6fa1f627f027bb5`.
The two-type compiled fixture proved that the pinned type-plus-IL invocation and
the corrected assembly-IL invocation produce identical output containing both
types. The full game inspection used the assembly-wide filename and recorded the
requested type separately. The UI documentation's C# expressions compiled against
this installed build.

Live validation used an independently initialized `TemplateMaintenance.Smoke`
code starter in an ignored disposable clone. The template remained uninitialized.

| Check | Actual result |
|---|---|
| Debug | Starter Harmony probe and helper enabled/disabled/stale-handle UI checks passed |
| Release plus external helper | Archived save loaded, mod test type absent, actual helper button dispatch passed, duplicate command ID did not repeat the click |
| Mod-absent loading | An installed project was temporarily removed; DLL, metadata and runtime listing were absent; saved scenario, faction ID, resources and date matched |
| Interrupted worker | Worker terminated deliberately; `restore -Session` stopped its owned game and recovered saves/settings/deployments |
| Interactive CLI | Documented PowerShell start/command/finish example passed; a subsequent session verified JSON stdin and duplicate-worker rejection without evidence changes |
| Release package | Four allowed files; no helper, test sources or proprietary DLLs; class inspection confirmed no `DevelopmentTests` |
| Recovery | All seven session journals and 17 deployment journals restored; 43 original save/profile/UMM files matched after each run; final audit matched 113 persistent original files and byte-identical PlayerPrefs |

The tested and packaged DLL SHA-256 was
`aad165aabdf7c783f9c0cbe08de2535b8db2266469524abbe019293bcb39d531`;
ZIP SHA-256 was
`62d34eeef1fb35fb6ce76bfe1b878d487e6a2485027b00ffff8fd31dbb4bab61`.
Raw records are in `.local/maintenance-validation` and the disposable clone's
`.local/runs`; these artifacts are intentionally ignored.

The first mod-absence attempt correctly failed because TI lists an empty enabled
folder. Removal now deletes empty folders and restores their original structure;
the regression and repeated live load passed. That failed session was restored
and is retained as failed evidence. The PowerShell launcher checks also caught
and fixed stripped JSON quotes, pipeline character conversion, and a null argument
for commands with no trailing options.

Scope and limits: campaign checks covered ModernScenario/Resistance on TI
1.0.53a. Screenshots were inspected; interaction evidence is Unity event dispatch,
not desktop pointer input. Captured normal-session Player logs contained no
exceptions. The tests exercise generic template/helper behavior, not a councilor
gameplay feature or other scenarios. Rotating logs and generated loader/Python
caches are outside the byte-identical persistent-file audit: one existing UMM
MCP cache was regenerated. Authored installed files, saves and settings matched;
only the original two enabled mod folders remained, and no game process was left
running. Dependency gitlinks and lock entries were unchanged; nothing was pushed
or published.
