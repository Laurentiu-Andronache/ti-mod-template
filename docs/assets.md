# Assets and specialist tools

## Unity bundles

Create an authoring project while initializing the mod:

```powershell
.\ti.ps1 init -Id Author.AssetMod -Kind Native -Assets
```

Open `assets/UnityProject` with **Unity 2020.3.49f1** and Windows x64 build support. This version is the handbook's known authoring profile, matching the inspected player; another target build needs a deliberate compatibility check. The project contains a minimal editor helper with the same version gate and Windows target as the [handbook bundle workflow](../references/ti-mods/docs/assets.md). The original [CreateAssetBundles helper](../references/ti-mods/tutorials/tutorial-files/CreateAssetBundles.cs) is also available in the pinned handbook.

Assign unique bundle names in Unity's asset importer, then run `TI Mod > Build Windows bundles`. For agent-driven batch builds, use the installed Unity editor:

```powershell
& 'C:\Program Files\Unity\Hub\Editor\2020.3.49f1\Editor\Unity.exe' -batchmode -quit -projectPath "$PWD\assets\UnityProject" -executeMethod BuildModBundles.Build -logFile "$PWD\.local\unity-build.log"
```

The helper writes to `.local/asset-bundles`, outside `Assets`. Copy intended content bundles and their matching `.manifest` files to `content/` and list each in `packageFiles`. Do not ship the entire Unity project or the generated aggregate manifest/bundle unless the game's loader specifically needs it. Template asset paths use the game's `bundleName/assetName` convention, not filesystem paths.

Verify the bundle in the running game. Pink materials, missing sprites or stale content can be shader/import/version/dependency/name problems, not just incorrect file placement. Restart after replacing bundles and exercise the screen that actually consumes the asset.

## Ship framework

`setup -Tools Ships` initializes the pinned [TIShipModdingFramework](https://github.com/UNNRazorback/TIShipModdingFramework) source. The build adapter replaces its developer-specific reference paths by compiling the existing sources against the selected game. Output stays in `.local/ships`; it is not automatically installed or packaged as part of every mod.

The framework adds no ship content by itself. Follow its prefab hierarchy and registration examples plus the handbook's [ship notes](../references/ti-mods/docs/assets.md#inspect-assets-and-ship-examples). Match hull/model keys, drive objects, mount pairs, radiators, collision layers and effects to the inspected framework and game. Decide whether to incorporate its MIT source or ship a reviewed runtime dependency with the needed license; the generic content allowlist deliberately rejects arbitrary DLLs.

Compilation validates the API adapter, not models or runtime behavior. Test hull selection, designer slots, tactical firing, propulsion, RCS and the strategic-map model separately. The handbook retains a [MonoMod adaptation](../references/ti-mods/tutorials/tutorial-files/TIShipModdingFramework_MonoMod.cs) for existing alternate-loader projects.

## Other asset pipelines

| Task | Tool and concrete starting point |
|---|---|
| Inspect/export Unity assets | [AssetRipper](https://github.com/AssetRipper/AssetRipper); extract a small relevant bundle into `.local`, then repair exported projects as needed |
| Portrait video | [FFmpeg](https://ffmpeg.org/download.html); follow the [VP8/alpha guidance](../references/ti-mods/tutorials/Councillor%20Portraits.md) and verify playback/transparency in-game |
| Images and badges | [GIMP](https://www.gimp.org/downloads/); retain layered sources, export RGBA images, inspect actual scale and alpha |
| Maps | [Inkscape](https://inkscape.org/); follow the [map coordinate/layer workflow](../references/ti-mods/tutorials/MapCreation.md) |
| Audio | [FMOD Studio](https://www.fmod.com/download#fmodstudio); start with the game's supplied authoring project and [bank/version instructions](../references/ti-mods/tutorials/Audio%20Modding%20Guide.md) |

These are task-dependent external tools rather than large source submodules downloaded for every balance mod. Record their actual versions in the asset project and evidence. Keep extracted shipped assets and decompiled scripts local; commit only assets you can intentionally distribute.

The current [Unity Editor MCP](https://github.com/CoplayDev/unity-mcp#quickstart) supports Unity 2021.3 and later. It is not automatically added to this Unity 2020.3 authoring project. Its editor bridge also does not replace TerraInvictaMCP's running-game bridge.
