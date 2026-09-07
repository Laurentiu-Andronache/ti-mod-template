# Setup, diagnosis, and recovery

## Requirements

Use Windows x64, Git, Python 3.11 or later, Steam with Terra Invicta installed, and a compatible Unity Mod Manager installation. The game's Mono runtime is independent of the .NET SDK used to compile mods. This scaffold's default mod target is `net48`; it restores SDK **8.0.424** and ILSpyCmd **9.1.0.7988**. It does not install another code loader alongside UMM.

Install Python from [python.org](https://www.python.org/downloads/windows/) if `py -3 --version` is missing or too old. For UMM, follow [its project](https://github.com/newman55/unity-mod-manager) and the [MCP prerequisites](../tools/TerraInvictaMCP/README.md#requirements). Start the game once to verify the UMM menu and create the player's profile, then close it. SDKs and ILSpyCmd are restored by the scaffold; game assemblies are never downloaded.

```powershell
.\ti.ps1 setup
.\ti.ps1 doctor
```

Setup checks the Git pins, discovers Steam libraries through the Windows registry and `libraryfolders.vdf`, validates `Assembly-CSharp.dll`, restores developer tools, compiles MCP, deploys its required files, and generates project-local client configuration. No global PATH changes are required. A local SDK download is verified against the SHA-512 in the dependency lock before extraction.

If discovery finds multiple installations, choose explicitly:

```powershell
.\ti.ps1 setup -GameDir 'D:\Games\SteamLibrary\steamapps\common\Terra Invicta'
```

`TerraInvictaDir` or `TI_ROOT` can also identify a candidate. A directory with a familiar name is insufficient: its managed assembly must exist. The generated `.local/machine.json` is never committed. After moving a clone, rerun setup to refresh paths.

## Optional tools

```powershell
.\ti.ps1 setup -Tools 'UI,Ships'
.\ti.ps1 setup -NoDeploy
```

`UI` downloads the checksum-pinned RuntimeUnityEditor UMM package. Its generic `Info.json` is adapted in staging to Terra Invicta's `ModInfo.json`, and other JSON catalogs are excluded. Its GPL license remains with the separate tool. Use F12 in-game after enabling it. It is never copied into a mod's release ZIP.

`Ships` initializes the optional ship-framework submodule and compiles its sources with local game references. It does not create or install ships, author models, or prove compatibility. See [assets](assets.md).

`-NoDeploy` restores/builds/stages tools and prepares client snippets without changing installed mod files. The client configuration points to the eventual installed server, so a connection still requires deployment. For authoring assets, `init -Assets` adds the separate Unity project; Unity/Unity Hub and Windows build support are external prerequisites.

## Loader metadata

The inspected installation uses:

```xml
<ModsDirectory>Mods/Enabled</ModsDirectory>
<ModInfo>ModInfo.json</ModInfo>
```

Native TI data always has `ModInfo.json`. Code fields can share that file when UMM uses the same filename. The installed native scanner collects `.json` files recursively and excludes `ModInfo.json`; an extra `ModFile.json`, `Info.json`, dependency manifest or JSON cache may be processed as a game template.

The handbook examples recorded a `ModFile.json` UMM configuration in their earlier baseline. This scaffold deliberately checks the actual installed `UnityModManager/Config.xml`. If it differs, setup reports the conflict and leaves it unchanged. Repair or migrate the UMM profile with its installer and account for existing code mods' metadata before retrying; blindly changing the filename can make those mods disappear.

Native-only packages do not need UMM to run for players. UMM is needed here for development MCP and C# behavior. Native-only manifests omit UMM's `Id`, assembly and entry fields, so UMM skips them.

## Connect an agent

Generated files:

- `.codex/config.toml`: a marked `[mcp_servers.terra-invicta]` block with absolute interpreter/server paths. Existing unrelated settings are preserved. An existing unmarked server entry is reported for a deliberate merge.
- `.local/mcp-config.json`: generic `mcpServers` configuration for other clients.

Codex uses project MCP configuration for trusted projects. Reconnect or restart the MCP server after setup. See the [official MCP guide](https://learn.chatgpt.com/docs/extend/mcp?surface=cli). Other agents can use the generic snippet and must be told to read `AGENTS.md` if they do not recognize it automatically.

MCP's Python process must run from the **installed** `Mods/Enabled/TerraInvictaMCP/server` layout. Its path calculations are relative to that location. Do not point it at `tools/TerraInvictaMCP/server` in the source submodule. Restarting the game replaces the bridge DLL; reconnecting the client replaces its cached Python server code.

If the current agent cannot acquire new MCP tools mid-session, use the CLI fallback:

```powershell
.\ti.ps1 call -Tool observe
.\ti.ps1 call -Tool selftest
```

Use `call` for a tool in a game session you are already working with; `test -Recipe ...` owns a recoverable launch/stop cycle.

## Recovery

Deployment journals live under `.local/deployments`. Each records original files, hashes, intended changes and status before writing installed files. Repeated deployment removes stale owned files and preserves unowned settings. An externally edited owned file causes a diagnostic instead of being overwritten.

With the game closed:

```powershell
.\ti.ps1 restore
.\ti.ps1 restore -Session 'the-run-folder-name'
```

Plain `restore` reverses this clone's deployment journals in reverse order, including replaced MCP files. `-Session` recovers saves/profile/UMM settings from an unfinished runtime run. Recover the session first if both are outstanding. Generated test saves are archived with the run's evidence. Do not delete `.local` until its outstanding journals have been restored or intentionally retained.

Session recovery can stop its recorded game process itself after checking PID,
executable path and start time. A live interactive worker retains the installation
lock: use `session finish -Session <id>` for it. After a worker interruption,
`restore -Session <id>` performs recovery; it never resumes queued mutations.
See [interactive testing](interactive-testing.md) for the complete workflow.

The test runner stops only its recorded game PID with matching path and start time. A pre-existing game is left alone. If process ownership cannot be established, recovery waits for you to close the game instead of guessing which process to terminate.

After a game update, `doctor` reports changed assembly fingerprints. Check loader injection with UMM, rerun setup, inspect changed hooks, rebuild, reconnect MCP and repeat the affected runtime recipes.
