# Creating and testing a Terra Invicta mod

## Identify the task first

This is a **Windows-only, one-mod-per-clone** workspace. If the user is maintaining the template itself, work on its tooling/docs/tests without initializing a gameplay mod. If the user asks for a mod and `mod.project.json` is absent, initialize the appropriate starter. Derive a descriptive name and unique dotted ID; ask about meaningful gameplay ambiguity, not facts discoverable from the installation.

Read [the command/workflow guide](docs/workflow.md) and the task's entries in [capabilities](docs/capabilities.md). For runtime work also read [testing](docs/testing.md) and the pinned MCP [playbook](tools/TerraInvictaMCP/docs/playbook.md). If submodules are absent, run `ti.ps1 setup` first or initialize the required gitlinks to read them.

The user can ask for any feasible TI mod: data/content, rules and victory logic, UI, campaign state, scenarios, art, maps, audio, ships, or combinations. Use the narrowest mechanism that satisfies the requested behavior. Do not silently turn an example into a requirement, or claim a workflow supports every future game API without inspection.

## First actions in a new mod clone

1. Read the request and record observable success criteria in a short feature note. Specify relevant factions, scenarios, DLC, existing/new saves, UI behavior, costs and failure cases.
2. Run `powershell -NoProfile -File .\ti.ps1 setup` unless local setup is already current. A Python interpreter and the compatible UMM installation are external prerequisites; [setup](docs/setup.md) gives exact diagnostics. Routine setup is automated.
3. Run `ti.ps1 doctor`; record the actual installation/assembly fingerprint. A Steam branch label and an old handbook version are not evidence of the installed API.
4. Run `ti.ps1 init -Id Author.ModName -Kind Native|Code|Hybrid` if needed. Use `-Name` and `-Author` where known; add `-Assets` for bundle authoring. Keep identifiers stable once they appear in saved data or releases.
5. Inspect the installed templates and relevant C#/IL, then implement and test. Continue through feature verification and packaging; a successful compile is not completion.

## Sources of truth and research

- For what the game does: installed assemblies/templates plus observations from the same running build.
- For the scaffold commands and package rules: this repository and its tests.
- For tested MCP capabilities: its pinned tool schema, playbook, protocol, and actual tool results.
- For modding knowledge: the local [handbook](references/ti-mods/README.md), maintained in [our origin fork](https://github.com/Laurentiu-Andronache/ti-mods), not the upstream repository.
- Keep version-sensitive citations tied to the recorded gitlinks in `tools/dependencies.lock.json`. The initial handbook [snapshot](https://github.com/Laurentiu-Andronache/ti-mods/tree/e0c91fb3cea08878a39e99ec201231688a043803) and [MCP snapshot](https://github.com/Laurentiu-Andronache/TerraInvictaMCP/tree/3f338b67b010fca17edc0f4f27cd33d1f35851f7) are reference evidence, not universal game contracts.

Use `rg` for focused searches. Start decompilation with a type index (`ti.ps1 inspect`), then a declaring type (`-Type Namespace.Type`) and IL (`-IL`) when needed. Follow callers, overloads, side effects, caches, initialization and teardown. Output belongs in `.local/inspection`; do not commit reconstructed game source or patch installed assemblies to implement a mod.

Do not trust a familiar private field name, a decompiler's reconstruction of unusual flow, or a string-based Harmony target just because compilation succeeds. Inspect the exact installed method and verify it at runtime.

## Pick the extension mechanism

| Need | Start here |
|---|---|
| Values, records, techs, orgs, narrative events, scenarios | Native sparse JSON and content registration |
| Logic, costs, behavior, victory evaluation | UMM/Harmony C# after inspecting existing operations |
| New controls or changed game-screen layout | Runtime hierarchy inspection, existing UI lifecycle, reusable controls |
| User preferences | UMM `ModSettings`, separate from campaign saves |
| Persistent campaign data | Registered game-state types and explicit save migration/removal tests |
| Temporary state and lookup caches | Rebuild for the current screen/campaign; do not retain old Unity objects |
| Models, sprites, portraits, maps, audio | Task-specific authoring pipeline in the capability map |

Prefer game operations over direct assignment when changing state. A resource debit, recruit creation, orbit change, research grant or victory event may involve validation, bookkeeping, notifications, caches and UI refresh. Trace the whole operation before replacing it.

## Native loading and packaging rules

- Keep authored native JSON at the root of `content/`. The loader reads merge settings from a template file's immediate directory.
- `mod.project.json` is project configuration and must never be deployed. `ModInfo.json` is generated; do not maintain another copy in content.
- Native records normally use exact `dataName` identity. Default array merging is positional; explicitly choose concatenation, replacement or a full intentional list. These switches apply at file level, including nested arrays.
- New records may require registration in `TIMetaTemplate` or other consuming lists. Test references, localization, reachability, and intended DLC scenarios.
- Template defaults differ from serialized campaign state. Test a new campaign and, where promised, existing saves separately.
- The inspected native scanner processes every `.json` except `ModInfo.json`. Settings/caches/debug output cannot be arbitrary JSON files in the deployed mod tree.
- This scaffold requires UMM's Terra Invicta profile to use `Mods/Enabled` and `ModInfo.json`. The handbook's historical `ModFile.json` examples do not override the current installation check. Do not globally rewrite UMM configuration to work around a failed package.
- `Title` matches the installed folder/ID. Code metadata shares `ModInfo.json` with the native fields. Plain native mods do not receive fake DLLs or a UMM runtime dependency.
- Keep game, Unity, UMM, Harmony, framework-reference and test DLLs out of release ZIPs. Add required installed game assemblies to the descriptor's `requiredAssemblies`; references stay `Private=false`.
- Add authored bundle/manifest pairs and other assets to `packageFiles`. Source files and executables do not belong in `content/`.

## Code and UI conventions

- Use the mod ID as the Harmony owner. Remove only that owner's patches on disable/unload; never use parameterless global unpatching.
- Keep patches narrow. Preserve the original operation outside the cases you explicitly handle. Avoid copying entire decompiled game methods to change a value.
- Guard patch and UI callbacks so a diagnostic or unexpected destroyed object cannot crash the game. Report relevant failures with the loader logger; do not spam each frame.
- Make enable, registration, screen setup and cleanup repeatable. Handle already-initialized terminals and screens. Remove only listeners/objects/registrations owned by this mod.
- Inspect actual UI roots/components. Reuse compatible game controls, then review copied listeners, controller collections, anchors, scaling, text, scroll bounds and input behavior.
- Display every newly added in-game cost as `[resource icon] [amount]`, using the appropriate native resource icon and the game's formatting helpers (for example, `TIUtilities.InlineResourceStr(FactionResource.Money)` followed by a space and the amount). Apply this to controls, tooltips, and dialogs; verify the icon renders correctly with the UI's font/sprite assets. Keep the displayed amount consistent with affordability checks and the actual charge.
- Reacquire state and UI after campaign or screen changes. Unpatching does not undo data already written to templates, caches or saves; document restart requirements.
- Keep tests in `DevelopmentTests.cs` behind `TI_MOD_TESTS`. Development methods return structured JSON; see the starter and [testing interface](docs/testing.md). Production behavior must not depend on the development helper.

## The test loop

1. Build and run relevant offline checks. Fix actual failures before deployment.
2. Use a disposable runtime recipe; it snapshots saves/profile/UMM settings and records the process it launches. Never experiment on a person's campaign or stop an unrelated running game.
3. Call MCP `observe` first. Read its current campaign token and blockers. Use fixtures to reach relevant states quickly instead of playing for hours.
4. Assert the requested behavior. Fixture spawns and generic MCP actions can bypass costs/prerequisites; they do not prove player affordability or availability. Test the actual player-facing operation too.
5. For UI, use `ti_dev` hierarchy/inspection and actual event-handler invocation, plus screenshots. The helper's event dispatch is not an OS pointer click; report desktop interaction separately when available.
6. Retest failed steps after fixes. Include insufficient resources, repeated action, repeated screen opening, selected faction/object changes, disabled state, save/reload and second-campaign behavior as relevant.
7. Collect the first related exception and preceding messages. Keep all evidence in `.local/runs`. Compare baseline warnings with new failures; do not dismiss exceptions just because the game reached its menu.
8. Finish with a clean Release build/package and feature-specific evidence. Describe remaining blocked tests precisely; do not label skipped or unrun checks as passes.

MCP's stdio process retains its Python code until reconnected. A game restart refreshes the bridge DLL, not an existing Python server. Reconnect after changes to deployed server files; compare `selftest`/build fingerprints. Long setup can hit its pause watchdog; adjust a test's pause budget explicitly and record why.

## Files, recovery, and maintenance

Use `ti.ps1 deploy`, `test`, and `restore` for owned changes. Their journals live outside the game and survive interruption. Close the game before replacing DLLs. Preserve externally modified files and unrelated mod settings. Recover an unfinished session before beginning another one.

Keep local paths, saves, logs, extracted assets and game DLLs ignored. Package only authored content and reviewed distributable dependencies. Inspect the final ZIP for stale files and test hooks. Publishing to Workshop or a remote repository is a separate user-directed action; preparing a ZIP is part of the normal mod workflow.

Treat submodules as pinned dependencies. Their contribution rules govern edits inside them, not new mod code here. Do not edit or upgrade them incidentally. Updating a dependency means updating its gitlink and lock entry together, reviewing compatibility, and repeating affected tests. For template maintenance, run `ti.ps1 test -Offline` and the changed integration paths; add meaningful regression tests for tooling failures.
