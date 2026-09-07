"""Portable checks for the scaffold and authored mod; no game process or bridge."""
from pathlib import Path
import importlib.util
import subprocess

from scaffold import Workspace, WorkflowError, read_json


def validate_repository(root):
    root = Path(root)
    handbook_validator = root / "references/ti-mods/scripts/validate.py"
    if not handbook_validator.exists():
        raise WorkflowError("Initialize required submodules before repository validation")
    spec = importlib.util.spec_from_file_location("handbook_validation", handbook_validator)
    handbook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(handbook)
    errors = []
    folders = [root / name for name in ("docs", "tools/DevTools", "tests/recipes", "templates", ".config")]
    files = [p for p in root.iterdir() if p.is_file()]
    for folder in folders:
        files += [p for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    for path in files:
        if path.suffix == ".md":
            errors += handbook.link_errors(root, path, path.read_text(encoding="utf-8"))
        if path.suffix == ".json":
            try:
                read_json(path)
            except ValueError as error:
                errors.append(f"{path}: {error}")
    listing = subprocess.run(["git", "ls-files", "--cached"], cwd=root, capture_output=True, text=True, check=True).stdout
    for path in listing.splitlines():
        if Path(path).suffix.lower() in (".dll", ".exe", ".pdb", ".zip", ".gz", ".sav") or path.startswith((".local/", "artifacts/")):
            errors.append("Generated/proprietary file tracked: " + path)
    workspace = Workspace(root)
    workspace.submodules()
    if (root / "mod.project.json").exists():
        project = workspace.project()
        workspace.manifest(project)
        workspace.validate_content(project)
    if errors:
        raise WorkflowError("Repository validation failed:\n" + "\n".join(errors))
    print(f"Repository validation passed ({len(files)} authored/reference files checked).")
