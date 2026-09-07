# Compatibility and validation record

This is a record of evidence, not a promise that a game version's private APIs will remain stable.

| Component | Initial profile |
|---|---|
| Operating system | Windows x64 only; PowerShell 5.1 entry point |
| Game reference | TI 1.0.53a with Dark Skies, confirmed by the live bridge |
| Unity authoring/player | 2020.3.49f1 |
| UMM | Installed 0.33; metadata filename `ModInfo.json` |
| Harmony | Installed UMM pair, handbook baseline 2.3.6 |
| Build | SDK 8.0.424, `net48` mod target; MCP/helper compiled against game BCL |
| Python | 3.11+; initial local checks use 3.14.7 |
| ILSpyCmd | 9.1.0.7988 |

## Evidence

Validated on 2026-09-07. An ordinary Git clone into a folder containing spaces initialized both required submodules from the fork URLs, downloaded its own SDK, restored ILSpyCmd, compiled and deployed MCP, and generated its local client configuration. It did not inherit the source workspace's `.local` directory or an installed SDK.

| Check | Result |
|---|---|
| Scaffold offline suite | 18 tests passed, including interrupted/partial file writes, recovery registration, external edits, settings preservation, package allowlists and the game's LF profile format |
| Pinned MCP offline suite | 552 tests passed |
| Live MCP selftest | Server code current; metadata/server/DLL versions agree; no tool/verb drift; native mod support enabled |
| Repository validation | Local documentation links, authored JSON, required pins and tracked-file checks passed |
| Local builds | MCP, development helper and Debug/Release starter compiled; starter had no warnings or errors |
| Native runtime | Sparse `AdAstra.researchCost` change from 5000 to 2500 compared in the engine; merge, references and localization all PASS with zero warnings |
| Code runtime | Disposable ModernScenario/Resistance campaign; helper initialized; conditional Harmony probe observed both patched and original behavior; final bridge health passed |
| UI helper runtime | Actual Unity button handler dispatch; enabled click counted once, disabled click refused, teardown/reopen reset state, stale handle refused |
| Release inspection | ZIP contained only the mod, metadata, authored native patch and license notices; ILSpy class index confirmed `DevelopmentTests` absent |
| Recovery audit | All 10 sessions and 18 deployment journals restored; 42 original save/profile files, UMM settings and 53 recorded MCP paths verified; PlayerPrefs registry export matched byte for byte |
| Optional tooling | RuntimeUnityEditor release checksum verified and metadata staged; ship framework adapter compiled against the installed game |

The main-menu screenshot was inspected successfully. Campaign smoke screenshots captured the black intro frame, with the helper's fixture visible during UI checks: these prove neither a finished campaign screen nor a particular gameplay UI's appearance. No OS pointer test was performed.

The implementation tests caught and corrected two game-specific requirements: MCP console calls need a loaded campaign, and `PlayerOptions.TIProfile` must retain LF line endings because this build compares boolean values without trimming carriage returns. Earlier failed runs remain in local evidence; they are not counted as passes.

Assembly-CSharp SHA-256: `ff7916c2085ddbafa5acf1e8ea185d37e629096752be388ba6fa1f627f027bb5`. Full fingerprints, package hashes, logs, screenshots and recovery records remain in ignored `.local` evidence. The integration fixture was initialized in the disposable clone; the template itself remains uninitialized.

The pinned handbook had passed its own validator and four offline tests during planning. The pinned MCP passed its stdio self-check and 552 offline tests. Those results support choosing the dependency revisions; they do not substitute for this scaffold's own integration tests.

## Limits

- Public CI runs game-independent validation only. It does not contain or obtain proprietary game assemblies.
- The UI helper's pointer-event dispatch includes an interactability and center-raycast check, but is not a physical/OS pointer test.
- RuntimeUnityEditor was downloaded/staged, not exercised interactively. Unity bundle authoring and ship assets were not tested in-game; a successful framework compile does not verify models, effects, tactical behavior or bundle compatibility.
- Other game builds, storefronts and code loaders need a new compatibility assessment. Native data packages have no UMM runtime requirement; this development workflow uses UMM for MCP.
- Dynamic state, new campaign types, changed victory logic and custom game screens require feature-specific tests beyond the starter recipes.

After updates, record the new assembly fingerprints and inspect private fields, overloads, initialization, cached calculations, scenario registration and save metadata. Rebuild and retest the supported scenarios; do not treat a branch label or successful compile as runtime compatibility.
