import contextlib
import io
import itertools
import json
from pathlib import Path
import shutil
import subprocess
from unittest.mock import Mock, patch

from test_workflow import Fixture
from scaffold import WorkflowError, digest, read_json, restore_transaction, write_json
from runtime import parse_dev_result, stop_owned_game
from sessions import InstallationLease, Session, interactive_worker, session_options, submit_command, validate_command, verify_mod_absent
from ti import inspection_spec, parser


class OptionsTests(Fixture):
    def test_powershell_forwards_pipeline_json_as_utf8(self):
        root = Path(__file__).resolve().parents[1]
        shutil.copy2(root / "ti.ps1", self.root / "ti.ps1")
        (self.root / "tools/ti.py").write_text("import json,sys; print(json.dumps({'args':sys.argv[1:],'input':json.load(sys.stdin)}))", encoding="utf-8")
        value = {"text": "café", "nested": {"count": 2}}
        payload = json.dumps(value, ensure_ascii=False)
        script = self.root / "check.ps1"
        script.write_text("'" + payload + "' | & '" + str(self.root / "ti.ps1").replace("'", "''") + "' session command -File '-'", encoding="utf-8-sig")
        result = subprocess.run(["powershell", "-NoProfile", "-File", str(script)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"args": ["session", "command", "-File", "-"], "input": value})

    def test_powershell_preserves_json_argument_quotes_and_spaces(self):
        root = Path(__file__).resolve().parents[1]
        shutil.copy2(root / "ti.ps1", self.root / "ti.ps1")
        (self.root / "tools/ti.py").write_text("import json,sys; print(json.dumps(sys.argv[1:]))", encoding="utf-8")
        payload = json.dumps({"id": "quoted", "path": "C:/with spaces/a", "text": 'a "quote"'})
        script = self.root / "check.ps1"
        script.write_text("& '" + str(self.root / "ti.ps1").replace("'", "''") + "' session command -Json '" + payload.replace("'", "''") + "'", encoding="utf-8")
        result = subprocess.run(["powershell", "-NoProfile", "-File", str(script)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ["session", "command", "-Json", payload])
        result = subprocess.run(["powershell", "-NoProfile", "-File", str(self.root / "ti.ps1")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ["help"])

    def test_configuration_matrix_and_legacy_defaults(self):
        self.assertEqual(session_options({}), dict(configuration="Release", modTests=False, devTools=False, deployMod=True))
        self.assertEqual(session_options({"devTools": True}), dict(configuration="Debug", modTests=True, devTools=True, deployMod=True))
        for config, hooks, helper, deploy in itertools.product(("Debug", "Release"), (False, True), (False, True), (False, True)):
            value = dict(configuration=config, modTests=hooks, devTools=helper, deployMod=deploy)
            self.assertEqual(session_options(value), value)
        for value in ({"devTools": "false"}, {"modTests": 1}, {"deployMod": None}, {"configuration": "release"}):
            with self.assertRaises(WorkflowError):
                session_options(value)

    def test_cli_hook_override_is_independent(self):
        self.assertIsNone(parser().parse_args(["build"]).mod_tests)
        self.assertFalse(parser().parse_args(["deploy", "-DevTools", "-NoModTests"]).mod_tests)
        self.assertTrue(parser().parse_args(["build", "-ModTests"]).mod_tests)

    def test_build_passes_independent_test_compilation_and_records_it(self):
        project = self.initialize("Code")
        self.workspace.config_path.parent.mkdir(parents=True)
        self.workspace.config_path.touch()
        game = self.root / "game"
        def compile(args):
            configuration = args[args.index("-c") + 1]
            path = self.root / f"src/Mod/bin/{configuration}/net48/{project['id']}.dll"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(next(a for a in args if str(a).startswith("-p:EnableModTests=")))
        with patch.object(self.workspace, "game", return_value=game), patch("scaffold.loader_config"), \
             patch.object(self.workspace, "fingerprint", return_value={}), \
             patch.object(self.workspace, "dotnet", side_effect=compile), \
             patch.object(self.workspace, "build_devtools") as helper, contextlib.redirect_stdout(io.StringIO()):
            for configuration, hooks, dev in itertools.product(("Debug", "Release"), (False, True), (False, True)):
                helper.reset_mock()
                stage = self.workspace.build(configuration, dev, mod_tests=hooks)
                record = read_json(stage.parent / (project["id"] + ".build.json"))
                self.assertEqual(record["modTests"], hooks)
                self.assertEqual(record["devTools"], dev)
                self.assertEqual(helper.call_count, int(dev))
                self.assertEqual((stage / (project["id"] + ".dll")).read_text(), "-p:EnableModTests=" + str(hooks).lower())

    def test_package_rejects_test_enabled_build_record(self):
        project = self.initialize("Native")
        with contextlib.redirect_stdout(io.StringIO()):
            stage = self.workspace.build()
        path = stage.parent / (project["id"] + ".build.json")
        record = read_json(path)
        record["modTests"] = True
        write_json(path, record)
        with patch.object(self.workspace, "build", return_value=stage) as build:
            with self.assertRaises(WorkflowError):
                self.workspace.package()
        build.assert_called_once_with("Release", dev_tools=False, mod_tests=False)


class SessionTests(Fixture):
    def make_session(self):
        self.initialize("Code")
        evidence = self.root / ".local/runs/session"
        evidence.mkdir(parents=True)
        session = Session(self.workspace, evidence, {})
        session.client = Mock()
        return session

    def test_mutation_is_dispatched_once_and_duplicate_returns_result(self):
        session = self.make_session()
        session.client.call.return_value = {"count": 1}
        request = {"id": "purchase", "tool": "give_resources", "arguments": {"amount": 1}}
        first = session.execute(request)
        self.assertEqual(first, session.execute(request))
        session.client.call.assert_called_once()
        with self.assertRaises(WorkflowError):
            session.execute({**request, "arguments": {"amount": 2}})

    def test_uncertain_dispatch_is_never_replayed(self):
        session = self.make_session()
        request = {"id": "action", "tool": "give_resources", "arguments": {}}
        folder = session.evidence / "commands/action"
        write_json(folder / "request.json", request)
        write_json(folder / "started.json", {"time": 0})
        with self.assertRaisesRegex(WorkflowError, "uncertain"):
            session.execute(request)
        session.client.call.assert_not_called()

    def test_timeout_result_is_cached_without_second_mutation(self):
        session = self.make_session()
        session.client.call.side_effect = WorkflowError("timeout")
        request = {"id": "action", "tool": "give_resources"}
        self.assertFalse(session.execute(request)["ok"])
        self.assertFalse(session.execute(request)["ok"])
        session.client.call.assert_called_once()

    def test_polling_validation_happens_before_mutation(self):
        session = self.make_session()
        with self.assertRaisesRegex(WorkflowError, "read-only"):
            session.execute({"id": "action", "tool": "give_resources", "waitSeconds": 10})
        session.client.call.assert_not_called()
        session.client.call.side_effect = [{"campaign": False}, {"campaign": True}]
        with patch("sessions.time.sleep"):
            response = session.execute({"id": "ready", "tool": "observe", "waitSeconds": 10, "expect": {"/campaign": True}})
        self.assertTrue(response["ok"])
        self.assertEqual(session.client.call.call_count, 2)

    def test_import_is_scratch_only_and_never_overwrites(self):
        session = self.make_session()
        source = self.root / "previous/generated-saves/scratch-source.gz"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"fixture")
        saves = self.root / "saves"
        saves.mkdir()
        session.record = {"savesDir": str(saves)}
        args = {"source": str(source), "name": "scratch-input"}
        result = session.import_save(args)
        self.assertEqual(digest(result["destination"]), digest(source))
        with self.assertRaises(WorkflowError):
            session.import_save(args)
        with self.assertRaises(WorkflowError):
            session.import_save({**args, "name": "../overwrite"})
        self.assertEqual((saves / "scratch-input.gz").read_bytes(), b"fixture")

    def test_absence_removes_existing_mod_and_recovers_settings(self):
        project = self.initialize("Code")
        game = self.root / "game"
        target = game / "Mods/Enabled" / project["id"]
        target.mkdir(parents=True)
        (target / (project["id"] + ".dll")).write_bytes(b"installed")
        write_json(target / "ModInfo.json", {"Id": project["id"]})
        (target / "Settings.xml").write_bytes(b"user settings")
        (target / "empty-original").mkdir()
        other = target.parent / "Other.Mod"
        other.mkdir()
        (other / "Settings.xml").write_bytes(b"other settings")
        before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
        with patch.object(self.workspace, "game", return_value=game), patch("scaffold.require_game_closed"), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(WorkflowError):
                verify_mod_absent(self.workspace, project)
            journal = self.workspace.remove_mod(project["id"])
            self.assertFalse(target.exists(), "The native scanner lists even an empty enabled folder")
            self.assertTrue(verify_mod_absent(self.workspace, project)["dllAbsent"])
            restore_transaction(journal, game)
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)
        self.assertTrue((target / "empty-original").is_dir())
        self.assertEqual((other / "Settings.xml").read_bytes(), b"other settings")

    def test_duplicate_installation_refuses_absence(self):
        project = self.initialize("Code")
        game = self.root / "game"
        write_json(game / "Mods/Enabled/Renamed/ModInfo.json", {"Id": project["id"]})
        with patch.object(self.workspace, "game", return_value=game), self.assertRaises(WorkflowError):
            verify_mod_absent(self.workspace, project)

    def test_installation_lease_blocks_other_clone_and_abandoned_session(self):
        game = self.root / "game"
        evidence = self.root / ".local/runs/unfinished"
        write_json(evidence / "session.json", {"status": "running"})
        with patch.dict("os.environ", {"LOCALAPPDATA": str(self.root / "appdata")}), patch.object(self.workspace, "game", return_value=game):
            lease = InstallationLease(self.workspace)
            try:
                lease.remember(evidence)
                with self.assertRaisesRegex(WorkflowError, "active"):
                    InstallationLease(self.workspace)
            finally:
                lease.close()
            with self.assertRaisesRegex(WorkflowError, "Unfinished"):
                InstallationLease(self.workspace)
            recovery = InstallationLease(self.workspace, recovery=evidence)
            recovery.close()
            write_json(evidence / "session.json", {"status": "restored"})
            InstallationLease(self.workspace).close()

    def test_reused_pid_is_not_stopped(self):
        owner = dict(Id=123, Path="game.exe", StartTime="before")
        with patch("runtime.windows_processes", return_value=[{**owner, "StartTime": "later"}]), \
             patch("runtime.require_game_closed", side_effect=WorkflowError("unrelated game")), patch("runtime.run") as stop:
            with self.assertRaises(WorkflowError):
                stop_owned_game({"owner": owner})
        stop.assert_not_called()

    def test_second_worker_cannot_overwrite_existing_evidence(self):
        session = self.make_session()
        (session.evidence / "worker-claim").mkdir()
        write_json(session.evidence / "result.json", {"status": "running", "original": True})
        with self.assertRaisesRegex(WorkflowError, "already claimed"):
            interactive_worker(self.workspace, session.evidence)
        self.assertTrue(read_json(session.evidence / "result.json")["original"])

    def test_command_and_finish_fail_promptly_after_startup_failure(self):
        session = self.make_session()
        write_json(session.evidence / "options.json", {})
        write_json(session.evidence / "worker-ended.json", {"status": "failed"})
        for request in ({"id": "observe", "tool": "observe"}, {"id": "session_finish", "tool": "finish"}):
            with self.assertRaisesRegex(WorkflowError, "worker ended"):
                submit_command(self.workspace, session.evidence.name, request)


class DiagnosticsTests(Fixture):
    def test_valid_and_negative_results(self):
        for value in ({"ok": True, "result": {"passed": True}}, {"ok": False, "error": "expected"}):
            self.assertEqual(parse_dev_result({"output": ["TI_DEV_RESULT:" + json.dumps(value)]}), value)

    def test_absent_marker_is_distinct_from_malformed_json(self):
        with self.assertRaisesRegex(WorkflowError, "Absent TI_DEV_RESULT"):
            parse_dev_result({"output": ["unknown command"]})
        for value in ('{"ok":', '{bad}', '[]', '{"ok":true} trailing', '{"ok":1}'):
            with self.assertRaisesRegex(WorkflowError, "Malformed or incomplete"):
                parse_dev_result({"output": ['TI_DEV_RESULT:{"ok":true}', "TI_DEV_RESULT:" + value]})

    def test_pinned_server_truncation_is_not_success(self):
        # Exercise the pinned result formatter without running a server or a bridge.
        source = Path(__file__).resolve().parents[1] / "tools/TerraInvictaMCP/server/tools.py"
        text = source.read_text(encoding="utf-8")
        start, end = text.index("def tool_result("), text.index("# ---------------------------------------------------------------- schema DSL")
        scope = {"json": json}
        for line in text.splitlines():
            if line.startswith(("PRETTY_LIMIT =", "TEXT_LIMIT =")):
                exec(line, scope)
        exec(text[start:end], scope)
        limit = scope["TEXT_LIMIT"]
        result = scope["json_result"]({"output": ["TI_DEV_RESULT:" + json.dumps({"ok": True, "large": "x" * limit})]})
        raw = result["content"][0]["text"]
        self.assertIn(f"truncated at {limit} chars", raw)
        with self.assertRaisesRegex(WorkflowError, "Truncated ti_dev"):
            parse_dev_result(raw)

    def test_il_filename_and_invocation_describe_assembly_scope(self):
        name, args, scope = inspection_spec("Example.dll", "Example.First", True)
        self.assertEqual(name, "Example.assembly.il.txt")
        self.assertEqual(args, ["-il"])
        self.assertEqual(scope, "assembly-il")
        self.assertEqual(inspection_spec("Example.dll", None, True), (name, args, scope))
        self.assertEqual(inspection_spec("Example.dll", "Example.First")[1], ["-t", "Example.First"])
