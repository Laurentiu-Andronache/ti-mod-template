# Terra Invicta AI mod template

A Windows workspace that gives an AI coding agent the references and tools to **create, inspect, build, test, and package a Terra Invicta mod**.

Clone this repository into a new folder, open that folder in your agent, and describe the mod you want. The agent starts with [AGENTS.md](AGENTS.md), initializes a native, C#, or combined mod, and follows an evidence-based test loop. No game DLLs or extracted game content are included.

Example requests:

> Create a mod that replaces this faction's victory conditions with these requirements: …

> Add a button to the councilor recruitment screen that costs 30 influence and generates one new recruit. Disable it when the player cannot afford it.

Those are examples of workflows, not features silently added to every new mod. See [the worked recipes](docs/recipes.md).

## First run

Prerequisites: Windows x64, Git, Python 3.11+, a local Terra Invicta installation, and Unity Mod Manager configured for the game. Close the game before setup deploys files. The bootstrap downloads a verified, local .NET SDK when needed; Visual Studio is optional.

```powershell
git clone <your-repository-url> ti-my-mod
cd ti-my-mod
.\ti.ps1 setup
```

An ordinary clone works: setup initializes the required pinned submodules. For a game that discovery cannot identify uniquely:

```powershell
.\ti.ps1 setup -GameDir 'D:\SteamLibrary\steamapps\common\Terra Invicta'
```

Setup builds and deploys your pinned TerraInvictaMCP fork, restores ILSpyCmd, and generates local MCP configuration. Reconnect your agent's MCP server afterward. Codex uses the generated project configuration; other clients can use `.local/mcp-config.json`. See [setup and recovery](docs/setup.md) for prerequisites, existing installations, and optional tools.

## A mod's development loop

An agent can run these commands for you. To initialize manually:

```powershell
.\ti.ps1 init -Id Example.MyMod -Name 'My Mod' -Kind Hybrid -Author 'Your name'
.\ti.ps1 doctor
.\ti.ps1 build
.\ti.ps1 test -Offline
.\ti.ps1 test -Recipe code-smoke
.\ti.ps1 package
```

Choose `Native` for data/assets, `Code` for C# behavior, or `Hybrid` for both. `init` refuses an already-initialized clone. A code starter contains a harmless local Harmony probe; replace it as the mod takes shape. `code-smoke` tests that starter probe and is not an acceptance test for your new feature.

Runtime recipes build and deploy the mod, start a disposable game session, collect evidence, stop the process they started, and restore existing saves and settings. New test saves are retained under the run's evidence directory. Author feature-specific recipes before claiming a mod works.

## Where things live

| Location | Purpose |
|---|---|
| `mod.project.json` | Created by `init`; one source of mod identity, metadata, extra game references, and authored-asset allowlist |
| `content/` | Native JSON, localization, and explicitly listed authored assets |
| `src/Mod/` | C# source and development-only assertions, when applicable |
| `assets/UnityProject/` | Optional Unity 2020.3.49f1 authoring project, created with `init -Assets` |
| `references/` | Pinned handbook and optional ship framework |
| `tools/` | Workflow implementation, pinned MCP source, and development helper source |
| `.local/` | Ignored machine configuration, SDK, decompilation, backups, and test evidence |
| `artifacts/` | Ignored staged packages and release ZIPs |

Start with [the workflow guide](docs/workflow.md), [testing](docs/testing.md), and [capability map](docs/capabilities.md). [Dependencies](docs/dependencies.md) explains which tools are embedded, downloaded, or external. [Compatibility](docs/compatibility.md) records exactly what has been checked.

This template's handbook and MCP references point to **Laurentiu-Andronache's forks**. Their pinned versions remain available locally, so an agent does not need to reconstruct this knowledge from upstream pages. Specialist authoring still requires the appropriate tools and assets, and each game update needs compatibility checks.

New scaffolding is MIT licensed. See [third-party notices](THIRD_PARTY_NOTICES.md) before redistributing dependencies.
