import contextlib
import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from test_workflow import Fixture
from scaffold import digest, read_json, write_json
from runtime import finish_session


class CleanupTests(Fixture):
    def session(self):
        source = self.root / "stage"
        source.mkdir()
        (source / "mod.dll").write_bytes(b"test")
        game = self.root / "game"
        target = game / "Mods/Enabled/Tests.Example"
        target.mkdir(parents=True)
        (target / "mod.dll").write_bytes(b"original")
        (target / "Settings.xml").write_bytes(b"unowned settings")
        journal = self.deployment(source, target)
        evidence = self.root / ".local/runs/test"
        evidence.mkdir(parents=True)
        saves, profile = self.root / "saves", self.root / "profile"
        files = []
        for group, path in [("saves", saves / "original.gz"), ("profile", profile / "prefs"),
                            ("umm", game / "TerraInvicta_Data/Managed/UnityModManager/Params.xml")]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"original " + group.encode())
            backup = evidence / "before" / group
            backup.parent.mkdir(exist_ok=True)
            backup.write_bytes(path.read_bytes())
            files.append(dict(path=str(path), backup=str(backup.relative_to(evidence)),
                              sha256=digest(path), group=group))
            path.write_bytes(b"test changed")
        (saves / "scratch-new.gz").write_bytes(b"new save")
        owner = dict(Id=123, Path=str(game / "TerraInvicta.exe"), StartTime="owned start")
        write_json(evidence / "session.json", dict(status="running", gameDir=str(game),
                   savesDir=str(saves), owner=owner, files=files, saveNames=["original.gz"],
                   deploymentJournals=[str(journal.relative_to(self.root))]))
        return evidence, game, profile, owner, files

    def test_log_copy_failure_still_stops_and_restores_everything(self):
        evidence, game, profile, owner, files = self.session()
        result = {"status": "passed"}
        client = Mock()
        with patch.object(self.workspace, "game", return_value=game), \
             patch("runtime.profile_root", return_value=profile), \
             patch("runtime.windows_processes", side_effect=[[owner], []]), \
             patch("runtime.require_game_closed"), patch("runtime.run") as stop, \
             patch("runtime.subprocess.run"), \
             patch("runtime.collect_logs", side_effect=OSError("log copy failed")), \
             contextlib.redirect_stderr(io.StringIO()):
            finish_session(self.workspace, evidence, result, client)
        client.close.assert_called_once()
        stop.assert_called_once()
        self.assertIn("123", stop.call_args.args[0])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["recoveryStatus"], "restored")
        for entry in files:
            self.assertEqual(digest(entry["path"]), entry["sha256"])
        self.assertEqual((game / "Mods/Enabled/Tests.Example/mod.dll").read_bytes(), b"original")
        self.assertEqual((game / "Mods/Enabled/Tests.Example/Settings.xml").read_bytes(), b"unowned settings")
        self.assertEqual((evidence / "generated-saves/scratch-new.gz").read_bytes(), b"new save")
        self.assertEqual(read_json(evidence / "session.json")["status"], "restored")

    def test_original_and_all_cleanup_errors_survive(self):
        evidence = self.root / "evidence"
        client = Mock()
        client.close.side_effect = OSError("shutdown")
        result = {"status": "failed", "error": "original test error"}
        with patch("runtime.collect_logs", side_effect=OSError("logs")), \
             patch("runtime.restore_session", side_effect=OSError("restore")) as restore, \
             contextlib.redirect_stderr(io.StringIO()):
            finish_session(self.workspace, evidence, result, client)
        restore.assert_called_once_with(self.workspace, evidence, stop=True)
        saved = read_json(evidence / "result.json")
        self.assertEqual(saved["error"], "original test error")
        self.assertEqual([e["phase"] for e in saved["cleanupErrors"]],
                         ["mcpShutdown", "logCollection", "restoration"])
        self.assertIn(evidence.name, saved["recoveryCommand"])

    def test_evidence_failure_does_not_prevent_restoration(self):
        with patch("runtime.collect_logs"), patch("runtime.restore_session") as restore, \
             patch("runtime.write_json", side_effect=OSError("disk full")), \
             contextlib.redirect_stderr(io.StringIO()):
            result = finish_session(self.workspace, self.root, {"status": "passed"})
        restore.assert_called_once()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["recoveryStatus"], "restored")

    def test_log_failure_and_external_deployment_edit_preserve_edit(self):
        evidence, game, profile, owner, files = self.session()
        external = game / "Mods/Enabled/Tests.Example/mod.dll"
        external.write_bytes(b"external edit")
        with patch.object(self.workspace, "game", return_value=game), \
             patch("runtime.profile_root", return_value=profile), \
             patch("runtime.stop_owned_game"), patch("runtime.subprocess.run"), \
             patch("runtime.collect_logs", side_effect=OSError("logs")), \
             contextlib.redirect_stderr(io.StringIO()):
            result = finish_session(self.workspace, evidence, {"status": "passed"})
        self.assertEqual(external.read_bytes(), b"external edit")
        self.assertEqual(result["recoveryStatus"], "required")
        for entry in files:
            self.assertEqual(digest(entry["path"]), entry["sha256"])
