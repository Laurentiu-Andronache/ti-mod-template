# Interactive disposable sessions

Run from an initialized disposable code-mod clone after `setup` and `doctor`.
The same lifecycle as recipes snapshots saves, profile and UMM settings, deploys
through journals, records the game PID/path/start time, and restores on finish.
The external worker lasts at most two hours. Its MCP connection stays open so
campaign tokens, pause policy and tool sequence stay coherent. It runs hidden;
build/startup output is in `worker.log`.

```powershell
$started = .\ti.ps1 session start -Json '{"configuration":"Release","modTests":false,"devTools":true}' | ConvertFrom-Json
$session = $started.session
.\ti.ps1 session command -Session $session -Json '{"id":"observed","tool":"observe","expect":{"/bridge":"up"},"waitSeconds":300}'
.\ti.ps1 session command -Session $session -Json '{"id":"campaign","tool":"campaign_new","arguments":{"scenario":"ModernScenario","faction":"ResistCouncil","options":["VeryLightSolarSystem"]}}'
.\ti.ps1 session command -Session $session -Json '{"id":"ready","tool":"observe","expect":{"/campaign":true},"waitSeconds":300}'
.\ti.ps1 session command -Session $session -Json '{"id":"helper","tool":"dev","arguments":{"op":"status"},"expect":{"/ok":true,"/initialized":true},"waitSeconds":300}'
.\ti.ps1 session command -Session $session -Json '{"id":"saved","tool":"save_game","arguments":{"name":"scratch-session-example"}}'
.\ti.ps1 session finish -Session $session
```

The worker calls `observe` before launch as well. `start` returns immediately;
queued commands run after readiness. Read `ready.json` or `worker.log` for startup
progress. Every command and raw MCP reply is archived under the explicit session
folder. `finish` waits for final health and recovery, returning the full result.
Negative assertions can explicitly expect helper `ok:false`. A failed command
keeps the session result failed even if later commands succeed.

`-File request.json` accepts a structured request without shell quoting;
`-File -` reads one JSON object from stdin. The same options apply to `start`.
Commands support recipe JSON Pointers and `${stepId/path}` references; IDs are
session-local letters, digits, underscores and hyphens. Without an ID the client
generates a UUID and records it in the queue. Prefer explicit IDs for automation.
Only read-only observation steps may use `waitSeconds` (1–300).

In PowerShell, pipe JSON with the dash quoted:
`'{"id":"observedAgain","tool":"observe"}' | .\ti.ps1 session command -Session $session -File '-'`.
For a process with redirected stdin, the direct Python entry point also accepts
`py -3 tools/ti.py session command -Session <id> -File -`.

Submitting the same ID and request returns its original response. Reusing an ID
for a different request fails. Dispatch intent is persisted before execution;
after a timeout or interruption the mutation may have happened, so inspect its
outcome and never resubmit it under a new ID. There is no automatic replay or
resume of interrupted commands. Queue and result writes are atomic.

## Load an archived fixture with the project mod absent

Start a fresh session using
`{"configuration":"Release","modTests":false,"devTools":true,"deployMod":false}`.
Import the previous run's `generated-saves/scratch-session-example.gz` using an
explicit absolute source path in a request file:

```json
{
  "id": "imported",
  "tool": "import_save",
  "arguments": {
    "source": "C:/your-clone/.local/runs/PREVIOUS-RUN/generated-saves/scratch-session-example.gz",
    "name": "scratch-session-reload"
  }
}
```

The destination must be a new scratch name. Import does not load or overwrite a
save; next send `load_game` with `name:"scratch-session-reload"`, then poll
`observe` and helper `status`. Inspect the loaded state and compare exceptions
with a baseline. `finish` archives generated saves and restores any project copy
temporarily removed for the test. Source/destination hashes are recorded.

## Recovery and evidence

An unfinished session blocks another one, including in a different clone using
the same installation. Use `finish` for a live worker. After its process has been
interrupted, recover from the owning clone:

```powershell
.\ti.ps1 restore -Session $session
```

Recovery stops only the matching owned game process. It preserves external edits
under the deployment journal rules and reports conflicts. Repeating completed
recovery is harmless. Preserve `.local` until every session and deployment is
restored. Plain `restore` reverses setup deployments after session recovery.

Evidence includes resolved options, installed assembly fingerprint, staged and
deployed file hashes, command intent/results, screenshots, logs, health and final
recovery status. For Release acceptance, compare the deployed DLL hash with the
DLL inside the final `package` ZIP. Session success is not proof of a particular
gameplay feature; use the [UI example](ui-testing-example.md) and feature assertions.
