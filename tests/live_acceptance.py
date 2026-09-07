"""Explicit opt-in maintenance checks. Run only in an initialized disposable clone.

Uses generic starter/helper assertions; never imports another mod's gameplay.
All sessions restore themselves, including assertion failures. Setup deployments
are intentionally restored separately with ti.ps1 restore after this script.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from scaffold import Workspace, WorkflowError, digest, read_json, write_json
from runtime import run_recipe
from sessions import start_interactive, submit_command


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print("PASS " + message, flush=True)


def command(workspace, sid, identity, tool, arguments=None, expect=None, wait=1):
    response = submit_command(workspace, sid, dict(id=identity, tool=tool, arguments=arguments or {},
                                                  expect=expect or {}, waitSeconds=wait))
    check(response["ok"], identity + ": " + response.get("error", "completed"))
    return response["data"]


def restored(workspace, evidence):
    record = read_json(evidence / "session.json")
    check(record["status"] == "restored", evidence.name + " restored")
    for entry in record["files"]:
        check(digest(entry["path"]) == entry["sha256"], entry["group"] + " original hash " + Path(entry["path"]).name)
    for journal in record.get("deploymentJournals", []):
        data = read_json(workspace.root / journal)
        check(data["status"] == "restored", "deployment restored " + Path(data["target"]).name)
        for name, entry in data["files"].items():
            target = Path(data["target"]) / name
            check((digest(target) if target.is_file() else None) == entry["before"], "deployment original hash " + name)


def main():
    workspace = Workspace(ROOT)
    project = workspace.project()
    if not project["id"].startswith("TemplateMaintenance."):
        raise WorkflowError("Initialize a disposable clone with a TemplateMaintenance.* code starter first")
    summary = {"fingerprint": workspace.fingerprint(workspace.game()), "runs": []}
    recipe = read_json(ROOT / "tests/recipes/ui-smoke.json")
    recipe["steps"].insert(3, {"id": "probe", "tool": "dev", "arguments": {"op": "run", "mod": "${mod}", "name": "Probe"}, "expect": {"/ok": True, "/result/passed": True}})
    recipe["steps"].append({"id": "save", "tool": "save_game", "arguments": {"name": "scratch-maintenance-debug"}})
    recipe_path = workspace.local / "maintenance-debug.json"
    write_json(recipe_path, recipe)
    debug = run_recipe(workspace, recipe_path)
    restored(workspace, debug)
    summary["runs"].append(str(debug))
    fixture = debug / "generated-saves/scratch-maintenance-debug.gz"
    check(fixture.exists(), "Debug fixture archived")

    release = start_interactive(workspace, dict(configuration="Release", modTests=False, devTools=True))
    sid = release["session"]
    evidence = Path(release["evidence"])
    try:
        command(workspace, sid, "observed", "observe", expect={"/bridge": "up"}, wait=300)
        command(workspace, sid, "imported", "import_save", {"source": str(fixture), "name": "scratch-maintenance-release"})
        command(workspace, sid, "loaded", "load_game", {"name": "scratch-maintenance-release"})
        command(workspace, sid, "ready", "observe", expect={"/campaign": True}, wait=300)
        command(workspace, sid, "helper", "dev", {"op": "status"}, {"/ok": True, "/initialized": True}, 300)
        command(workspace, sid, "hooksAbsent", "dev", {"op": "tests", "mod": project["id"]}, {"/ok": False})
        created = command(workspace, sid, "fixture", "dev", {"op": "fixture", "action": "create"}, {"/ok": True})
        click = dict(id="click", tool="dev", arguments={"op": "click", "handle": created["button"]["handle"]}, expect={"/ok": True, "/fixtureClicks": 1})
        first = submit_command(workspace, sid, click)
        check(first["ok"], "Release helper click")
        check(submit_command(workspace, sid, click) == first, "duplicate command returns same response")
        command(workspace, sid, "counter", "dev", {"op": "fixture", "action": "status"}, {"/clicks": 1})
        command(workspace, sid, "screen", "screenshot")
        command(workspace, sid, "fixtureCleanup", "dev", {"op": "fixture", "action": "destroy"})
        command(workspace, sid, "saved", "save_game", {"name": "scratch-maintenance-release-saved"})
    finally:
        finish = submit_command(workspace, sid, {"id": "session_finish", "tool": "finish"})
        check(finish["ok"], "Release session finished")
    restored(workspace, evidence)
    summary["runs"].append(str(evidence))
    tested_hash = read_json(evidence / "result.json")["deployedFiles"][project["id"]][project["id"] + ".dll"]
    package = workspace.package()
    with zipfile.ZipFile(package) as archive:
        dll = archive.read(project["id"] + "/" + project["id"] + ".dll")
        check(hashlib.sha256(dll).hexdigest() == tested_hash, "packaged DLL matches tested Release hash")
        check(not any("DevTools" in name or "DevelopmentTests" in name for name in archive.namelist()), "ZIP excludes helper and test sources")
    summary.update(package=str(package), releaseDllSha256=tested_hash, zipSha256=digest(package))

    # Seed an installed project copy to prove absence does not simply skip deploy.
    stage = ROOT / "artifacts/Release" / project["id"]
    workspace.deploy_folder(stage, project["id"])
    absent = start_interactive(workspace, dict(configuration="Release", modTests=False, devTools=True, deployMod=False))
    sid = absent["session"]
    absent_evidence = Path(absent["evidence"])
    try:
        command(workspace, sid, "observed", "observe", expect={"/bridge": "up"}, wait=300)
        command(workspace, sid, "imported", "import_save", {"source": str(evidence / "generated-saves/scratch-maintenance-release-saved.gz"), "name": "scratch-maintenance-absent"})
        command(workspace, sid, "loaded", "load_game", {"name": "scratch-maintenance-absent"})
        observed = command(workspace, sid, "ready", "observe", expect={"/campaign": True}, wait=300)
        check(observed["scenario"]["dataName"] == "ModernScenario", "mod-absent saved scenario retained")
        command(workspace, sid, "helper", "dev", {"op": "status"}, {"/ok": True, "/initialized": True}, 300)
        check(not (workspace.game() / "Mods/Enabled" / project["id"] / "ModInfo.json").exists(), "installed project metadata absent during load")
        check(not (workspace.game() / "Mods/Enabled" / project["id"] / (project["id"] + ".dll")).exists(), "installed project DLL absent during load")
        command(workspace, sid, "screen", "screenshot")
    finally:
        check(submit_command(workspace, sid, {"id": "session_finish", "tool": "finish"})["ok"], "absence session finished")
    restored(workspace, absent_evidence)
    summary["runs"].append(str(absent_evidence))

    interrupted = start_interactive(workspace, dict(configuration="Release", modTests=False, devTools=True))
    sid = interrupted["session"]
    command(workspace, sid, "observed", "observe", expect={"/bridge": "up"}, wait=300)
    # This is the worker just launched and owned by this test, not a game process.
    subprocess.run(["taskkill.exe", "/PID", str(interrupted["workerPid"]), "/F"], check=True)
    time.sleep(1)
    subprocess.run([sys.executable, str(ROOT / "tools/ti.py"), "restore", "-Session", sid], check=True)
    restored(workspace, Path(interrupted["evidence"]))
    summary["runs"].append(interrupted["evidence"])
    write_json(workspace.local / "maintenance-live-result.json", {"status": "passed", **summary})
    print("LIVE ACCEPTANCE PASSED " + str(workspace.local / "maintenance-live-result.json"), flush=True)


if __name__ == "__main__":
    main()
