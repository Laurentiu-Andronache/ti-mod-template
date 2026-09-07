# Commands and project workflow

Run commands from your clone. `ti.ps1` forwards arguments to a Python standard-library implementation; every command also accepts `--help`.

## Describe and initialize

Decide which behavior the player should see, which scenarios/factions it applies to, and whether existing saves must work. For ambiguous terms such as "advisor", inspect the game vocabulary and clarify the intended object before building the wrong feature.

```powershell
.\ti.ps1 init -Id Author.Example -Name 'Example Mod' -Kind Hybrid -Author 'Author'
```

The descriptor generated at the root is the only identity source:

```json
{
  "schemaVersion": 1,
  "id": "Author.Example",
  "name": "Example Mod",
  "kind": "Hybrid",
  "author": "Author",
  "version": "0.1.0",
  "description": "Describe the behavior.",
  "native": { "LoadOrder": 0 },
  "requiredAssemblies": [],
  "packageFiles": []
}
```

Use dotted IDs containing identifier segments of letters/digits, starting with letters. Match the namespace when renaming authored C# after initialization. `id`, DLL name, entry type and native folder title stay aligned. Version is `major.minor.patch`. `name` is the human-facing UMM display name; native `Title` remains the folder ID for the game's menu operations.

`native` accepts `LoadOrder`, `ModURL`, `TemplatesToConcatArrays`, `TemplatesToReplaceArrays`, and `TemplatesToReplace`. Array settings are lists of exact filenames including `.json`. `requiredAssemblies` adds installed Managed-directory DLLs to the build with `Private=false`, for example `UnityEngine.UI.dll` and `Unity.TextMeshPro.dll`. `packageFiles` explicitly lists authored non-JSON/non-localization files, relative to `content/`.

Initialization creates one mod and refuses to overwrite existing content. `Native` creates no C# project. `Code` and `Hybrid` create the same extensible UMM lifecycle starter; the distinction documents intent. Native builds can stage/package without the game or SDK, but require in-game verification before release.

## Investigate

```powershell
.\ti.ps1 inspect
.\ti.ps1 inspect -Type 'PavonisInteractive.TerraInvicta.TICouncilorState'
.\ti.ps1 inspect -Type 'PavonisInteractive.TerraInvicta.TICouncilorState' -IL
```

The first command lists classes. Output paths include the source DLL hash under `.local/inspection/`. Search the index before guessing namespaces: some TI types are global, others are namespaced. `-Assembly` selects another DLL directly under Managed. Add relevant dependencies, callers, signature and timing notes to a feature design without copying reconstructed game code into Git.

For data, compare the shipped template, scenario overlays and actual consuming code. Use the running engine's MCP `template` and `localize` results to check effective values. The original files on disk need not change when a native patch succeeds.

## Build and deploy

```powershell
.\ti.ps1 build
.\ti.ps1 build -Configuration Debug -DevTools
.\ti.ps1 deploy -Configuration Debug -DevTools
```

Build validates content and stages only the manifest, mod DLL when applicable, native/localization files, explicitly listed authored assets, and license notices. It recreates staging so obsolete files cannot leak into the package. Code compiles for `net48` using local game/Unity/UMM/Harmony references. Never distribute their copied binaries.

`-DevTools` enables the conditional development test type and builds a separate console/UI helper. Ordinary Release builds do not contain that test type. Deployment requires the game to be closed; DLL replacement takes effect after restart.

The validator enforces a flat JSON layout, strict JSON with no duplicate keys, record arrays with unique `dataName`, object-shaped GlobalConfig, and recognized template filenames when the game is present. It cannot infer every cross-template reference or prove gameplay semantics. For a new custom template type defined by code, extend the filename validation deliberately after documenting its type and loader registration; do not bypass the check by inventing a vanilla filename.

## Test and package

```powershell
.\ti.ps1 test -Offline
.\ti.ps1 test -Recipe code-smoke
.\ti.ps1 test -Recipe ui-smoke
.\ti.ps1 test -Recipe 'tests/recipes/my-feature.json'
.\ti.ps1 logs
.\ti.ps1 package
```

Offline tests exercise the scaffold's file operations and package validation, not Unity. Runtime recipes assert behavior in a game owned by the test runner. See [testing](testing.md) for the format and evidence boundaries.

`package` always rebuilds Release with development tests disabled. It produces `artifacts/<id>-<version>.zip` with the installable mod folder at its root and prints a SHA-256. Inspect the ZIP and retest the actual release build when test hooks could affect timing or dependencies. C# patch hooks, custom saved types and additional runtime libraries require their own acceptance tests.

## Template maintenance

Keep `.local` and `artifacts` out of Git. Treat submodules as reference dependencies. Run the offline suite for changes to tooling and affected runtime recipes for changes to build, deployment, game interaction, or C# helper code.

Public Windows CI initializes required submodules and runs offline tests. It cannot compile a real game mod or run a campaign without proprietary installed references. The [compatibility record](compatibility.md) separates those checks.
