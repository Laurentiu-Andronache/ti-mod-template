#!/usr/bin/env python3
"""Command dispatcher for ti.ps1. Run 'help' for all supported options."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import time

from scaffold import Workspace, WorkflowError, read_json, require_game_closed, restore_transaction, run, write_json

ROOT = Path(__file__).resolve().parents[1]


def parser():
    cli = argparse.ArgumentParser(description="Terra Invicta Windows mod workflow")
    commands = cli.add_subparsers(dest="command")
    setup = commands.add_parser("setup", help="Discover tools, restore dependencies, build/deploy MCP, generate client config")
    setup.add_argument("-GameDir", "--game-dir")
    setup.add_argument("-Tools", "--tools", default="", help="Comma-separated optional UI,Ships profiles")
    setup.add_argument("-NoDeploy", "--no-deploy", action="store_true", help="Build/stage tools without changing the game")
    commands.add_parser("doctor", help="Check local setup and version drift")
    init = commands.add_parser("init", help="Initialize one mod; refuses existing content")
    init.add_argument("-Id", "--id", required=True)
    init.add_argument("-Name", "--name")
    init.add_argument("-Kind", "--kind", choices=["Native", "Code", "Hybrid"], default="Hybrid")
    init.add_argument("-Author", "--author", default="Your name")
    init.add_argument("-Assets", "--assets", action="store_true")
    inspect = commands.add_parser("inspect", help="Read-only decompilation into .local/inspection")
    inspect.add_argument("-Type", "--type")
    inspect.add_argument("-Assembly", "--assembly", default="Assembly-CSharp.dll")
    inspect.add_argument("-IL", "--il", action="store_true")
    for name in ("build", "deploy"):
        command = commands.add_parser(name, help="Build/stage the mod" if name == "build" else "Build and deploy the mod while game is closed")
        command.add_argument("-Configuration", "--configuration", choices=["Debug", "Release"], default="Release")
        command.add_argument("-DevTools", "--dev-tools", action="store_true")
    test = commands.add_parser("test", help="Run offline tests or a disposable runtime recipe")
    group = test.add_mutually_exclusive_group(required=True)
    group.add_argument("-Offline", "--offline", action="store_true")
    group.add_argument("-Recipe", "--recipe", help="Path or built-in recipe name, e.g. code-smoke")
    commands.add_parser("package", help="Build a Release ZIP without development tools")
    commands.add_parser("logs", help="Collect game and loader logs under .local")
    restore = commands.add_parser("restore", help="Restore deployment journals, or an unfinished runtime session")
    restore.add_argument("-Session", "--session", help="Run folder name from .local/runs")
    call = commands.add_parser("call", help="Use one installed MCP tool without configuring an agent client")
    call.add_argument("-Tool", "--tool", default="observe")
    call.add_argument("-Json", "--json", default="{}")
    dev = commands.add_parser("dev", help="Send a structured development-helper request via MCP console")
    dev.add_argument("-Json", "--json", required=True)
    commands.add_parser("help")
    return cli


def main():
    cli = parser()
    args = cli.parse_args()
    workspace = Workspace(ROOT)
    try:
        if args.command in (None, "help"):
            cli.print_help()
        elif args.command == "setup":
            profiles = tuple(p.strip() for p in args.tools.split(",") if p.strip())
            if set(profiles) - {"UI", "Ships"}:
                raise WorkflowError("-Tools accepts UI,Ships. Use init -Assets for a Unity authoring project.")
            workspace.setup(args.game_dir, profiles, args.no_deploy)
        elif args.command == "doctor":
            from scaffold import loader_config
            config = workspace.config()
            game = workspace.game()
            loader_config(game)
            workspace.submodules()
            current = workspace.fingerprint(game)
            changed = {k: v for k, v in current.items() if k != "lastLogVersionLines"} != {
                k: v for k, v in config["fingerprint"].items() if k != "lastLogVersionLines"}
            print(json.dumps({"gameDir": str(game), "python": sys.executable, "dotnet": config["dotnet"],
                              "fingerprint": current, "changedSinceSetup": changed}, indent=2))
            workspace.dotnet(["--version"])
            workspace.dotnet(["tool", "run", "ilspycmd", "--version"])
            if changed:
                raise WorkflowError("Installation fingerprint changed. Review compatibility, rerun setup, rebuild, and repeat affected runtime tests.")
        elif args.command == "init":
            workspace.initialize(args.id, args.name, args.kind, args.author, args.assets)
        elif args.command == "inspect":
            if Path(args.assembly).name != args.assembly or not args.assembly.endswith(".dll"):
                raise WorkflowError("-Assembly must be a DLL filename in the game's Managed directory")
            managed = workspace.game() / "TerraInvicta_Data/Managed"
            assembly = managed / args.assembly
            from scaffold import digest
            fingerprint = digest(assembly)
            folder = workspace.local / "inspection" / fingerprint[:16]
            folder.mkdir(parents=True, exist_ok=True)
            options = ["tool", "run", "ilspycmd", "--disable-updatecheck", "-r", managed]
            options += ["-t", args.type] if args.type else ["-l", "c"]
            if args.il:
                options.append("-il")
            options.append(assembly)
            output = workspace.dotnet(options, capture=True)
            name = re.sub(r"[^A-Za-z0-9_.-]", "_", args.type or "types") + (".il.txt" if args.il else ".cs.txt")
            path = folder / name
            path.write_text(output, encoding="utf-8")
            write_json(folder / "source.json", {"assembly": str(assembly), "sha256": fingerprint, "ilspycmd": "9.1.0.7988"})
            print(path)
        elif args.command in ("build", "deploy"):
            if args.command == "deploy":
                require_game_closed()
            stage = workspace.build(args.configuration, args.dev_tools)
            if args.command == "deploy":
                workspace.deploy_folder(stage, workspace.project()["id"])
                if args.dev_tools:
                    workspace.deploy_folder(workspace.local / "staging/TiModTemplate.DevTools", "TiModTemplate.DevTools")
        elif args.command == "test":
            if args.offline:
                run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT)
                from validate import validate_repository
                validate_repository(ROOT)
            else:
                from runtime import run_recipe
                recipe = Path(args.recipe)
                if not recipe.exists():
                    recipe = ROOT / "tests/recipes" / (args.recipe + ".json")
                run_recipe(workspace, recipe)
        elif args.command == "package":
            workspace.package()
        elif args.command == "logs":
            from runtime import collect_logs
            print(collect_logs(workspace, workspace.local / "logs" / time.strftime("%Y%m%d-%H%M%S")))
        elif args.command == "restore":
            require_game_closed()
            if args.session:
                from scaffold import contained
                from runtime import restore_session
                restore_session(workspace, contained(workspace.local / "runs", args.session))
            else:
                pending = [p for p in (workspace.local / "runs").glob("*/session.json") if read_json(p)["status"] != "restored"]
                if pending:
                    raise WorkflowError("Restore the unfinished runtime session first: -Session " + pending[0].parent.name)
                for path in sorted((workspace.local / "deployments").glob("*/manifest.json"), reverse=True):
                    restore_transaction(path, workspace.game())
                print("Recorded deployments restored; unrelated files and mod settings retained.")
        elif args.command in ("call", "dev"):
            from runtime import MCP
            client = MCP(workspace)
            try:
                result = client.dev(json.loads(args.json)) if args.command == "dev" else client.call(args.tool, json.loads(args.json))
                print(json.dumps(result, ensure_ascii=False, indent=2))
                if args.command == "dev" and not result.get("ok"):
                    return 1
            finally:
                client.close()
    except (WorkflowError, ValueError, OSError, KeyError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
