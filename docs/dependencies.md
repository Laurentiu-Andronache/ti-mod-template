# Dependency choices and updates

Exact pins and download hashes live in [the dependency lock](../tools/dependencies.lock.json). The gitlinks are the executable source of each submodule revision; setup verifies agreement with the lock and refuses incidental local edits.

| Dependency | Why included | How consumed |
|---|---|---|
| Laurentiu-Andronache/ti-mods | Full modding handbook, maintained code examples, asset helpers and reference recipes | Required pinned submodule; read locally and cite this fork |
| Laurentiu-Andronache/TerraInvictaMCP | Live game state, fixtures, screenshots and native mod validation | Required pinned submodule; built from its own reference list and staged in the expected installed layout |
| UNNRazorback/TIShipModdingFramework | TI-specific ship registration and prefab integration | Optional pinned submodule; initialized by the Ships profile |
| ILSpyCmd 9.1.0.7988 | Scriptable type listing and focused C#/IL inspection | Local .NET tool manifest, .NET 8 runtime |
| .NET SDK 8.0.424 | Reproducible compiler for net48 mods and MCP's direct Roslyn build | Prefer an installed exact SDK; otherwise SHA-512-verified local ZIP |
| RuntimeUnityEditor 6.3 | Live UI/object inspection independent of the custom helper | Optional SHA-256-verified UMM release, staged with TI-compatible metadata |
| UMM/Harmony | Code loading and patching matched to the actual installation | External prerequisite and local assembly references, never silently upgraded |

RuntimeUnityEditor source, ILSpy source, UMM source and Harmony source are available in their official projects, but a source checkout adds no capability needed by their default runtime/compiler usage here. AssetRipper's large source tree is similarly unnecessary for its export workflow. The ship framework is small and TI-specific, making local source useful for an agent adapting a model integration.

The optional ship submodule has `update = none`; ordinary recursive clone does not make it a mandatory tool. `setup -Tools Ships` explicitly initializes it with `--checkout`. To initialize just the required references manually:

```powershell
git submodule update --init --checkout -- references/ti-mods tools/TerraInvictaMCP
```

## Updating a pin

1. Read the selected dependency's release/commit notes and license. Review changed game/runtime requirements.
2. Update its submodule checkout and gitlink, then the corresponding lock entry. Never point either TI fork at upstream incidentally.
3. For downloads, record a specific versioned URL and digest from its release publisher; setup must not execute an unverified download.
4. Re-run offline checks and relevant local builds. For MCP, run its offline stdio/unit checks and live selftest; for UI, repeat the helper/inspector checks; for ships, repeat the targeted asset/runtime scenarios.
5. Refresh [compatibility](compatibility.md) with observed outcomes. Keep untested version claims explicit.

Building MCP here does not run its installer or register global clients. The adapter reads `$Refs` from the pinned PowerShell build script, invokes SDK Roslyn with `/nostdlib` and `/noconfig`, and copies only the needed source/server/docs/license metadata into staging. This retains the game's BCL identities and keeps the submodule clean.

Changes *inside* a dependency follow that dependency's contribution rules. Template work and new mods remain in this repository. Review a dependency change separately rather than editing its instructions to suit an unrelated task.
