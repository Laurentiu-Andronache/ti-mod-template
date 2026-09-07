# Modding capability map

Use this map to load focused information instead of reading the entire handbook into context. The local links refer to the pinned handbook submodule; the corresponding online links use **our origin fork**. Verify installed code when a historical guide differs.

| Task | Local starting point | Origin reference |
|---|---|---|
| Installations, logs, saves, recovery | [Getting started](../references/ti-mods/docs/getting-started.md) | [Origin](https://github.com/Laurentiu-Andronache/ti-mods/blob/e0c91fb/docs/getting-started.md) |
| Native JSON values and new records | [JSON tutorial](../references/ti-mods/tutorials/Create_Template_JSON_mod.md) | [Origin](https://github.com/Laurentiu-Andronache/ti-mods/blob/e0c91fb/tutorials/Create_Template_JSON_mod.md) |
| Array merging, scenarios, Dark Skies | [Native data](../references/ti-mods/docs/native-data.md) | [Origin](https://github.com/Laurentiu-Andronache/ti-mods/blob/e0c91fb/docs/native-data.md) |
| Global fields absent from vanilla JSON | [GlobalConfig](../references/ti-mods/docs/global-config.md) | [Origin](https://github.com/Laurentiu-Andronache/ti-mods/blob/e0c91fb/docs/global-config.md) |
| Orgs, research, events, text, registration | [Content authoring](../references/ti-mods/docs/content-authoring.md) | [Origin](https://github.com/Laurentiu-Andronache/ti-mods/blob/e0c91fb/docs/content-authoring.md) |
| Custom organizations | [Organizations](../references/ti-mods/tutorials/Custom%20Orgs.md) | [Origin](https://github.com/Laurentiu-Andronache/ti-mods/blob/e0c91fb/tutorials/Custom%20Orgs.md) |
| Behavior patches and lifecycle | [Code modding](../references/ti-mods/docs/code-modding.md) | [Origin](https://github.com/Laurentiu-Andronache/ti-mods/blob/e0c91fb/docs/code-modding.md) |
| Template/state lookup, initialization | [APIs](../references/ti-mods/docs/template-and-state-apis.md) | [Origin](https://github.com/Laurentiu-Andronache/ti-mods/blob/e0c91fb/docs/template-and-state-apis.md) |
| Programmatic template changes | [Template recipe](../references/ti-mods/cookbook/patching_data_templates_in_code/index.md) | [Origin](https://github.com/Laurentiu-Andronache/ti-mods/blob/e0c91fb/cookbook/patching_data_templates_in_code/index.md) |
| Register a console command | [Console recipe](../references/ti-mods/cookbook/add_console_command/index.md) | [Origin](https://github.com/Laurentiu-Andronache/ti-mods/blob/e0c91fb/cookbook/add_console_command/index.md) |
| Add persisted campaign state | [Save-state recipe](../references/ti-mods/cookbook/save_mod_state_to_save_file/index.md) | [Origin](https://github.com/Laurentiu-Andronache/ti-mods/blob/e0c91fb/cookbook/save_mod_state_to_save_file/index.md) |
| New UI controls | [Unity UI](../references/ti-mods/tutorials/IntroToUI.md), [our helper](testing.md) | [Origin](https://github.com/Laurentiu-Andronache/ti-mods/blob/e0c91fb/tutorials/IntroToUI.md) |
| Ship designer layout | [Worked UI example](../references/ti-mods/tutorials/Ship%20Designer%20UI.md) | [Origin](https://github.com/Laurentiu-Andronache/ti-mods/blob/e0c91fb/tutorials/Ship%20Designer%20UI.md) |
| Bundles, models, ships | [Assets](../references/ti-mods/docs/assets.md), [our asset setup](assets.md) | [Origin](https://github.com/Laurentiu-Andronache/ti-mods/blob/e0c91fb/docs/assets.md) |
| Councilor portraits and badges | [Portraits](../references/ti-mods/tutorials/Councillor%20Portraits.md) | [Origin](https://github.com/Laurentiu-Andronache/ti-mods/blob/e0c91fb/tutorials/Councillor%20Portraits.md) |
| Region geometry and maps | [Map creation](../references/ti-mods/tutorials/MapCreation.md) | [Origin](https://github.com/Laurentiu-Andronache/ti-mods/blob/e0c91fb/tutorials/MapCreation.md) |
| Music, voice, sound effects | [Audio](../references/ti-mods/tutorials/Audio%20Modding%20Guide.md) | [Origin](https://github.com/Laurentiu-Andronache/ti-mods/blob/e0c91fb/tutorials/Audio%20Modding%20Guide.md) |
| Existing MonoMod/BepInEx mods | [Alternate loader](../references/ti-mods/tutorials/MonoMod%20Guide.md), [examples](../references/ti-mods/tutorials/MonoMod%20Examples.md) | [Origin](https://github.com/Laurentiu-Andronache/ti-mods/blob/e0c91fb/tutorials/MonoMod%20Guide.md) |
| Debugging and version changes | [Debugging](../references/ti-mods/docs/debugging.md), [compatibility](../references/ti-mods/docs/compatibility.md) | [Origin](https://github.com/Laurentiu-Andronache/ti-mods/blob/e0c91fb/docs/debugging.md) |
| Workshop upload/update | [Publishing](../references/ti-mods/tutorials/Uploading%20and%20Updating%20Workshop%20Mod.md) | [Origin](https://github.com/Laurentiu-Andronache/ti-mods/blob/e0c91fb/tutorials/Uploading%20and%20Updating%20Workshop%20Mod.md) |

Victory conditions, diplomacy, research, economic rules and councilor generation are code/data investigations, not fixed scaffold APIs. Search installed types, trace the player's operation and event/notification paths, and choose hooks after checking timing and state consistency. [Worked recipes](recipes.md) show how to do that without inventing signatures.

For unusual content, the table is a routing guide, not a restriction. Extend the authored mod and its tooling after finding concrete evidence for the additional capability. Existing MonoMod/BepInEx projects need their own build/deployment profiles; the default UMM package cannot be relabeled as another loader's plugin.
