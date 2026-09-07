"""MCP transport, evidence, and recoverable disposable-game sessions."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
import xml.etree.ElementTree as ET

from scaffold import (WorkflowError, contained, digest, read_json, require_game_closed,
                      restore_transaction, run, windows_processes, write_json)


class MCP:
    def __init__(self, workspace, evidence=None):
        self.workspace = workspace
        self.evidence = Path(evidence) if evidence else None
        server = workspace.game() / "Mods/Enabled/TerraInvictaMCP/server"
        if not (server / "__main__.py").is_file():
            raise WorkflowError("MCP is not deployed. Run setup first.")
        self.proc = subprocess.Popen([sys.executable, str(server)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True, encoding="utf-8", errors="replace", bufsize=1)
        self.messages = queue.Queue()
        self.stderr = []
        self.sequence = 0
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._errors, daemon=True).start()
        self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                               "clientInfo": {"name": "ti-mod-template", "version": "0.1.0"}})
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        self.proc.stdin.flush()

    def _read(self):
        try:
            for line in self.proc.stdout:
                try:
                    self.messages.put(json.loads(line))
                except ValueError:
                    self.messages.put(WorkflowError("MCP stdout was not JSON-RPC: " + line[:200]))
        finally:
            self.messages.put(WorkflowError("MCP server exited: " + "".join(self.stderr)[-1500:]))

    def _errors(self):
        for line in self.proc.stderr:
            self.stderr.append(line)

    def rpc(self, method, params, timeout=360):
        self.sequence += 1
        request_id = self.sequence
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": request_id,
                                         "method": method, "params": params}) + "\n")
        self.proc.stdin.flush()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                message = self.messages.get(timeout=min(5, max(0.01, deadline - time.monotonic())))
            except queue.Empty:
                continue
            if isinstance(message, Exception):
                raise message
            if message.get("method") == "notifications/progress":
                text = message.get("params", {}).get("message")
                if text:
                    print(text, flush=True)
            if message.get("id") == request_id:
                if "error" in message:
                    raise WorkflowError("MCP protocol error: " + json.dumps(message["error"]))
                return message.get("result", {})
        raise WorkflowError(f"MCP timed out on {method}; inspect logs before retrying a mutation.")

    def call(self, tool, arguments=None):
        result = self.rpc("tools/call", {"name": tool, "arguments": arguments or {},
                                       "_meta": {"progressToken": str(self.sequence + 1)}})
        texts = []
        for index, item in enumerate(result.get("content", [])):
            if item.get("type") == "text":
                texts.append(item["text"])
            elif item.get("type") == "image" and self.evidence:
                ext = ".png" if item.get("mimeType") == "image/png" else ".jpg"
                image = self.evidence / f"{self.sequence:03d}-{tool}-{index}{ext}"
                image.write_bytes(base64.b64decode(item["data"], validate=True))
                texts.append(json.dumps({"image": str(image)}))
        # Tool warnings can be separate text blocks; retain them alongside the data.
        parsed = []
        for text in texts:
            try:
                parsed.append(json.loads(text))
            except ValueError:
                parsed.append(text)
        data = parsed[0] if len(parsed) == 1 else {"blocks": parsed}
        if self.evidence:
            write_json(self.evidence / f"{self.sequence:03d}-{tool}.json",
                       {"tool": tool, "arguments": arguments or {}, "isError": bool(result.get("isError")), "data": data})
        if result.get("isError"):
            raise WorkflowError(f"MCP {tool} failed: {json.dumps(data, ensure_ascii=False)[:4000]}")
        return data

    def dev(self, request):
        payload = base64.b64encode(json.dumps(request).encode("utf-8")).decode("ascii")
        result = self.call("console", {"line": "ti_dev " + payload})
        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):
                for child in value.values():
                    yield from strings(child)
            elif isinstance(value, list):
                for child in value:
                    yield from strings(child)
        found = []
        for text in strings(result):
            for line in text.splitlines():
                if "TI_DEV_RESULT:" in line:
                    remainder = line.split("TI_DEV_RESULT:", 1)[1]
                    try:
                        found.append(json.JSONDecoder().raw_decode(remainder)[0])
                    except ValueError:
                        pass
        if not found:
            raise WorkflowError("No structured ti_dev result. Confirm DevTools is enabled and the console command registered.")
        # Negative tests intentionally inspect ok:false instead of treating transport success as feature success.
        return found[-1]

    def close(self):
        if self.proc.poll() is None:
            self.proc.stdin.close()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
        if self.evidence and self.stderr:
            (self.evidence / "mcp-stderr.log").write_text("".join(self.stderr), encoding="utf-8")


def json_pointer(value, pointer):
    if pointer == "":
        return value
    if not pointer.startswith("/"):
        raise WorkflowError("Use JSON Pointer assertions beginning with '/': " + pointer)
    for part in pointer[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        try:
            value = value[int(part)] if isinstance(value, list) else value[part]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise WorkflowError(f"Missing assertion/reference path {pointer}") from error
    return value


def expand(value, context):
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        expression = value[2:-1]
        name, _, path = expression.partition("/")
        if name not in context:
            raise WorkflowError("Unknown recipe variable: " + name)
        return json_pointer(context[name], "/" + path if path else "")
    if isinstance(value, dict):
        return {key: expand(child, context) for key, child in value.items()}
    if isinstance(value, list):
        return [expand(child, context) for child in value]
    return value


def assert_expected(result, expected):
    for pointer, wanted in expected.items():
        actual = json_pointer(result, pointer)
        if type(actual) is not type(wanted) or actual != wanted:
            raise WorkflowError(f"Assertion {pointer}: expected {wanted!r}, got {actual!r}")


def profile_root():
    return Path(os.environ.get("USERPROFILE", str(Path.home()))) / "AppData/LocalLow/Pavonis Interactive/TerraInvicta"


def saves_directory(workspace):
    log = profile_root() / "Player.log"
    if log.exists():
        matches = re.findall(r"Setting savedGamesPath:\s*(.+)", log.read_text(encoding="utf-8", errors="replace"))
        if matches:
            path = Path(matches[-1].strip())
            if path.is_dir():
                return path.resolve()
    # Ask the pinned MCP path resolver, which handles redirected Windows Documents.
    server = workspace.game() / "Mods/Enabled/TerraInvictaMCP/server"
    code = "import sys; sys.path.insert(0,sys.argv[1]); import bridge; print(bridge.SAVES_DIR)"
    result = run([sys.executable, "-c", code, server], capture=True)
    return Path(result.strip()).resolve()


def snapshot_session(workspace, evidence):
    require_game_closed()
    pending = [p for p in (workspace.local / "runs").glob("*/session.json")
               if read_json(p).get("status") != "restored"]
    if pending:
        raise WorkflowError("An unfinished runtime session needs recovery: ./ti.ps1 restore -Session " + pending[0].parent.name)
    game = workspace.game()
    save_dir = saves_directory(workspace)
    record = {"schemaVersion": 1, "status": "prepared", "gameDir": str(game),
              "savesDir": str(save_dir), "owner": None, "launchRequested": False, "files": [], "saveNames": []}
    roots = [("saves", save_dir), ("profile", profile_root())]
    for group, folder in roots:
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(folder)
            contained(folder, relative)
            if group == "profile" and (path.suffix.lower() in (".log", ".png", ".jpg") or "mcp-screenshots" in path.parts):
                continue
            backup = contained(evidence / "before" / group, relative)
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
            record["files"].append({"path": str(path), "backup": str(backup.relative_to(evidence)), "sha256": digest(path), "group": group})
            if group == "saves":
                record["saveNames"].append(relative.as_posix())
    params = game / "TerraInvicta_Data/Managed/UnityModManager/Params.xml"
    backup = evidence / "before/Params.xml"
    if params.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(params, backup)
        record["files"].append({"path": str(params), "backup": "before/Params.xml", "sha256": digest(params), "group": "umm"})
    else:
        record["missingParams"] = str(params)
    # Unity PlayerPrefs are registry-backed on Windows. Preserve the game's key,
    # since use-mods and menu preferences may change during a test.
    if os.name == "nt":
        export = subprocess.run(["reg.exe", "export", r"HKCU\Software\Pavonis Interactive\TerraInvicta",
                                 str(evidence / "before/playerprefs.reg"), "/y"], capture_output=True)
        record["playerPrefsExisted"] = export.returncode == 0
    write_json(evidence / "session.json", record)
    return record


def enable_test_mods(workspace, mod_ids):
    path = workspace.game() / "TerraInvicta_Data/Managed/UnityModManager/Params.xml"
    tree = ET.parse(path) if path.exists() else ET.ElementTree(ET.Element("Param"))
    root = tree.getroot()
    show = root.find("ShowOnStart")
    if show is None:
        show = ET.SubElement(root, "ShowOnStart")
    show.text = "0"
    mods = root.find("ModParams")
    if mods is None:
        mods = ET.SubElement(root, "ModParams")
    # Existing mods retain their enabled state; intentional compatibility/isolation
    # scenarios must declare their own policy instead of silently changing the set.
    for mod_id in mod_ids:
        found = next((m for m in mods.findall("Mod") if m.get("Id") == mod_id), None)
        if found is None:
            found = ET.SubElement(mods, "Mod", {"Id": mod_id})
        found.set("Enabled", "true")
    tree.write(path, encoding="utf-8", xml_declaration=True)
    profile = saves_directory(workspace) / "PlayerOptions.TIProfile"
    if not profile.exists():
        raise WorkflowError("Launch the game once to create PlayerOptions.TIProfile, then close it and retry the runtime test.")
    text = profile.read_text(encoding="utf-8-sig")
    if re.search(r"(?m)^LoadingFailureDueToMods:True\s*$", text):
        raise WorkflowError("The profile records a previous native-mod loading failure. Diagnose that failure before running a new recipe.")
    if not re.search(r"(?m)^UseMods:(True|False)\s*$", text):
        raise WorkflowError("Unrecognized UseMods profile format; inspect TIPlayerProfileManager for this game build.")
    profile.write_text(re.sub(r"(?m)^UseMods:(True|False)", "UseMods:True", text), encoding="utf-8")


def stop_owned_game(record):
    owner = record.get("owner")
    processes = windows_processes()
    if not owner:
        if processes:
            raise WorkflowError("No owned game PID was recorded. Close the game before restoring this session.")
        return
    same = [p for p in processes if p["Id"] == owner["Id"] and p.get("StartTime") == owner.get("StartTime")
            and p.get("Path") == owner.get("Path")]
    if same:
        run(["taskkill.exe", "/PID", str(owner["Id"]), "/T", "/F"], capture=True)
        deadline = time.monotonic() + 20
        while windows_processes() and time.monotonic() < deadline:
            time.sleep(1)
    require_game_closed()


def restore_session(workspace, evidence, stop=False):
    evidence = Path(evidence)
    record = read_json(evidence / "session.json")
    if record["status"] == "restored":
        return
    if stop:
        stop_owned_game(record)
    else:
        require_game_closed()
    if Path(record["gameDir"]).resolve() != workspace.game():
        raise WorkflowError("Runtime journal belongs to another game installation")
    saves = Path(record["savesDir"])
    for entry in record["files"]:
        backup = contained(evidence, entry["backup"])
        if not backup.is_file() or digest(backup) != entry["sha256"]:
            raise WorkflowError("Runtime backup missing or damaged: " + str(backup))
    if saves.exists():
        for path in saves.rglob("*"):
            if path.is_file() and path.relative_to(saves).as_posix() not in record["saveNames"]:
                relative = path.relative_to(saves)
                contained(saves, relative)
                archived = contained(evidence / "generated-saves", relative)
                archived.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, archived)
                path.unlink()
    for entry in record["files"]:
        backup = contained(evidence, entry["backup"])
        if not backup.is_file() or digest(backup) != entry["sha256"]:
            raise WorkflowError("Runtime backup missing or damaged: " + str(backup))
        destination = Path(entry["path"])
        allowed_root = saves if entry["group"] == "saves" else profile_root() if entry["group"] == "profile" else workspace.game() / "TerraInvicta_Data/Managed/UnityModManager"
        destination = contained(allowed_root, destination.relative_to(allowed_root))
        if not destination.is_file() or digest(destination) != entry["sha256"]:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, destination)
    if record.get("missingParams"):
        params = workspace.game() / "TerraInvicta_Data/Managed/UnityModManager/Params.xml"
        if params.exists():
            params.unlink()
    if os.name == "nt":
        # Delete just the game's PlayerPrefs key so newly created test values do not survive import.
        subprocess.run(["reg.exe", "delete", r"HKCU\Software\Pavonis Interactive\TerraInvicta", "/f"], capture_output=True)
        if record.get("playerPrefsExisted"):
            run(["reg.exe", "import", evidence / "before/playerprefs.reg"], capture=True)
    for path in reversed(record.get("deploymentJournals", [])):
        restore_transaction(contained(workspace.root, path), workspace.game(), remove_generated=True)
    record["status"] = "restored"
    write_json(evidence / "session.json", record)


def collect_logs(workspace, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    game = workspace.game()
    paths = [profile_root() / "Player.log", profile_root() / "Player-prev.log",
             game / "Logs/TerraInvicta.log", game / "TerraInvicta_Data/Managed/UnityModManager/Log.txt"]
    for path in paths:
        if path.is_file():
            shutil.copy2(path, destination / path.name)
    return destination


def run_recipe(workspace, recipe_path):
    recipe = read_json(recipe_path)
    if recipe.get("schemaVersion") != 1 or not isinstance(recipe.get("steps"), list):
        raise WorkflowError("Recipe requires schemaVersion:1 and steps array")
    ids = [step.get("id") for step in recipe["steps"]]
    if any(not isinstance(i, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", i) for i in ids) or len(ids) != len(set(ids)):
        raise WorkflowError("Recipe step IDs must be unique alphanumeric identifiers")
    require_game_closed()
    project = workspace.project()
    dev_tools = bool(recipe.get("devTools", False))
    evidence = workspace.local / "runs" / (time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    evidence.mkdir(parents=True)
    session = snapshot_session(workspace, evidence)
    write_json(evidence / "recipe.json", recipe)
    result = {"status": "running", "recipe": str(recipe_path), "steps": [],
              "fingerprint": workspace.fingerprint(workspace.game())}
    client = None
    watching = threading.Event()
    owner_lock = threading.Lock()
    def note_owner():
        while not watching.is_set():
            found = [p for p in windows_processes() if p.get("Path") and
                     Path(p["Path"]).resolve() == (workspace.game() / "TerraInvicta.exe").resolve()]
            if len(found) == 1:
                with owner_lock:
                    session["owner"] = found[0]
                    write_json(evidence / "session.json", session)
                return
            watching.wait(2)
    try:
        stage = workspace.build("Debug" if dev_tools else "Release", dev_tools)
        result["package"] = str(stage)
        result["packageFiles"] = {p.relative_to(stage).as_posix(): digest(p) for p in stage.rglob("*") if p.is_file()}
        session["deploymentJournals"] = []
        stages = [(stage, project["id"])]
        if dev_tools:
            stages.append((workspace.local / "staging/TiModTemplate.DevTools", "TiModTemplate.DevTools"))
        for folder, mod_id in stages:
            journal = workspace.deploy_folder(folder, mod_id)
            session["deploymentJournals"].append(str(journal.relative_to(workspace.root)))
            write_json(evidence / "session.json", session)
        enable_test_mods(workspace, ["TerraInvictaMCP", project["id"]] + (["TiModTemplate.DevTools"] if dev_tools else []))
        client = MCP(workspace, evidence)
        session["launchRequested"] = True
        session["status"] = "running"
        write_json(evidence / "session.json", session)
        observer = threading.Thread(target=note_owner, daemon=True)
        observer.start()
        print(f"Starting disposable runtime test; evidence: {evidence}", flush=True)
        client.call("game_start")
        context = {"mod": project["id"], "run": evidence.name}
        for step in recipe["steps"]:
            print("Test step: " + step["id"], flush=True)
            args = expand(step.get("arguments", {}), context)
            if step.get("tool") in ("game_start", "game_stop"):
                raise WorkflowError("Recipes do not own process lifecycle; use a separate recipe for restart tests.")
            deadline = time.monotonic() + min(300, max(1, step.get("waitSeconds", 1)))
            while True:
                data = client.dev(args) if step["tool"] == "dev" else client.call(step["tool"], args)
                try:
                    assert_expected(data, expand(step.get("expect", {}), context))
                    break
                except WorkflowError:
                    if time.monotonic() >= deadline:
                        raise
                    if step["tool"] not in ("observe", "query", "template", "localize") and not (step["tool"] == "dev" and args.get("op") in ("status", "inspect")):
                        raise WorkflowError("Polling may only repeat read-only observation steps; mutations are never retried automatically.")
                    time.sleep(2)
            context[step["id"]] = data
            result["steps"].append({"id": step["id"], "status": "passed", "data": data})
            write_json(evidence / "result.json", result)
        result["status"] = "passed"
    except Exception as error:
        result["status"] = "failed"
        result["error"] = str(error)
        raise
    finally:
        watching.set()
        if "observer" in locals():
            observer.join(timeout=10)
        if client:
            client.close()
        try:
            collect_logs(workspace, evidence / "logs")
            restore_session(workspace, evidence, stop=True)
        except Exception as error:
            result["recoveryError"] = str(error)
            result["status"] = "failed"
            print("Recovery required: " + str(error), flush=True)
        write_json(evidence / "result.json", result)
    if result["status"] != "passed":
        raise WorkflowError("Test recovery failed; inspect " + str(evidence / "result.json"))
    print(f"Runtime test passed; saves and settings restored. Evidence: {evidence}")
    return evidence
