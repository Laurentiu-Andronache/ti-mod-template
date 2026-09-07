# Compatibility and validation record

This is a record of evidence, not a promise that a game version's private APIs will remain stable.

| Component | Initial profile |
|---|---|
| Operating system | Windows x64 only; PowerShell 5.1 entry point |
| Game reference | Installed TI assembly inspected locally; handbook baseline is 1.0.53a with Dark Skies |
| Unity authoring/player | 2020.3.49f1 |
| UMM | Installed 0.33; metadata filename `ModInfo.json` |
| Harmony | Installed UMM pair, handbook baseline 2.3.6 |
| Build | SDK 8.0.424, `net48` mod target; MCP/helper compiled against game BCL |
| Python | 3.11+; initial local checks use 3.14.7 |
| ILSpyCmd | 9.1.0.7988 |

## Evidence

Implementation validation is recorded here after the fresh-clone and runtime checks finish. Generated logs, screenshots, exact assembly hashes and run results stay in ignored local evidence directories.

The pinned handbook had passed its own validator and four offline tests during planning. The pinned MCP passed its stdio self-check and 552 offline tests. Those results support choosing the dependency revisions; they do not substitute for this scaffold's own integration tests.

## Limits

- Public CI runs game-independent validation only. It does not contain or obtain proprietary game assemblies.
- The UI helper's pointer-event dispatch includes an interactability and center-raycast check, but is not a physical/OS pointer test.
- Asset authoring requires the matching installed Unity/other tools. A successful ship-framework compile does not verify models, effects, tactical behavior or bundle compatibility.
- Other game builds, storefronts and code loaders need a new compatibility assessment. Native data packages have no UMM runtime requirement; this development workflow uses UMM for MCP.
- Dynamic state, new campaign types, changed victory logic and custom game screens require feature-specific tests beyond the starter recipes.

After updates, record the new assembly fingerprints and inspect private fields, overloads, initialization, cached calculations, scenario registration and save metadata. Rebuild and retest the supported scenarios; do not treat a branch label or successful compile as runtime compatibility.
