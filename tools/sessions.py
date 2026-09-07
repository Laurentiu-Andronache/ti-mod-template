"""One owned runtime lifecycle for recipes and durable interactive commands."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid

from scaffold import WorkflowError, contained, digest, read_json, require_game_closed, windows_processes, write_json
from runtime import MCP, assert_expected, expand, snapshot_session, enable_test_mods, finish_session


def session_options(value):
    if not isinstance(value, dict) or value.get("schemaVersion", 1) != 1:
        raise WorkflowError("Session options require a schemaVersion:1 object")
    helper = value.get("devTools", False)
    options = dict(configuration=value.get("configuration", "Debug" if helper else "Release"),
                   modTests=value.get("modTests", helper), devTools=helper,
                   deployMod=value.get("deployMod", True))
    if options["configuration"] not in ("Debug", "Release"):
        raise WorkflowError("configuration must be Debug or Release")
    for key in ("modTests", "devTools", "deployMod"):
        if type(options[key]) is not bool:
            raise WorkflowError(key + " must be a boolean")
    return options


class InstallationLease:
    """OS lock serializes clones; durable pointer blocks abandoned sessions."""
    def __init__(self, workspace, recovery=None):
        key = hashlib.sha256(str(workspace.game()).casefold().encode()).hexdigest()
        base = Path(os.environ.get("LOCALAPPDATA", str(workspace.local))) / "TiModTemplate/sessions"
        base.mkdir(parents=True, exist_ok=True)
        self.pointer = base / (key + ".json")
        self.file = (base / (key + ".lock")).open("a+b")
        self.locked = False
        try:
            import msvcrt
            self.file.seek(0, 2)
            if self.file.tell() == 0:
                self.file.write(b"0")
                self.file.flush()
            self.file.seek(0)
            try:
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise WorkflowError("Another runtime session is active for this installation; finish its owning session first. " + str(self.pointer)) from error
            self.locked = True
            if self.pointer.exists():
                previous = Path(read_json(self.pointer)["journal"])
                if not previous.is_file():
                    raise WorkflowError("Missing runtime journal referenced by " + str(self.pointer))
                if read_json(previous).get("status") != "restored" and previous.parent != recovery:
                    raise WorkflowError("Unfinished session: " + str(previous) + "; recover it from its owning clone with restore -Session " + previous.parent.name)
        except BaseException:
            self.close()
            raise

    def remember(self, evidence):
        write_json(self.pointer, {"journal": str(evidence / "session.json")})

    def close(self):
        if self.locked:
            import msvcrt
            self.file.seek(0)
            msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            self.locked = False
        self.file.close()


def evidence_folder(workspace):
    folder = workspace.local / "runs" / (time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True)
    return folder


def verify_mod_absent(workspace, project):
    mods = workspace.game() / "Mods/Enabled"
    hits = []
    for path in mods.rglob("*"):
        if not path.is_file():
            continue
        if path.name.casefold() == (project["id"] + ".dll").casefold():
            hits.append(str(path))
        if path.name == "ModInfo.json":
            info = read_json(path)
            if project["id"] in (info.get("Id"), info.get("Title")) or info.get("AssemblyName") == project["id"] + ".dll":
                hits.append(str(path))
    if hits:
        raise WorkflowError("Project mod is still installed; absence test refused: " + ", ".join(hits))
    return {"dllAbsent": True, "metadataAbsent": True, "mod": project["id"]}


class Session:
    def __init__(self, workspace, evidence, options):
        self.workspace, self.evidence, self.options = workspace, evidence, session_options(options)
        self.project = workspace.project()
        self.client = None
        self.record = None
        self.result = {"status": "running", "options": self.options, "steps": []}
        self.context = {"mod": self.project["id"], "run": evidence.name}
        self.watching = threading.Event()
        self.observer = None
        self.record_lock = threading.Lock()

    def remember(self, journal):
        self.record["deploymentJournals"].append(str(journal.relative_to(self.workspace.root)))
        write_json(self.evidence / "session.json", self.record)

    def start(self):
        w, options = self.workspace, self.options
        self.result["fingerprint"] = w.fingerprint(w.game())
        self.record["deploymentJournals"] = []
        stages = []
        if options["deployMod"]:
            stage = w.build(options["configuration"], False, mod_tests=options["modTests"])
            stages.append((stage, self.project["id"]))
            self.result["package"] = str(stage)
            self.result["packageFiles"] = {p.relative_to(stage).as_posix(): digest(p) for p in stage.rglob("*") if p.is_file()}
        else:
            w.remove_mod(self.project["id"], on_prepared=self.remember)
            self.result["modAbsence"] = verify_mod_absent(w, self.project)
        if options["devTools"]:
            stages.append((w.build_devtools(), "TiModTemplate.DevTools"))
        for folder, mod_id in stages:
            w.deploy_folder(folder, mod_id, on_prepared=self.remember)
        self.result["deployedFiles"] = {
            mod_id: {p.relative_to(folder).as_posix(): digest(w.game() / "Mods/Enabled" / mod_id / p.relative_to(folder))
                     for p in folder.rglob("*") if p.is_file()}
            for folder, mod_id in stages}
        enable_test_mods(w, ["TerraInvictaMCP"] + [mod_id for _, mod_id in stages])
        write_json(self.evidence / "result.json", self.result)
        self.client = MCP(w, self.evidence)
        self.result["initialObservation"] = self.client.call("observe")
        self.record.update(launchRequested=True, status="running")
        write_json(self.evidence / "session.json", self.record)

        def note_owner():
            try:
                while not self.watching.is_set():
                    found = [p for p in windows_processes() if p.get("Path") and
                             Path(p["Path"]).resolve() == (w.game() / "TerraInvicta.exe").resolve()]
                    if len(found) == 1:
                        with self.record_lock:
                            self.record["owner"] = found[0]
                            write_json(self.evidence / "session.json", self.record)
                        return
                    self.watching.wait(1)
            except BaseException as error:
                self.result["ownershipError"] = str(error)

        self.observer = threading.Thread(target=note_owner, daemon=True)
        self.observer.start()
        self.client.call("game_start")
        self.observer.join(timeout=5)
        if not self.record.get("owner"):
            raise WorkflowError("Game launched but ownership could not be recorded; " + self.result.get("ownershipError", "inspect session journal"))
        self.result["readyObservation"] = self.client.call("observe")
        if not options["deployMod"]:
            self.result["modAbsence"] = verify_mod_absent(w, self.project)
            self.result["runtimeMods"] = self.client.call("raw", {"cmd": "mods.list", "args": {}})
            if self.project["id"] in json.dumps(self.result["runtimeMods"]):
                raise WorkflowError("Runtime reports project mod in absence session")
        write_json(self.evidence / "ready.json", {"session": self.evidence.name, "status": "ready"})

    def import_save(self, args):
        source = Path(args["source"]).resolve()
        name = args["name"]
        if not isinstance(name, str) or not re.fullmatch(r"scratch-[A-Za-z0-9_-]+", name):
            raise WorkflowError("Imported save name must be scratch- followed by letters, digits, underscores or hyphens")
        if source.suffix not in (".gz", ".json") or not source.is_file() or "generated-saves" not in source.parts:
            raise WorkflowError("Import source must be an archived generated-saves .gz or .json fixture")
        destination = contained(Path(self.record["savesDir"]), name + source.suffix)
        if destination.exists():
            raise WorkflowError("Refusing to overwrite existing save: " + str(destination))
        record = dict(source=str(source), destination=str(destination), sha256=digest(source))
        write_json(self.evidence / "imports" / (name + ".json"), record)
        temporary = destination.with_name(destination.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            shutil.copy2(source, temporary)
            if digest(temporary) != record["sha256"]:
                raise WorkflowError("Fixture changed during import")
            # Windows rename refuses an existing destination, including a racing writer.
            temporary.rename(destination)
        finally:
            temporary.unlink(missing_ok=True)
        return record

    def execute(self, request):
        request = expand(request, self.context)
        validate_command(request)
        command_id = request["id"]
        folder = contained(self.evidence / "commands", command_id)
        folder.mkdir(parents=True, exist_ok=True)
        saved = folder / "request.json"
        if saved.exists() and read_json(saved) != request:
            raise WorkflowError("Command ID already belongs to a different request: " + command_id)
        if (folder / "response.json").exists():
            return read_json(folder / "response.json")
        if (folder / "started.json").exists():
            raise WorkflowError("Command outcome is uncertain; refusing replay: " + command_id)
        write_json(saved, request)
        write_json(folder / "started.json", {"time": time.time()})
        try:
            tool, args = request["tool"], request.get("arguments", {})
            deadline = time.monotonic() + request.get("waitSeconds", 1)
            while True:
                data = self.import_save(args) if tool == "import_save" else self.client.dev(args) if tool == "dev" else self.client.call(tool, args)
                try:
                    assert_expected(data, request.get("expect", {}))
                    break
                except WorkflowError:
                    if time.monotonic() >= deadline or request.get("waitSeconds", 1) <= 1:
                        raise
                    time.sleep(2)
            response = {"id": command_id, "ok": True, "data": data}
            self.context[command_id] = data
        except Exception as error:
            response = {"id": command_id, "ok": False, "error": str(error),
                        "outcome": "failed-or-uncertain", "retryMutation": False}
            self.result["status"] = "failed"
        write_json(folder / "response.json", response)
        self.result["steps"].append(response)
        write_json(self.evidence / "result.json", self.result)
        return response


def validate_command(request):
    if not isinstance(request, dict) or not isinstance(request.get("id"), str) or not re.fullmatch(r"[A-Za-z0-9_-]+", request["id"]):
        raise WorkflowError("Command requires a unique id of letters, digits, underscores or hyphens")
    tool, args = request.get("tool"), request.get("arguments", {})
    if not isinstance(tool, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", tool) or not isinstance(args, dict):
        raise WorkflowError("Command requires a tool name and object arguments")
    if tool in ("game_start", "game_stop", "finish"):
        raise WorkflowError("Use session start/finish for process lifecycle")
    wait = request.get("waitSeconds", 1)
    if type(wait) not in (int, float) or not 1 <= wait <= 300:
        raise WorkflowError("waitSeconds must be between 1 and 300")
    if not isinstance(request.get("expect", {}), dict):
        raise WorkflowError("expect must be a JSON Pointer mapping")
    if wait > 1 and tool not in ("observe", "query", "template", "localize") and not (tool == "dev" and args.get("op") in ("status", "inspect")):
        raise WorkflowError("Polling may only repeat read-only observations; mutations are issued once")


def run_session(workspace, options, body, evidence=None):
    evidence = evidence or evidence_folder(workspace)
    session = Session(workspace, evidence, options)
    lease = InstallationLease(workspace)
    try:
        session.record = snapshot_session(workspace, evidence)
        try:
            lease.remember(evidence)
            session.start()
            body(session)
            health = session.client.call("observe")
            assert_expected(health, {"/bridge": "up", "/version/crashed": False})
            session.result["finalHealth"] = health
            if session.result["status"] != "failed":
                session.result["status"] = "passed"
        except BaseException as error:
            session.result.update(status="failed", error=str(error), errorType=type(error).__name__)
        finally:
            try:
                session.watching.set()
                if session.observer:
                    session.observer.join(timeout=10)
            finally:
                finish_session(workspace, evidence, session.result, session.client)
    finally:
        lease.close()
    return evidence, session.result


def start_interactive(workspace, options):
    session_options(options)
    workspace.project()
    require_game_closed()
    # Check before launching a worker, which takes its own lease for its lifetime.
    lease = InstallationLease(workspace)
    lease.close()
    evidence = evidence_folder(workspace)
    write_json(evidence / "options.json", options)
    with (evidence / "worker.log").open("w", encoding="utf-8") as log:
        worker = subprocess.Popen([sys.executable, str(workspace.root / "tools/ti.py"),
                                   "session", "worker", "-Session", evidence.name],
                                  cwd=workspace.root, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
    write_json(evidence / "worker.json", {"pid": worker.pid})
    return {"session": evidence.name, "evidence": str(evidence), "status": "starting", "workerPid": worker.pid}


def interactive_worker(workspace, evidence):
    try:
        (evidence / "worker-claim").mkdir()
    except FileExistsError as error:
        raise WorkflowError("This session worker was already claimed. Do not resume commands; use restore -Session and start a new session.") from error
    finish_folder = None
    def commands(session):
        nonlocal finish_folder
        deadline = time.monotonic() + 7200
        while time.monotonic() < deadline:
            for path in sorted((evidence / "queue").glob("*/request.json"), key=lambda p: p.stat().st_mtime_ns):
                folder = path.parent
                if (folder / "response.json").exists():
                    continue
                request = read_json(path)
                if request.get("tool") == "finish":
                    finish_folder = folder
                    return
                try:
                    response = session.execute(request)
                except Exception as error:
                    response = {"ok": False, "id": request.get("id"), "error": str(error)}
                    session.result["status"] = "failed"
                write_json(folder / "response.json", response)
            time.sleep(0.2)
        raise WorkflowError("Interactive session exceeded two hours; finishing through recovery")
    try:
        _, result = run_session(workspace, read_json(evidence / "options.json"), commands, evidence)
    except BaseException as error:
        result = {"status": "failed", "error": str(error)}
        write_json(evidence / "result.json", result)
    if finish_folder:
        write_json(finish_folder / "response.json", {"ok": result["status"] == "passed", "data": result})
    write_json(evidence / "worker-ended.json", {"status": result["status"]})
    return result


def submit_command(workspace, session_id, request, timeout=360):
    evidence = contained(workspace.local / "runs", session_id)
    if not (evidence / "options.json").is_file():
        raise WorkflowError("Not an interactive session: " + session_id)
    request = dict(request)
    request.setdefault("id", "cmd_" + uuid.uuid4().hex)
    if request.get("tool") != "finish":
        validate_command(request)
    folder = contained(evidence / "queue", request["id"])
    path = folder / "request.json"
    try:
        folder.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        if not path.exists() or read_json(path) != request:
            raise WorkflowError("Command ID already reserved for another or incomplete request: " + request["id"])
    else:
        write_json(path, request)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = folder / "response.json"
        if response.exists():
            return read_json(response)
        if (evidence / "worker-ended.json").exists():
            raise WorkflowError("Session worker ended before command completion; inspect " + str(evidence / "result.json"))
        if (evidence / "session.json").exists() and read_json(evidence / "session.json")["status"] == "restored":
            # Finish response is written immediately after recovery; allow that write.
            if request.get("tool") != "finish":
                raise WorkflowError("Session ended before command completion; inspect " + str(evidence))
        time.sleep(0.2)
    raise WorkflowError("Command pending or outcome uncertain. Do not resend a mutation with a new ID. Inspect " + str(folder))
