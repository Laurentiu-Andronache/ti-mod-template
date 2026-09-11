"""Windows mod workflow. Standard library only; proprietary inputs stay local."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.request
import uuid
import xml.etree.ElementTree as ET
import zipfile


MOD_ATTRIBUTION = "Created using https://github.com/Laurentiu-Andronache/ti-mod-template"


class WorkflowError(Exception):
    pass


def mod_description(description):
    # Keep one attribution at the end, including after an existing description is edited.
    body = "\n".join(line for line in description.splitlines()
                     if line.strip() != MOD_ATTRIBUTION).rstrip()
    return body + "\n\n" + MOD_ATTRIBUTION if body else MOD_ATTRIBUTION


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate key {key!r}")
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f"non-JSON number {value}")

    return json.loads(Path(path).read_text(encoding="utf-8-sig"),
                      object_pairs_hook=pairs, parse_constant=constant)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def digest(path, algorithm="sha256"):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, algorithm).hexdigest()


def contained(root, relative):
    """Reject traversal, ADS, and links/junctions before any write or removal."""
    root = Path(root).absolute()
    relative = Path(relative)
    if relative.is_absolute() or any(p in ("..", ".") or ":" in p for p in relative.parts):
        raise WorkflowError(f"Unsafe relative path: {relative}")
    result = root / relative
    def linked(path):
        try:
            return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)
        except FileNotFoundError:
            return False
    for path in (root, *root.parents):
        if linked(path):
            raise WorkflowError(f"Refusing linked directory: {path}")
    for path in (result, *result.parents):
        if path == root:
            break
        if linked(path):
            raise WorkflowError(f"Refusing linked path: {path}")
    if not result.resolve().is_relative_to(root.resolve()):
        raise WorkflowError(f"Path escapes {root}: {result}")
    return result


def remove_tree(root, relative):
    path = contained(root, relative)
    if path == Path(root).resolve():
        raise WorkflowError("Cannot remove workspace root")
    if path.exists():
        # Check descendants too: do not follow an embedded junction on Windows.
        for child in path.rglob("*"):
            contained(root, child.relative_to(root))
        shutil.rmtree(path)


def run(arguments, *, cwd=None, env=None, capture=False, timeout=600):
    result = subprocess.run([str(a) for a in arguments], cwd=cwd, env=env,
                            text=True, encoding="utf-8", errors="replace",
                            capture_output=capture, timeout=timeout)
    if result.returncode:
        details = ((result.stdout or "") + (result.stderr or "")).strip()
        raise WorkflowError(f"Command failed ({result.returncode}): {arguments[0]}\n{details}")
    return result.stdout if capture else None


def download(spec, destination):
    destination = Path(destination)
    algorithm = "sha512" if "sha512" in spec else "sha256"
    if destination.exists() and digest(destination, algorithm) == spec[algorithm]:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(".partial")
    print(f"Downloading {spec['url']}", flush=True)
    request = urllib.request.Request(spec["url"], headers={"User-Agent": "ti-mod-template"})
    with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as target:
        shutil.copyfileobj(response, target)
    if digest(partial, algorithm) != spec[algorithm]:
        partial.unlink()
        raise WorkflowError("Download checksum mismatch; nothing was installed")
    os.replace(partial, destination)


def extract_zip(archive, destination):
    destination = Path(destination)
    with zipfile.ZipFile(archive) as source:
        for item in source.infolist():
            # Zip paths use '/' even on Windows. Reject Unix symlinks too.
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise WorkflowError(f"Archive contains a symlink: {item.filename}")
            target = contained(destination, item.filename)
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(item) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)


def windows_processes():
    if os.name != "nt":
        return []
    text = run(["powershell.exe", "-NoProfile", "-Command",
                "@(Get-Process TerraInvicta -ErrorAction SilentlyContinue | "
                "Select-Object Id,Path,StartTime) | ConvertTo-Json -Compress"], capture=True)
    parsed = json.loads(text) if text.strip() else []
    return parsed if isinstance(parsed, list) else [parsed]


def require_game_closed():
    if windows_processes():
        raise WorkflowError("Terra Invicta is running. Close it before deployment/restoration; your session was left intact.")


def discover_game(explicit=None):
    if explicit:
        candidates = [Path(explicit)]
    else:
        candidates = []
        configured = os.environ.get("TerraInvictaDir") or os.environ.get("TI_ROOT")
        if configured:
            candidates.append(Path(configured))
        steam_roots = []
        if os.name == "nt":
            import winreg
            for hive, key, name in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                                    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")):
                try:
                    with winreg.OpenKey(hive, key) as handle:
                        steam_roots.append(Path(winreg.QueryValueEx(handle, name)[0]))
                except OSError:
                    pass
        steam_roots.append(Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Steam")
        for steam in list(steam_roots):
            libraries = steam / "steamapps/libraryfolders.vdf"
            if libraries.exists():
                for value in re.findall(r'"path"\s*"([^"]+)"', libraries.read_text(encoding="utf-8")):
                    steam_roots.append(Path(value.replace("\\\\", "\\")))
        candidates += [p / "steamapps/common/Terra Invicta" for p in steam_roots]
    found = sorted({p.resolve() for p in candidates
                    if (p / "TerraInvicta_Data/Managed/Assembly-CSharp.dll").is_file()})
    if len(found) != 1:
        raise WorkflowError("Supply -GameDir pointing to one Terra Invicta installation. Found: " +
                            (", ".join(map(str, found)) or "none"))
    return found[0]


def loader_config(game):
    folder = Path(game) / "TerraInvicta_Data/Managed/UnityModManager"
    path = folder / "Config.xml"
    if not path.exists() or not (folder / "UnityModManager.dll").exists():
        raise WorkflowError("Unity Mod Manager is missing. Install UMM for Terra Invicta, verify its menu, then rerun setup. See docs/setup.md.")
    tree = ET.parse(path).getroot()
    if tree.findtext("ModInfo") != "ModInfo.json" or tree.findtext("ModsDirectory", "").replace("\\", "/") != "Mods/Enabled":
        raise WorkflowError("UMM must use Mods/Enabled and ModInfo.json for this workflow. "
                            "The native loader treats other JSON metadata as templates. "
                            "Configuration was not changed; see docs/setup.md#loader-metadata.")
    if not (folder / "0Harmony.dll").exists():
        raise WorkflowError("UMM's bundled 0Harmony.dll is missing; repair the matching loader installation.")
    return folder


class Workspace:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.local = self.root / ".local"
        self.config_path = self.local / "machine.json"
        self.lock = read_json(self.root / "tools/dependencies.lock.json")

    def config(self):
        if not self.config_path.exists():
            raise WorkflowError("Run ./ti.ps1 setup first.")
        config = read_json(self.config_path)
        if config.get("workspace") != str(self.root):
            raise WorkflowError("Workspace moved. Run setup to regenerate local paths.")
        return config

    def game(self):
        return discover_game(self.config()["gameDir"])

    def fingerprint(self, game):
        result = {}
        for name in ("Assembly-CSharp.dll", "UnityEngine.CoreModule.dll",
                     "UnityModManager/UnityModManager.dll", "UnityModManager/0Harmony.dll"):
            path = Path(game) / "TerraInvicta_Data/Managed" / name
            if path.is_file():
                result[name] = {"sha256": digest(path), "bytes": path.stat().st_size}
        log = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "AppData/LocalLow/Pavonis Interactive/TerraInvicta/Player.log"
        if log.exists():
            lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
            result["lastLogVersionLines"] = [s for s in lines if
                "Initialize engine version:" in s or "[Manager] Version:" in s or
                re.search(r"(?:Terra Invicta|Game)[ :]+[Vv]ersion", s)][:10]
        return result

    def submodules(self, ships=False):
        for path, spec in self.lock["submodules"].items():
            if not spec["required"] and not ships:
                continue
            target = self.root / path
            if (target / ".git").exists():
                actual = run(["git", "rev-parse", "HEAD"], cwd=target, capture=True).strip()
                if actual != spec["commit"]:
                    raise WorkflowError(f"{path} differs from dependencies.lock.json. Update the gitlink and lock together, or restore the recorded revision.")
                if run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=target, capture=True).strip():
                    raise WorkflowError(f"{path} has local edits; setup will not overwrite them.")
            else:
                run(["git", "submodule", "update", "--init", "--checkout", "--", path], cwd=self.root)
                actual = run(["git", "rev-parse", "HEAD"], cwd=target, capture=True).strip()
                if actual != spec["commit"]:
                    raise WorkflowError(f"Submodule pin mismatch: {path}")

    def sdk(self):
        version = self.lock["sdk"]["version"]
        candidates = [self.local / "dotnet/dotnet.exe"]
        if shutil.which("dotnet"):
            candidates.append(Path(shutil.which("dotnet")))
        for candidate in candidates:
            if candidate.exists():
                listing = run([candidate, "--list-sdks"], capture=True)
                if any(line.startswith(version + " ") for line in listing.splitlines()):
                    return candidate
        archive = self.local / "downloads" / f"dotnet-{version}.zip"
        download(self.lock["sdk"], archive)
        extract_zip(archive, self.local / "dotnet")
        return self.local / "dotnet/dotnet.exe"

    def dotnet(self, arguments, capture=False):
        executable = self.config()["dotnet"]
        env = dict(os.environ, DOTNET_ROOT=str(Path(executable).parent),
                   DOTNET_MULTILEVEL_LOOKUP="0", DOTNET_CLI_TELEMETRY_OPTOUT="1",
                   DOTNET_SKIP_FIRST_TIME_EXPERIENCE="1")
        return run([executable, *arguments], cwd=self.root, env=env, capture=capture)

    def setup(self, game_dir=None, profiles=(), no_deploy=False):
        if os.name != "nt":
            raise WorkflowError("This template supports Windows only.")
        self.submodules(ships="Ships" in profiles)
        game = discover_game(game_dir)
        dotnet = self.sdk()
        config = {"schemaVersion": 1, "workspace": str(self.root), "gameDir": str(game),
                  "python": sys.executable, "dotnet": str(dotnet),
                  "fingerprint": self.fingerprint(game), "profiles": sorted(set(profiles))}
        write_json(self.config_path, config)
        self.dotnet(["tool", "restore"])
        loader_config(game)
        self.build_mcp()
        if not no_deploy:
            self.deploy_folder(self.local / "staging/TerraInvictaMCP", "TerraInvictaMCP")
        self.client_config()
        if "UI" in profiles:
            self.install_ui(no_deploy=no_deploy)
        if "Ships" in profiles:
            self.build_ships()
        print("Setup complete. Reconnect the MCP client to load its generated project configuration.", flush=True)

    def client_config(self):
        server = self.game() / "Mods/Enabled/TerraInvictaMCP/server"
        python = sys.executable
        folder = self.root / ".codex"
        folder.mkdir(exist_ok=True)
        path = folder / "config.toml"
        # Own a marked block; preserve all unrelated settings and existing servers.
        start, end = "# BEGIN TI-MOD-TEMPLATE MCP", "# END TI-MOD-TEMPLATE MCP"
        original = path.read_text(encoding="utf-8") if path.exists() else ""
        block = (f'{start}\n[mcp_servers.terra-invicta]\ncommand = {json.dumps(python)}\n'
                 f'args = [{json.dumps(str(server))}]\nstartup_timeout_sec = 30\n'
                 f'tool_timeout_sec = 360\n{end}')
        write_json(self.local / "mcp-config.json", {"mcpServers": {"terra-invicta":
                   {"command": python, "args": [str(server)]}}})
        if start in original and end in original:
            original = re.sub(re.escape(start) + r".*?" + re.escape(end), lambda _: block,
                              original, flags=re.S)
        elif re.search(r"\[mcp_servers\.[\"']?terra-invicta", original):
            raise WorkflowError("Existing terra-invicta MCP entry is not owned by setup; merge the snippet in .local/mcp-config.json.")
        else:
            original = original.rstrip() + "\n\n" + block + "\n"
        path.write_text(original.lstrip(), encoding="utf-8")

    def build_mcp(self):
        source = self.root / "tools/TerraInvictaMCP"
        stage = self.local / "staging/TerraInvictaMCP"
        remove_tree(self.root, stage.relative_to(self.root))
        stage.mkdir(parents=True)
        # Read the reference list from the pinned build script instead of maintaining a divergent list.
        text = (source / "build.ps1").read_text(encoding="utf-8-sig")
        match = re.search(r"\$Refs\s*=\s*@\((.*?)\n\)", text, re.S)
        if not match:
            raise WorkflowError("MCP build script changed; review its reference list before updating the adapter.")
        references = re.findall(r'"([^"\r\n]+\.dll)"', match[1])
        self.compile_game_sources(list((source / "src").rglob("*.cs")), stage / "TerraInvictaMCP.dll", references)
        shutil.copy2(source / "ModInfo.json", stage / "ModInfo.json")
        shutil.copy2(source / "LICENSE", stage / "LICENSE")
        for name in ("server", "docs", "src"):
            for path in (source / name).rglob("*"):
                if path.is_file() and path.suffix in (".py", ".md", ".cs") and "__pycache__" not in path.parts:
                    target = stage / path.relative_to(source)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
        write_json(stage / "scaffold-build.dat", {"commit": self.lock["submodules"]["tools/TerraInvictaMCP"]["commit"],
                   "assemblySha256": digest(stage / "TerraInvictaMCP.dll")})
        return stage

    def compile_game_sources(self, sources, output, references):
        managed = self.game() / "TerraInvicta_Data/Managed"
        loader_config(self.game())
        version = self.lock["sdk"]["version"]
        # --list-sdks resolves the SDK location even when an existing system SDK is selected.
        listing = self.dotnet(["--list-sdks"], capture=True)
        sdk_base = next((re.search(r"\[(.*)\]", line).group(1) for line in listing.splitlines()
                         if line.startswith(version + " ")), None)
        if not sdk_base:
            raise WorkflowError("Pinned SDK missing; rerun setup.")
        compiler = Path(sdk_base) / version / "Roslyn/bincore/csc.dll"
        missing = [name for name in references if not (managed / name).is_file()]
        if missing:
            raise WorkflowError("Missing game references: " + ", ".join(missing))
        output.parent.mkdir(parents=True, exist_ok=True)
        self.dotnet([compiler, "/nologo", "/target:library", "/nostdlib+", "/noconfig", "/deterministic+",
                     f"/out:{output}", *[f"/reference:{managed / name}" for name in references],
                     *sorted(sources)])

    def install_ui(self, no_deploy=False):
        archive = self.local / "downloads/RuntimeUnityEditor-6.3.zip"
        download(self.lock["runtimeUnityEditor"], archive)
        unpacked = self.local / "rue-unpacked"
        remove_tree(self.root, unpacked.relative_to(self.root))
        extract_zip(archive, unpacked)
        manifests = list(unpacked.rglob("Info.json"))
        if len(manifests) != 1:
            raise WorkflowError("Unexpected RuntimeUnityEditor archive layout")
        source = manifests[0].parent
        stage = self.local / "staging/RuntimeUnityEditor"
        remove_tree(self.root, stage.relative_to(self.root))
        shutil.copytree(source, stage)
        info = read_json(stage / "Info.json")
        info.update(Title="RuntimeUnityEditor", Description="Development-only Unity inspector.")
        (stage / "Info.json").unlink()
        # UMM update catalogs are not native templates and must not be installed as JSON.
        for path in stage.rglob("*.json"):
            path.unlink()
        write_json(stage / "ModInfo.json", info)
        if not no_deploy:
            self.deploy_folder(stage, "RuntimeUnityEditor")

    def build_ships(self):
        source = self.root / "references/TIShipModdingFramework/ShipModdingFramework"
        refs = ["mscorlib.dll", "System.dll", "System.Core.dll", "netstandard.dll",
                "Assembly-CSharp.dll", "Assembly-CSharp-firstpass.dll",
                "UnityEngine.dll", "UnityEngine.CoreModule.dll", "UnityEngine.PhysicsModule.dll",
                "UnityEngine.ParticleSystemModule.dll", "UnityEngine.AssetBundleModule.dll",
                "UnityEngine.AudioModule.dll", "UnityEngine.UI.dll", "UnityEngine.UIModule.dll",
                "UnityModManager/UnityModManager.dll", "UnityModManager/0Harmony.dll"]
        sources = [p for p in source.rglob("*.cs") if "obj" not in p.parts and "bin" not in p.parts]
        self.compile_game_sources(sources, self.local / "ships/ShipModdingFramework.dll", refs)
        print("Ship framework adapter built. This is not an in-game compatibility or asset test.")

    def project(self):
        path = self.root / "mod.project.json"
        if not path.exists():
            raise WorkflowError("Initialize a mod first: ./ti.ps1 init -Id YourName.YourMod -Kind Hybrid")
        project = read_json(path)
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z][A-Za-z0-9]*)+", project.get("id", "")):
            raise WorkflowError("Mod ID must use dotted identifiers, e.g. Author.MyMod (letters and digits).")
        if project.get("kind") not in ("Native", "Code", "Hybrid"):
            raise WorkflowError("Mod kind must be Native, Code, or Hybrid")
        if not re.fullmatch(r"\d+\.\d+\.\d+", project.get("version", "")):
            raise WorkflowError("Version must be major.minor.patch")
        return project

    def initialize(self, mod_id, name, kind, author, assets=False):
        if any((self.root / p).exists() for p in ("mod.project.json", "src/Mod", "content")):
            raise WorkflowError("This clone already has a mod or authored content. Initialization will not overwrite it.")
        project = {"schemaVersion": 1, "id": mod_id, "name": name or mod_id, "kind": kind,
                   "author": author, "version": "0.1.0", "description": mod_description("Describe this mod's behavior."),
                   "native": {"LoadOrder": 0}, "requiredAssemblies": [], "packageFiles": []}
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z][A-Za-z0-9]*)+", mod_id):
            raise WorkflowError("Use a dotted ID such as Author.MyMod; only letters and digits in each segment.")
        write_json(self.root / "mod.project.json", project)
        (self.root / "content").mkdir()
        (self.root / "content/.gitkeep").touch()
        if kind != "Native":
            source = self.root / "src/Mod"
            source.mkdir(parents=True)
            for template in (self.root / "templates/umm").iterdir():
                if template.is_file():
                    text = template.read_text(encoding="utf-8").replace("__MOD_ID__", mod_id)
                    (source / template.name).write_text(text, encoding="utf-8")
        if assets:
            shutil.copytree(self.root / "templates/unity", self.root / "assets/UnityProject")
        print(f"Initialized {kind} mod {mod_id}. Edit content/ and src/Mod/ as applicable.")

    def validate_content(self, project, game=None):
        content = self.root / "content"
        files = []
        allowed_extra = set(project.get("packageFiles", []))
        known = set()
        if game:
            known = {p.name for p in (Path(game) / "TerraInvicta_Data/StreamingAssets/Templates").glob("*.json")}
            known |= {p.name for p in (Path(game) / "DLC_Content").rglob("*.json")}
        for path in content.rglob("*"):
            if not path.is_file() or path.name == ".gitkeep":
                continue
            rel = path.relative_to(content)
            contained(content, rel)
            if path.suffix.lower() in (".dll", ".pdb", ".exe", ".cs", ".csproj", ".py", ".ps1"):
                raise WorkflowError(f"Executable/source file in content: {rel}. Add runtime dependencies through a reviewed build step.")
            if path.suffix.lower() == ".json":
                if len(rel.parts) != 1:
                    raise WorkflowError(f"Keep native JSON flat: {rel}; merge settings belong to its immediate directory.")
                if path.name == "ModInfo.json":
                    raise WorkflowError("Metadata is generated from mod.project.json; remove content/ModInfo.json.")
                if known and path.name not in known:
                    raise WorkflowError(f"Unknown template filename: {path.name}. Verify the installed template type before adding support.")
                if not known and not re.fullmatch(r"TI[A-Za-z0-9]+\.json", path.name):
                    raise WorkflowError(f"Unexpected JSON in game package: {rel}")
                value = read_json(path)
                if path.name == "TIGlobalConfig.json":
                    if not isinstance(value, dict):
                        raise WorkflowError("TIGlobalConfig.json must be an object")
                elif not isinstance(value, list) or any(not isinstance(row, dict) or not row.get("dataName") for row in value):
                    raise WorkflowError(f"{path.name} must be an array of records with dataName")
                if isinstance(value, list):
                    names = [row["dataName"] for row in value]
                    if len(names) != len(set(names)):
                        raise WorkflowError(f"Duplicate dataName in {path.name}")
            elif path.suffix.lower() == ".csv":
                pass  # TI localization format is validated in-game, not rewritten as generic CSV.
            elif rel.as_posix() not in allowed_extra:
                raise WorkflowError(f"Add authored asset to packageFiles explicitly: {rel.as_posix()}")
            files.append(path)
        for extra in allowed_extra:
            if not contained(content, extra).is_file():
                raise WorkflowError(f"Listed package file is missing: {extra}")
        return files

    def manifest(self, project):
        native = project.get("native", {})
        allowed = {"LoadOrder", "TemplatesToConcatArrays", "TemplatesToReplaceArrays", "TemplatesToReplace",
                   "ModURL"}
        if not isinstance(native, dict) or set(native) - allowed:
            raise WorkflowError("Unsupported native metadata key; inspect the current loader before extending the descriptor.")
        if "LoadOrder" in native and type(native["LoadOrder"]) is not int:
            raise WorkflowError("LoadOrder must be an integer")
        for key in ("TemplatesToConcatArrays", "TemplatesToReplaceArrays", "TemplatesToReplace"):
            if key in native and (not isinstance(native[key], list) or
                                  any(not isinstance(n, str) or Path(n).name != n or not n.endswith(".json") for n in native[key])):
                raise WorkflowError(f"{key} must be an array of exact JSON filenames")
        info = {"Title": project["id"], "Author": project["author"],
                "Description": mod_description(project["description"]), **native}
        if project["kind"] != "Native":
            info.update(Id=project["id"], DisplayName=project["name"], Version=project["version"],
                        ManagerVersion="0.33.0", AssemblyName=project["id"] + ".dll",
                        EntryMethod=project["id"] + ".Main.Load", Requirements=[])
        return info

    def build(self, configuration="Release", dev_tools=False, *, mod_tests=None):
        if configuration not in ("Debug", "Release"):
            raise WorkflowError("configuration must be Debug or Release")
        if type(dev_tools) is not bool or (mod_tests is not None and type(mod_tests) is not bool):
            raise WorkflowError("devTools and modTests must be booleans")
        mod_tests = dev_tools if mod_tests is None else mod_tests
        project = self.project()
        game = self.game() if self.config_path.exists() else None
        files = self.validate_content(project, game)
        stage = self.root / "artifacts" / configuration / project["id"]
        remove_tree(self.root, stage.relative_to(self.root))
        stage.mkdir(parents=True)
        if project["kind"] != "Native":
            if not game:
                raise WorkflowError("Run setup before compiling a code mod.")
            loader_config(game)
            extra = ET.Element("Project")
            group = ET.SubElement(extra, "ItemGroup")
            for name in project.get("requiredAssemblies", []):
                if not isinstance(name, str) or Path(name).name != name or not name.endswith(".dll"):
                    raise WorkflowError("requiredAssemblies entries must be filenames in Managed/")
                reference = game / "TerraInvicta_Data/Managed" / name
                if not reference.is_file():
                    raise WorkflowError(f"Required game assembly not found: {reference}")
                item = ET.SubElement(group, "Reference", {"Include": name[:-4]})
                ET.SubElement(item, "HintPath").text = str(reference)
                ET.SubElement(item, "Private").text = "false"
            extra_path = self.local / "ExtraReferences.props"
            extra_path.parent.mkdir(parents=True, exist_ok=True)
            ET.ElementTree(extra).write(extra_path, encoding="utf-8", xml_declaration=True)
            self.dotnet(["build", self.root / "src/Mod/Mod.csproj", "-c", configuration,
                         f"-p:TerraInvictaDir={game}", f"-p:ModId={project['id']}",
                         f"-p:Version={project['version']}", f"-p:EnableModTests={str(mod_tests).lower()}",
                         f"-p:ExtraReferencesFile={extra_path}", "--nologo"])
            output = self.root / f"src/Mod/bin/{configuration}/net48/{project['id']}.dll"
            shutil.copy2(output, stage / output.name)
        for source in files:
            target = stage / source.relative_to(self.root / "content")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        write_json(stage / "ModInfo.json", self.manifest(project))
        for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
            if (self.root / name).is_file():
                shutil.copy2(self.root / name, stage / name)
        write_json(stage.parent / f"{project['id']}.build.json",
                   {"project": project, "configuration": configuration, "devTools": dev_tools,
                    "modTests": mod_tests if project["kind"] != "Native" else False,
                    "files": {p.relative_to(stage).as_posix(): digest(p) for p in stage.rglob("*") if p.is_file()},
                    "fingerprint": self.fingerprint(game) if game else None})
        if dev_tools:
            self.build_devtools()
        print(f"Package staged: {stage}")
        return stage

    def build_devtools(self):
        stage = self.local / "staging/TiModTemplate.DevTools"
        remove_tree(self.root, stage.relative_to(self.root))
        stage.mkdir(parents=True, exist_ok=True)
        references = ["mscorlib.dll", "System.dll", "System.Core.dll", "netstandard.dll",
                      "Assembly-CSharp.dll", "Assembly-CSharp-firstpass.dll", "Newtonsoft.Json.dll",
                      "UnityEngine.dll", "UnityEngine.CoreModule.dll", "UnityEngine.UI.dll", "UnityEngine.UIModule.dll",
                      "UnityEngine.IMGUIModule.dll", "UnityEngine.InputLegacyModule.dll", "UnityEngine.TextRenderingModule.dll", "Unity.TextMeshPro.dll",
                      "UnityModManager/UnityModManager.dll", "UnityModManager/0Harmony.dll"]
        self.compile_game_sources(list((self.root / "tools/DevTools").glob("*.cs")),
                                  stage / "TiModTemplate.DevTools.dll", references)
        write_json(stage / "ModInfo.json", {"Id": "TiModTemplate.DevTools", "Title": "TiModTemplate.DevTools",
                   "DisplayName": "TI Mod Template Development Tools", "Author": "TI mod template contributors",
                   "Description": "Development only: console probes and UI test helpers.", "Version": "0.1.0",
                   "ManagerVersion": "0.33.0", "AssemblyName": "TiModTemplate.DevTools.dll",
                   "EntryMethod": "TiModTemplate.DevTools.Main.Load"})
        return stage

    def deploy_folder(self, source, mod_id, on_prepared=None):
        require_game_closed()
        game = self.game()
        loader_config(game)
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", mod_id):
            raise WorkflowError("Invalid deployment folder name")
        target = contained(game, "Mods/Enabled/" + mod_id)
        source = Path(source)
        if not (source / "ModInfo.json").is_file():
            raise WorkflowError(f"Missing staged manifest: {source}")
        return deploy_transaction(self.root, source, target, on_prepared=on_prepared)

    def package(self):
        project = self.project()
        stage = self.build("Release", dev_tools=False, mod_tests=False)
        record = read_json(stage.parent / f"{project['id']}.build.json")
        if record.get("modTests", record.get("devTools", False)) or record["configuration"] != "Release":
            raise WorkflowError("Development build cannot be packaged")
        output = self.root / "artifacts" / f"{project['id']}-{project['version']}.zip"
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, expected in sorted(record["files"].items()):
                path = contained(stage, name)
                if digest(path) != expected:
                    raise WorkflowError(f"Staged file changed: {name}")
                archive.write(path, f"{project['id']}/{name}")
        print(f"Release ZIP: {output} (SHA256 {digest(output)})")
        return output

    def remove_mod(self, mod_id, on_prepared=None):
        """Temporarily remove a whole project folder through an ordinary journal."""
        require_game_closed()
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", mod_id):
            raise WorkflowError("Invalid mod ID")
        empty = self.local / "empty-removal-source"
        empty.mkdir(parents=True, exist_ok=True)
        if any(empty.iterdir()):
            raise WorkflowError("Removal source must be empty")
        target = contained(self.game(), "Mods/Enabled/" + mod_id)
        return deploy_transaction(self.root, empty, target, on_prepared=on_prepared, remove_all=True)


def deploy_transaction(workspace, source, target, on_prepared=None, *, remove_all=False):
    """Write-ahead journal. Backups remain outside the game and survive process interruption."""
    workspace, source, target = Path(workspace), Path(source), Path(target)
    transactions = workspace / ".local/deployments"
    transactions.mkdir(parents=True, exist_ok=True)
    active = []
    for path in sorted(transactions.glob("*/manifest.json")):
        previous = read_json(path)
        if previous["target"] == str(target) and previous["status"] != "restored":
            active.append((path, previous))
    if any(m["status"] == "installing" for _, m in active):
        raise WorkflowError("Interrupted deployment found. Run restore before deploying again.")
    owned = {}
    for _, previous in active:
        for name, entry in previous["files"].items():
            owned[name] = entry.get("after")
    incoming = {p.relative_to(source).as_posix(): p for p in source.rglob("*") if p.is_file()}
    for name in incoming:
        contained(source, name)
    names = set(incoming) | set(owned)
    if remove_all:
        if incoming:
            raise WorkflowError("Removal transaction cannot install files")
        names.update(p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file())
    # Do not silently overwrite edits made after a previous deployment.
    for name, expected in owned.items():
        path = contained(target, name)
        actual = digest(path) if path.is_file() else None
        if actual != expected:
            raise WorkflowError(f"Deployed file was changed externally: {path}. Preserve/reconcile it before continuing.")
    journal_dir = transactions / (time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    journal = {"schemaVersion": 1, "target": str(target), "status": "installing", "files": {},
               "existingFiles": sorted(p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file())}
    if remove_all:
        journal["removedFolder"] = target.exists()
        journal["existingDirectories"] = [p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_dir()]
    journal_path = journal_dir / "manifest.json"
    for name in sorted(names):
        destination = contained(target, name)
        before = digest(destination) if destination.is_file() else None
        backup = contained(journal_dir / "before", name)
        if before:
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, backup)
        journal["files"][name] = {"before": before, "after": digest(incoming[name]) if name in incoming else None,
                                  "temporary": name + ".ti-" + uuid.uuid4().hex + ".tmp"}
    write_json(journal_path, journal)
    if on_prepared:
        on_prepared(journal_path)
    for name, entry in journal["files"].items():
        destination = contained(target, name)
        if name in incoming:
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = contained(target, entry["temporary"])
            shutil.copy2(incoming[name], temporary)
            os.replace(temporary, destination)
        elif destination.exists():
            destination.unlink()
    if remove_all:
        prune_empty_directories(target)
    journal["status"] = "installed"
    write_json(journal_path, journal)
    print(f"Deployed {target.name}; recovery journal: {journal_path}")
    return journal_path


def prune_empty_directories(target):
    if target.exists():
        for folder in sorted((p for p in target.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            contained(target, folder.relative_to(target))
            if not any(folder.iterdir()):
                folder.rmdir()
        if not any(target.iterdir()):
            target.rmdir()


def restore_transaction(path, game, remove_generated=False):
    path = Path(path)
    journal = read_json(path)
    if journal["status"] == "restored":
        return
    target = Path(journal["target"])
    # A tampered journal must not turn restore into an arbitrary filesystem writer.
    relative = target.relative_to(Path(game))
    target = contained(game, relative)
    if len(relative.parts) != 3 or relative.parts[:2] != ("Mods", "Enabled"):
        raise WorkflowError("Deployment journal target is not a direct Mods/Enabled folder")
    for name, entry in journal["files"].items():
        destination = contained(target, name)
        current = digest(destination) if destination.is_file() else None
        if current not in (entry["before"], entry["after"]):
            raise WorkflowError(f"Refusing to overwrite an external edit during restore: {destination}")
        if entry["before"] is not None:
            backup = contained(path.parent / "before", name)
            if not backup.is_file() or digest(backup) != entry["before"]:
                raise WorkflowError(f"Missing or damaged deployment backup: {backup}")
    for name, entry in journal["files"].items():
        destination = contained(target, name)
        if entry["before"] is not None:
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Older journals lack a temporary name. Persist one before restoring,
            # so recovery itself can be interrupted safely.
            if "temporary" not in entry:
                entry["temporary"] = name + ".ti-" + uuid.uuid4().hex + ".tmp"
                write_json(path, journal)
            temporary = contained(target, entry["temporary"])
            shutil.copy2(contained(path.parent / "before", name), temporary)
            os.replace(temporary, destination)
        elif destination.exists():
            destination.unlink()
        if entry.get("temporary"):
            temporary = contained(target, entry["temporary"])
            if temporary.exists():
                temporary.unlink()
    if target.exists() and remove_generated:
        for generated in target.rglob("*"):
            if not generated.is_file():
                continue
            name = generated.relative_to(target).as_posix()
            if name not in journal.get("existingFiles", []) and name not in journal["files"]:
                contained(target, name)
                archive = contained(path.parent / "generated", name)
                archive.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(generated, archive)
                generated.unlink()
    prune_empty_directories(target)
    if journal.get("removedFolder"):
        target.mkdir(parents=True, exist_ok=True)
        for name in journal.get("existingDirectories", []):
            contained(target, name).mkdir(parents=True, exist_ok=True)
    journal["status"] = "restored"
    write_json(path, journal)
