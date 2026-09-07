"""Opt-in installed-tool check: two-type IL output scope."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from scaffold import Workspace, digest, write_json
from ti import inspection_spec


def main():
    workspace = Workspace(ROOT)
    folder = workspace.local / "inspection-fixture"
    folder.mkdir(parents=True, exist_ok=True)
    dll = folder / "InspectionFixture.dll"
    workspace.compile_game_sources([ROOT / "tests/fixtures/InspectionFixture.cs"], dll, ["mscorlib.dll"])
    prefix = ["tool", "run", "ilspycmd", "--disable-updatecheck"]
    previous = workspace.dotnet(prefix + ["-t", "InspectionFixture.First", "-il", dll], capture=True)
    name, options, scope = inspection_spec(dll.name, "InspectionFixture.First", True)
    current = workspace.dotnet(prefix + options + [dll], capture=True)
    assert previous == current
    assert "InspectionFixture.First" in current and "InspectionFixture.Second" in current
    (folder / name).write_text(current, encoding="utf-8")
    write_json(folder / "result.json", {"status": "passed", "scope": scope,
               "requestedType": "InspectionFixture.First", "output": name,
               "sha256": digest(dll), "pinnedTypePlusIlMatchesAssemblyIl": True})
    print("Inspection fixture passed: " + str(folder / "result.json"))


if __name__ == "__main__":
    main()
