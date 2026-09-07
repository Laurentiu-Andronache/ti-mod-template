import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from scaffold import (Workspace, WorkflowError, contained, deploy_transaction, digest,
                      discover_game, extract_zip, loader_config, read_json, restore_transaction, write_json)
from runtime import assert_expected, expand, json_pointer


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="TI scaffold test ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "tools").mkdir()
        shutil.copy2(ROOT / "tools/dependencies.lock.json", self.root / "tools/dependencies.lock.json")
        shutil.copytree(ROOT / "templates", self.root / "templates")
        self.workspace = Workspace(self.root)

    def initialize(self, kind="Hybrid"):
        with contextlib.redirect_stdout(io.StringIO()):
            self.workspace.initialize("Tests.Example", "Example", kind, "Tests")
        return self.workspace.project()

    def deployment(self, source, target):
        with contextlib.redirect_stdout(io.StringIO()):
            return deploy_transaction(self.root, source, target)


class ProjectTests(Fixture):
    def test_initialization_is_single_mod_and_consistent(self):
        project = self.initialize()
        self.assertIn("namespace Tests.Example", (self.root / "src/Mod/Main.cs").read_text())
        manifest = self.workspace.manifest(project)
        self.assertEqual(manifest["Title"], manifest["Id"])
        self.assertEqual(manifest["EntryMethod"], "Tests.Example.Main.Load")
        with self.assertRaises(WorkflowError):
            self.workspace.initialize("Tests.Other", None, "Code", "Tests")

    def test_invalid_identity_creates_nothing(self):
        for identity in ("../bad", "Single", "A.B/C", "A.B:C", "A.1Bad"):
            with self.assertRaises(WorkflowError):
                self.workspace.initialize(identity, None, "Native", "Tests")
        self.assertFalse((self.root / "mod.project.json").exists())

    def test_native_build_without_game_and_zip_allowlist(self):
        project = self.initialize("Native")
        write_json(self.root / "content/TITechTemplate.json", [{"dataName": "AdAstra", "researchCost": 2500}])
        with contextlib.redirect_stdout(io.StringIO()):
            package = self.workspace.package()
        with zipfile.ZipFile(package) as archive:
            self.assertEqual(set(archive.namelist()), {"Tests.Example/ModInfo.json", "Tests.Example/TITechTemplate.json"})
            self.assertNotIn("Id", json.loads(archive.read("Tests.Example/ModInfo.json")))

    def test_stale_staging_files_do_not_enter_package(self):
        self.initialize("Native")
        with contextlib.redirect_stdout(io.StringIO()):
            stage = self.workspace.build()
            (stage / "obsolete.dll").write_bytes(b"old")
            package = self.workspace.package()
        with zipfile.ZipFile(package) as archive:
            self.assertNotIn("Tests.Example/obsolete.dll", archive.namelist())

    def test_json_duplicates_and_unknown_metadata_fail(self):
        project = self.initialize("Native")
        path = self.root / "content/TITechTemplate.json"
        path.write_text('[{"dataName":"A","dataName":"B"}]')
        with self.assertRaises(ValueError):
            self.workspace.validate_content(project)
        path.unlink()
        write_json(self.root / "content/ModFile.json", {"Id": "Tests.Example"})
        with self.assertRaises(WorkflowError):
            self.workspace.validate_content(project)

    def test_assets_require_explicit_allowlist(self):
        project = self.initialize("Native")
        asset = self.root / "content/icons"
        asset.write_bytes(b"authored bundle")
        with self.assertRaises(WorkflowError):
            self.workspace.validate_content(project)
        project["packageFiles"] = ["icons"]
        self.assertEqual(self.workspace.validate_content(project), [asset])
        (self.root / "content/game.dll").write_bytes(b"not a mod asset")
        project["packageFiles"].append("game.dll")
        with self.assertRaises(WorkflowError):
            self.workspace.validate_content(project)

    def test_array_and_metadata_validation(self):
        project = self.initialize("Native")
        write_json(self.root / "content/TITechTemplate.json", [{"dataName": "A"}, {"dataName": "A"}])
        with self.assertRaises(WorkflowError):
            self.workspace.validate_content(project)
        project["native"]["TemplatesToReplaceArrays"] = "TITechTemplate.json"
        with self.assertRaises(WorkflowError):
            self.workspace.manifest(project)

    def test_discovery_requires_assembly_and_metadata_is_not_assumed(self):
        game = self.root / "Game with spaces"
        managed = game / "TerraInvicta_Data/Managed"
        managed.mkdir(parents=True)
        with self.assertRaises(WorkflowError):
            discover_game(game)
        (managed / "Assembly-CSharp.dll").touch()
        self.assertEqual(discover_game(game), game.resolve())
        umm = managed / "UnityModManager"
        umm.mkdir()
        (umm / "UnityModManager.dll").touch()
        (umm / "0Harmony.dll").touch()
        config = umm / "Config.xml"
        config.write_text('<Config><ModsDirectory>Mods/Enabled</ModsDirectory><ModInfo>ModFile.json</ModInfo></Config>')
        before = config.read_bytes()
        with self.assertRaises(WorkflowError):
            loader_config(game)
        self.assertEqual(before, config.read_bytes())
        config.write_text(config.read_text().replace("ModFile.json", "ModInfo.json"))
        self.assertEqual(loader_config(game), umm)


class DeploymentTests(Fixture):
    def paths(self):
        source = self.root / "stage"
        target = self.root / "game/Mods/Enabled/Tests.Example"
        source.mkdir()
        target.mkdir(parents=True)
        return source, target

    def test_upgrade_removes_stale_owned_files_and_restore_preserves_settings(self):
        source, target = self.paths()
        (target / "original.dll").write_bytes(b"original")
        (target / "Settings.xml").write_text("user settings")
        (source / "original.dll").write_bytes(b"v1")
        (source / "obsolete.asset").write_bytes(b"old")
        first = self.deployment(source, target)
        (source / "original.dll").write_bytes(b"v2")
        (source / "obsolete.asset").unlink()
        second = self.deployment(source, target)
        self.assertFalse((target / "obsolete.asset").exists())
        self.assertEqual((target / "Settings.xml").read_text(), "user settings")
        restore_transaction(second, self.root / "game")
        self.assertEqual((target / "original.dll").read_bytes(), b"v1")
        restore_transaction(first, self.root / "game")
        self.assertEqual((target / "original.dll").read_bytes(), b"original")
        self.assertFalse((target / "obsolete.asset").exists())
        restore_transaction(first, self.root / "game")  # repeated recovery is harmless

    def test_external_changes_are_not_overwritten(self):
        source, target = self.paths()
        (source / "mod.dll").write_bytes(b"v1")
        journal = self.deployment(source, target)
        (target / "mod.dll").write_bytes(b"user updated it")
        with self.assertRaises(WorkflowError):
            self.deployment(source, target)
        with self.assertRaises(WorkflowError):
            restore_transaction(journal, self.root / "game")
        self.assertEqual((target / "mod.dll").read_bytes(), b"user updated it")

    def test_interruption_can_be_recovered(self):
        source, target = self.paths()
        (source / "a.dll").write_bytes(b"new")
        (target / "a.dll").write_bytes(b"before")
        original_copy = shutil.copy2
        def fail_install(src, dst, *args, **kwargs):
            if Path(src) == source / "a.dll":
                raise OSError("simulated interrupted copy")
            return original_copy(src, dst, *args, **kwargs)
        with patch("scaffold.shutil.copy2", side_effect=fail_install), self.assertRaises(OSError):
            self.deployment(source, target)
        with self.assertRaises(WorkflowError):
            self.deployment(source, target)
        journal = next((self.root / ".local/deployments").glob("*/manifest.json"))
        restore_transaction(journal, self.root / "game")
        self.assertEqual((target / "a.dll").read_bytes(), b"before")

    def test_partial_write_recovery(self):
        source, target = self.paths()
        (source / "a.dll").write_bytes(b"new")
        journal = self.deployment(source, target)
        data = read_json(journal)
        data["status"] = "installing"
        write_json(journal, data)
        restore_transaction(journal, self.root / "game")
        self.assertFalse((target / "a.dll").exists())

    def test_damaged_backup_is_detected_before_restore(self):
        source, target = self.paths()
        (source / "a.dll").write_bytes(b"new")
        (target / "a.dll").write_bytes(b"old")
        journal = self.deployment(source, target)
        (journal.parent / "before/a.dll").write_bytes(b"damaged")
        with self.assertRaises(WorkflowError):
            restore_transaction(journal, self.root / "game")
        self.assertEqual((target / "a.dll").read_bytes(), b"new")


class PathAndRecipeTests(Fixture):
    def test_traversal_and_archive_escape(self):
        for relative in ("../escape", "C:/elsewhere", "file:stream"):
            with self.assertRaises(WorkflowError):
                contained(self.root, relative)
        archive = self.root / "bad.zip"
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("../escape", "no")
        with self.assertRaises(WorkflowError):
            extract_zip(archive, self.root / "unpacked")
        self.assertFalse((self.root / "escape").exists())

    def test_recipe_references_assertions_and_type_strictness(self):
        context = {"mod": "Tests.Example", "created": {"button": {"handle": "abc"}}}
        self.assertEqual(expand({"mod": "${mod}", "handle": "${created/button/handle}"}, context),
                         {"mod": "Tests.Example", "handle": "abc"})
        self.assertEqual(json_pointer({"a/b": [1, 2]}, "/a~1b/1"), 2)
        assert_expected({"passed": True}, {"/passed": True})
        with self.assertRaises(WorkflowError):
            assert_expected({"passed": 1}, {"/passed": True})
        with self.assertRaises(WorkflowError):
            expand("${missing/result}", context)


if __name__ == "__main__":
    unittest.main()
