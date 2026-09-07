# Third-party notices

The C# starter, console registration lifecycle and modding guidance adapt portions of the MIT-licensed [ti-mods fork](https://github.com/Laurentiu-Andronache/ti-mods). Its original notice is retained below. The full handbook remains a separately pinned submodule with its own license.

```text
MIT License

Copyright (c) 2022

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

| Dependency | License / distribution |
|---|---|
| [TerraInvictaMCP fork](https://github.com/Laurentiu-Andronache/TerraInvictaMCP) | MIT, copyright 2026 MeatBunny; deployed with its LICENSE |
| [TIShipModdingFramework](https://github.com/UNNRazorback/TIShipModdingFramework) | MIT; retain its LICENSE.txt when incorporating substantial code |
| [ILSpy / ILSpyCmd](https://github.com/icsharpcode/ILSpy) | MIT; restored as a development tool |
| [RuntimeUnityEditor](https://github.com/ManlyMarco/RuntimeUnityEditor) | GPL-3.0; optional separate development tool, excluded from mod releases |
| [.NET SDK](https://github.com/dotnet/sdk) | Microsoft .NET distribution with included license/third-party notices; local development dependency |
| [Unity Mod Manager](https://github.com/newman55/unity-mod-manager) | MIT; referenced from the installation |
| [Harmony](https://github.com/pardeike/Harmony) | MIT; use UMM's matching copy |

The scaffold's MIT license does not relicense these dependencies or proprietary game/editor assets. Inspect each selected dependency's license when deciding to distribute it. The default release ZIP contains the mod's own DLL and authored content only.
