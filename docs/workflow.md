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
  "description": "Describe the behavior.\n\nCreated using https://github.com/Laurentiu-Andronache/ti-mod-template",
  "native": { "LoadOrder": 0 },
  "requiredAssemblies": [],
  "packageFiles": []
}
```

Use dotted IDs containing identifier segments of letters/digits, starting with letters. Match the namespace when renaming authored C# after initialization. `id`, DLL name, entry type and native folder title stay aligned. Version is `major.minor.patch`. `name` is the human-facing UMM display name; native `Title` remains the folder ID for the game's menu operations.

`native` accepts `LoadOrder`, `ModURL`, `TemplatesToConcatArrays`, `TemplatesToReplaceArrays`, and `TemplatesToReplace`. Array settings are lists of exact filenames including `.json`. `requiredAssemblies` adds installed Managed-directory DLLs to the build with `Private=false`, for example `UnityEngine.UI.dll` and `Unity.TextMeshPro.dll`. `packageFiles` explicitly lists authored non-JSON/non-localization files, relative to `content/`.

Initialization creates one mod and refuses to overwrite existing content. `Native` creates no C# project. `Code` and `Hybrid` create the same extensible UMM lifecycle starter; the distinction documents intent. Native builds can stage/package without the game or SDK, but require in-game verification before release.

Every generated mod description ends with the standalone line
`Created using https://github.com/Laurentiu-Andronache/ti-mod-template`.
Initialization includes it in `mod.project.json`; build, deploy and package
ensure it appears once at the end of `ModInfo.json`'s `Description`, including
for existing projects. Keep the same final line in publication descriptions.

## Investigate

```powershell
.\ti.ps1 inspect
.\ti.ps1 inspect -Type 'PavonisInteractive.TerraInvicta.TICouncilorState'
.\ti.ps1 inspect -Type 'PavonisInteractive.TerraInvicta.TICouncilorState' -IL
```

The first command lists classes. Output paths include the source DLL hash under `.local/inspection/`. Search the index before guessing namespaces: some TI types are global, others are namespaced. `-Assembly` selects another DLL directly under Managed. Add relevant dependencies, callers, signature and timing notes to a feature design without copying reconstructed game code into Git.

`-IL` emits **assembly-wide IL**, including when `-Type` is supplied. With the
pinned ILSpyCmd 9.1.0.7988, type selection does not filter IL. Output is named
`Assembly-CSharp.assembly.il.txt`; its `.source.json` sidecar records the requested
type separately from the actual scope, arguments and assembly fingerprint. The
assembly-wide file can be large. Use focused searches such as
`rg -n 'TICouncilorState::' .local/inspection/<hash>/Assembly-CSharp.assembly.il.txt`,
then read the surrounding declaring method. Without `-IL`, `-Type` still selects C#.

For data, compare the shipped template, scenario overlays and actual consuming code. Use the running engine's MCP `template` and `localize` results to check effective values. The original files on disk need not change when a native patch succeeds.

## Build and deploy

```powershell
.\ti.ps1 build
.\ti.ps1 build -Configuration Debug -DevTools
.\ti.ps1 deploy -Configuration Debug -DevTools
.\ti.ps1 build -Configuration Release -DevTools -NoModTests
.\ti.ps1 build -Configuration Debug -ModTests
```

Build validates content and stages only the manifest, mod DLL when applicable, native/localization files, explicitly listed authored assets, and license notices. It recreates staging so obsolete files cannot leak into the package. Code compiles for `net48` using local game/Unity/UMM/Harmony references. Never distribute their copied binaries.

`-DevTools` builds the separate console/UI helper (and deploys it for `deploy`).
`-ModTests` and `-NoModTests` independently control conditional mod assertions.
For compatibility, omitting both retains the old behavior: `-DevTools` also
enables mod tests. A production test uses explicit
`-Configuration Release -DevTools -NoModTests`. Debug alone does not imply test
hooks. Build evidence records both choices. Deployment requires the game closed;
restart loads new DLLs.

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
