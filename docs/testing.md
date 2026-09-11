# Testing interfaces and evidence

## What a passed test means

Compilation proves references and C# syntax work. Native `modcheck` compares effective data and finds some reference/localization/reachability problems. A fixture proves only the mechanism it exercises: MCP's generic actions and spawns can bypass the cost and eligibility that a player must satisfy. UI handler dispatch proves event wiring with the reported checks; an OS pointer click is separate evidence.

Before claiming the feature works, test the behavior the user requested, its failure cases, and relevant lifecycle transitions. A startup screenshot is not proof of campaign behavior. The [worked recipes](recipes.md) give concrete acceptance criteria.

## Running recipes

For exploratory work using the same recovery lifecycle, see
[interactive sessions](interactive-testing.md). For a fingerprint-specific UI
investigation, see the [worked UI example](ui-testing-example.md).

```powershell
.\ti.ps1 test -Offline
.\ti.ps1 test -Recipe code-smoke
.\ti.ps1 test -Recipe ui-smoke
.\ti.ps1 test -Recipe native-smoke
```

`code-smoke` targets the generated starter's `Probe` test. `ui-smoke` creates a development-only canvas and tests enabled/disabled buttons, raycast checks, destruction, reopening, and stale handles. `native-smoke` runs merge/reference/localization checks for the current mod from the main menu; add campaign-level assertions for actual availability and effects.

Runtime recipes require the game closed and MCP deployed by setup. They snapshot the actual save directory (preferring `savedGamesPath` from the log), including profile, autosaves and continue slots; back up UMM options; enable the test's tools and native mod support; then start the game through Steam. Existing other mods keep their enabled state, which is recorded through MCP observations and logs. For a conflict test, record that set and the intended load order explicitly.

The runner captures the game PID, executable path and start time after its launch request. On completion or failure it stops only that owned process, archives newly created saves, restores original saves/settings, and reverses this recipe's mod/helper deployments. The separately deployed MCP setup stays installed until `restore` reverses it.

An interrupted process leaves a recoverable `session.json`. Run
`restore -Session <run-folder>` from its owning clone; recovery stops only the
recorded matching game process. An active interactive worker must be finished
first. If ownership is missing or another game is running, close that game
yourself before retrying. Then use plain `restore` if setup deployment recovery
is also needed. Damaged original backups are refused.

Shutdown, log collection and restoration are attempted independently. A diagnostic
failure still fails the run but cannot skip restoration. `result.json` retains
the original error, each `cleanupErrors` entry and `recoveryStatus`; when recovery
is required it includes the exact recovery command. If result writing itself
fails, the combined result is printed to stderr and the session journal remains
the recovery authority. A machine-local installation lock prevents two clones
from testing the same installation concurrently or bypassing an unfinished run.

## Recipe format

Four options are independent. `configuration` is `Debug` or `Release`;
`modTests` controls `TI_MOD_TESTS`; `devTools` deploys the external helper;
`deployMod` controls project deployment. Omitted options preserve legacy recipes:
configuration is Debug with `devTools:true`, otherwise Release; `modTests` defaults
to `devTools`; `deployMod` defaults to true. Explicit values must have the right
types. For production testing use all three explicit values:

```json
{"schemaVersion":1,"configuration":"Release","modTests":false,"devTools":true,"deployMod":true,"steps":[]}
```

`deployMod:false` skips the project build and journals temporary removal of its
installed folder, including settings. DLL/metadata absence and runtime mod
listing are checked before accepting the session. A renamed duplicate install
is refused. Recovery restores the original project installation; unrelated mods
retain their enabled state. Use this only for saves whose removal behavior the
mod promises, such as changes using vanilla saved types.

Recipes are small JSON files stored outside deployable content. This example is executable against an initialized code starter:

```json
{
  "schemaVersion": 1,
  "devTools": true,
  "steps": [
    {
      "id": "campaign",
      "tool": "campaign_new",
      "arguments": { "scenario": "ModernScenario", "faction": "ResistCouncil", "options": ["VeryLightSolarSystem"] }
    },
    {
      "id": "ready",
      "tool": "observe",
      "arguments": {},
      "expect": { "/campaign": true },
      "waitSeconds": 300
    },
    {
      "id": "initialized",
      "tool": "dev",
      "arguments": { "op": "status" },
      "expect": { "/ok": true, "/initialized": true, "/crashed": false },
      "waitSeconds": 300
    },
    {
      "id": "probe",
      "tool": "dev",
      "arguments": { "op": "run", "mod": "${mod}", "name": "Probe" },
      "expect": { "/ok": true, "/result/passed": true }
    }
  ]
}
```

Each step has a unique alphanumeric `id`, MCP `tool`, `arguments`, and optional `expect` mapping of [JSON Pointers](https://www.rfc-editor.org/rfc/rfc6901) to exact expected values. Types are strict: `true` is not the number `1`. A missing asserted path fails. The special `dev` tool routes through the helper below.

`${mod}` is the current mod ID. `${run}` is the evidence folder name. `${stepId/path/to/value}` substitutes an entire value from a previous step's structured result; it is not arbitrary code or string interpolation. Use it to carry current game IDs or UI handles forward. Do not hard-code IDs copied from another campaign.

For an asynchronous load, add `waitSeconds` (maximum 300) to an observation/assertion step. Only `observe`, `query`, `template`, `localize`, and development `status`/`inspect` steps may be retried. Mutating calls are issued once; an uncertain result needs inspection, not an automatic duplicate action. Recipes cannot directly call `game_start`/`game_stop`; the runner owns lifecycle. Use separate recipes for application-restart tests.

Each tool call, resolved arguments, assertions, screenshot, package hash, installation fingerprint, and final status is recorded in `.local/runs/<run-id>/`. The runner also requires a responding bridge and no reported engine crash at the end. Missing tool capabilities or recovery failures are failures with an explanation, never silent skips. These files contain local paths and game state: summarize/redact evidence before intentionally sharing it.

Campaign initialization does not mean the desired screen is visible: an intro cinematic or prompt can still cover it. Inspect the screenshot and current hierarchy, then use the relevant player-facing close/continue action before asserting a game screen. A black cinematic frame must not be reported as successful visual verification.

## Development helper

The helper can inspect production builds with no mod test methods. Its `tests`
and `run` operations require `modTests:true`; its UI operations do not.

Keep custom results compact: return counts, IDs and the few values asserted, then
request a separate observation for details. Tree traversal is already bounded;
inspect a narrower child instead of embedding whole screens in a custom result.
The pinned MCP server at commit `c961ccc86028b3f494fdbf121c3b2b0082eea10d`
replaces serialized JSON payloads above 160,000 characters with a complete JSON
`response_too_large` diagnostic and sets `isError:true`. The diagnostic includes
`textLength` and `textLimit`; the original payload is omitted. This counts
serialized characters, including JSON escapes, before the surrounding MCP
envelope. The client rejects the tool error and retains raw evidence. The handler
has already run, so inspect current state before retrying a mutation. Narrow
reads or return smaller custom results. The client also recognizes legacy
truncation suffixes and distinguishes malformed JSON from an absent marker.
Partial JSON never counts as a successful result. No new wire limit is imposed.

Build/deploy with `-DevTools` or use a recipe with `devTools: true`. **A loaded campaign is required by MCP's console bridge**, even for the harmless starter probe. The code/UI smoke recipes create a disposable campaign and wait for it to load. The separate UMM helper registers `ti_dev` when the game terminal exists, including terminals initialized before or after the helper. It unregisters only its own registration when disabled.

The wire format uses one base64-encoded UTF-8 JSON request as the command's argument. This avoids TI's comma-separated console argument parsing. It emits a tagged JSON result, `TI_DEV_RESULT:…`, which the runner extracts. Every response has `ok`; failures have `error`. A command failing with `ok:false` can be an explicitly asserted negative test.

CLI example in an active test session:

```powershell
.\ti.ps1 dev -Json '{"op":"status"}'
.\ti.ps1 dev -Json '{"op":"roots"}'
```

| Operation | Inputs and behavior |
|---|---|
| `status` | Reports helper version, enabled state, campaign initialization and engine crash flag |
| `roots` | Lists up to 128 loaded-scene roots and 128 canvases, including persistent UI |
| `tree` | `handle`, optional `depth` (0–8) and `limit` (1–200); bounded hierarchy with names/components/text and handles |
| `inspect` | `handle`; reads the current object, active and interactable state |
| `click` | `handle`; Button or Toggle only; checks active state, interactability, EventSystem, and top center raycast before Unity pointer-click dispatch |
| `tests` | `mod`; lists development test methods in that mod |
| `run` | `mod`, `name`; executes one development test method and returns its JSON result |
| `fixture` | `action`: `create`, `status`, `destroy`; creates/removes the helper's own test canvas and click counter |

Handles reference the actual Unity object and are invalid after destruction, helper disable, or handle-cache eviction. Reinspect after screen/campaign changes. Output traversal is bounded; increase the requested depth deliberately or inspect a narrower child. Long-running game tests belong in client-side polling, not a console callback that freezes the Unity frame.

UI evidence should cover long text, scaling, scroll/clipping, input focus and tooltips in addition to handler behavior. The development fixture is a tool self-test; it does not inspect your recruitment screen for you. Use your agent's desktop tools for final real-pointer checks where available, and document when they were unavailable.

## Writing mod assertions

The starter's `<ModId>.DevelopmentTests` type exists only with `TI_MOD_TESTS`. Each declared public static method with no parameters and a `string` return is callable. Return a JSON object with `passed` and useful observed values. A thrown exception is caught and reported by the helper.

Keep each method short enough to finish in a frame. Prefer separate setup/action/observation methods and recipe polling over synchronous multi-day simulations. Restore temporary settings in `finally`, as the starter probe does. Do not treat test setup as the player-facing behavior under test.

The ordinary release build removes the development type and does not reference the helper assembly. `package` rebuilds with tests disabled. Inspect a release with ILSpyCmd to verify that game-affecting test hooks are absent when extending this pattern.

## Logs and troubleshooting

The first relevant exception is usually more useful than the last cascade of null references. Inspect `Player.log`, the game's log under `Logs`, and UMM's `Log.txt`, captured before a later launch rotates them. Record the triggering action and compare with the baseline mod set. Use [the handbook's debugging guide](../references/ti-mods/docs/debugging.md) for loader errors, initialization order, persisted-state failures and version-specific hooks.

MCP reads its own playbook via resources; use it before scripting campaign setup. Its clock watchdog may refuse mutations after a long paused setup. Set a justified pause limit explicitly, record it, and return to normal progress. A blocked event/prompt is not a reason to spin on `advance` indefinitely.
