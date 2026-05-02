# Kit Optimization Suggestions

Review of `src/kit` against `PowerToys-main`, focused on stability, build size (currently ~0.97 GB per release configuration), and PowerToys module compatibility.

## 1. Current Architecture Assessment

The "PowerToys-derived + explicit allowlist" approach is sound:

- Module loading is strictly limited by `KitKnownModules` (Awake / LightSwitch / Monitor); the three module DLLs and Awake/LightSwitch source are essentially in parity with `PowerToys-main` (diff only shows build-output differences).
- `shared_constants.h` already namespaces Kit identifiers: `APPDATA_PATH = "Kit"`, `AWAKE_EXIT_EVENT`, `MONITOR_EXIT_EVENT`, `LIGHTSWITCH_TOGGLE_EVENT`, `KitRunnerTerminateSettingsEvent` — preventing collisions with an installed official PowerToys.
- Updater / auto-update / settings telemetry are inert (`UpdateUtils.cpp` has three empty functions, `trace.cpp` is all empty stubs, `settings_telemetry::init` is no longer called by the runner).
- `Settings.UI.UnitTests` includes `BuildCompatibility.cs` and `General.cs` static checks that `KitKnownModules` / `KIT_URI_PROTOCOL_SCHEME` cannot regress. Keep this discipline.

## 2. Where the 0.97 GB Comes From

Measured `x64/1.0.1` = 1003 MB. Root causes: ".NET self-contained × 3 independent publish units + uncut WinAppSDK + unnecessary AI/WPF dependencies + unrestricted localization resources".

| Component | Estimated Size | Notes |
|---|---|---|
| **`WinUI3Apps/` subdirectory** | **~387 MB** | Full .NET 8 + WindowsAppSDK + WinUI3 self-contained runtime (Settings + QuickAccess) |
| **Duplicate DLLs in root** | **~250 MB** | `Microsoft.Windows.SDK.NET.dll` 26M×2, `onnxruntime.dll` 21M×2, `DirectML.dll` 18M×2, `PresentationFramework.dll` 16M×2, `System.Private.CoreLib.dll` 15M×2, `System.Windows.Forms.dll` 14M×2, etc. — almost full duplicate publish |
| **23 PDB files** | **~165 MB** | `Kit.pdb` 29M, `PowerToys.LightSwitchModuleInterface.pdb` 19M, `BackgroundActivator.pdb` 16M, `PowerToys.ActionRunner.pdb` 14M ... |
| **100 localization directories** | **~50–80 MB** | af-ZA, am-ET, ar-SA ... README declares English-only; all satellite resources are dead weight |
| **AI / ML runtime** | **~80 MB** | `onnxruntime.dll`(21M) + `DirectML.dll`(18M) + Microsoft.Windows.AI.* set, pulled in by `LanguageModelProvider` → `Microsoft.AI.Foundry.Local`. No active module uses AI |
| **WPF stack** | **~40 MB** | `PresentationFramework`/`PresentationCore`/`PresentationUI`/`PresentationFramework.Aero*`, pulled in by `Common.UI` via `<UseWPF>true</UseWPF>` + `<UseWindowsForms>true</UseWindowsForms>` |
| **OOBE assets** | **26 MB** | `Assets/Settings/Modules/OOBE/*.gif/png` — 31 files; pages already excluded via `<Page Remove>` but assets remain |

Side-channel waste: `x64/1.0.0` and `x64/1.0.1` contain near-identical content; combined with `x64/Debug` (1.2 GB), total `x64/` = 3.2 GB.

## 3. Stability / Dead-Code Risk Inventory

1. **`runner/main.cpp` retains the ImageResizer AI-detection branch** (lines 87–198, 261–272). `is_image_resizer_registered_for_kit()` always returns false, so `DetectAiCapabilitiesAsync()` is a dead path; `general_settings.cpp:247/433` still re-triggers it on settings changes. Adds startup latency and misleads future maintainers.
2. **`UpdateUtils.cpp` / `trace.cpp` are "empty ABI stubs"**. They compile and link, but the ETW provider GUID is still registered as `Microsoft.PowerToys` (`trace.cpp:8–11`). Minor for self-use, but inconsistent with the "self-use fork, Kit-branded" principle.
3. **`Common.UI` forces WPF**. The comment says "Hack: referenced for dll version alignment", but the cost is dragging the entire WPF runtime into every self-contained publish that references it.
4. **`LanguageModelProvider` is AdvancedPaste-specific**. AdvancedPaste page/viewmodel are excluded via `<Compile Remove>`, but `Settings.UI.csproj` still `ProjectReference`s `LanguageModelProvider.csproj`, dragging in `Microsoft.Extensions.AI` / `Microsoft.AI.Foundry.Local` / `OpenAI` / OnnxRuntime entirely.
5. **Monitor worker is also self-contained**. `PowerToys.Monitor.exe` is a headless scanner, but it generates its own `PowerToys.Monitor.deps.json` plus a duplicate copy of the .NET runtime (although it lands in the root dir shared with Awake).
6. **"Files-on-disk vs files-Removed" delta**. `Settings.UI/SettingsXAML/Views` still contains 37 `*Page.xaml.cs`, of which ~30 are silently excluded via csproj `<Compile Remove>`. Consequences:
   - Grep searches hit dead code.
   - Any later refactor of shared Settings code (e.g., `ShellViewModel`, `ModuleHelper`) risks accidentally "fixing" dead pages, creating false positives.
   - Upstream PowerToys-main merges will keep producing false-positive conflicts on these 30 files.
7. **`runner/main.cpp` still has OOBE / Scoobe trigger branches** (lines 328–336), but OOBE views are removed from csproj. `open_oobe_window()` may have no corresponding window after the trim, becoming a silent dead command. Either remove the `--open-oobe`/`--open-scoobe` command-line parsing entirely, or log "OOBE removed in Kit" explicitly.
8. **`x64/1.0.0` and `x64/1.0.1` coexist**. Older directories aren't auto-cleaned after `Version.props` bump. If the runner is changed to load from the newer version, Settings could still winload mismatched DLLs from the older directory. Each version bump should clean old version-numbered output dirs.
9. **`BuildTests=false` only disables test compilation**, but `Common.UI.Controls`, `Settings.UI.Controls`, `Common.Search`, etc., remain self-contained. Even without tests, Settings components each duplicate the .NET runtime.
10. **`.nuget-cache` / `.nuget-packages` / `.nuget-appdata`** sit at the repo root but are not in `.gitignore`. Currently empty shells, but easily filled by scripts and accidentally committed.
11. **Runtime folder vs module naming is mixed**: runner binary is `Kit.exe`, module DLLs are `PowerToys.AwakeModuleInterface.dll`, worker is `PowerToys.Monitor.exe`, Settings is at `WinUI3Apps\PowerToys.Settings.exe`. This is intentional for compatibility but is hard-coded in `KitKnownModules`, with logs mixing `Kit` and `PowerToys`. If PowerToys-main renames a module DLL, you must update `KitKnownModules` + three test references + build tasks. Centralizing into a single manifest would be more stable.

## 4. Slimming and Stability Recommendations (sorted by ROI)

### A. Quick Wins (~ -550 MB to -650 MB, zero module-behavior change)

1. **Disable satellite locale resources**. In `Directory.Build.props` csproj block, add:
   ```xml
   <PropertyGroup Condition="'$(MSBuildProjectExtension)' == '.csproj'">
     <SatelliteResourceLanguages>en-US</SatelliteResourceLanguages>
   </PropertyGroup>
   ```
   100 locale folders disappear immediately, saving ~50–80 MB, consistent with "visible UI use English Kit text".
2. **Don't ship PDBs in Release**. In `Directory.Build.props`:
   ```xml
   <PropertyGroup Condition="'$(Configuration)' == 'Release'">
     <DebugType>none</DebugType>
     <DebugSymbols>false</DebugSymbols>
   </PropertyGroup>
   ```
   For C++ projects: `<GenerateDebugInformation>false</GenerateDebugInformation>` (or keep PDBs but use `<DebugInformationFormat>None</DebugInformationFormat>` in a Release variant). 23 PDBs total ~165 MB. If you need debug symbols, keep portable PDBs in `obj/` and skip copying them to `Release/`.
3. **Delete OOBE assets**. The full `src\kit\src\settings-ui\Settings.UI\Assets\Settings\Modules\OOBE\` directory. Keep only `LightSwitch.png` / `Awake.png` / Monitor-relevant images (the latter to be added). -26 MB.
4. **Clean old `x64/1.0.0` version directories**, and add a PreBuild target next to `Version.props` to auto-clean old version subdirectories.
5. **Cut `Settings.UI` → `LanguageModelProvider`** ProjectReference + delete `FoundryLocalModelPicker.xaml/cs`:
   - Remove `<ProjectReference Include="..\..\common\LanguageModelProvider\LanguageModelProvider.csproj" />` from `PowerToys.Settings.csproj` line 221.
   - Comment out or remove `LanguageModelProvider` from `Kit.slnx`.
   - This stops `onnxruntime.dll` / `DirectML.dll` / `Microsoft.Windows.AI.*` from being published. ~ -80 MB.
6. **Remove the runner's ImageResizer AI-detection branch**:
   - Delete `main.cpp` lines 87–90, 120–198, 260–272; delete `ai_detection.h`.
   - Remove the ImageResizer enable triggers near `general_settings.cpp:247, 433`.
   - Add a negative test in `BuildCompatibility.cs`: runner `main.cpp` MUST NOT contain `DetectAiCapabilitiesAsync` / `ImageResizer`.
7. **Drop WPF/WinForms from `Common.UI`**. Set `Common.UI.csproj`'s `<UseWPF>` and `<UseWindowsForms>` to `false`. If the only purpose was a "dll version alignment" hack, aligning via `ManagedCommon` is enough — WPF (~30–40 MB) is too heavy. Validate Settings on a branch before merging.
8. **After dropping LanguageModelProvider, lock down OnnxRuntime / Microsoft.AI.\* transitive imports**. In `Settings.UI.csproj`, add `<RuntimeHostConfigurationOption Include="System.Globalization.Invariant" Value="true" />` (subject to compatibility) and explicit `<TrimmerRootAssembly>` entries listing only active module DLLs, to prevent these from being silently re-pulled later.

### B. Mid-Term (Structural Improvements)

9. **Centralize active-module manifest**. Currently four places must stay in sync: `runner/main.cpp` `KitKnownModules`, `Kit.slnx` BuildDependency, `Settings.UI` navigation/route mapping, Home `KitDashboardModules`. Suggest a `src\Kit.Modules.props` or `KitModules.json` that drives all four through T4/source generators — a single edit point. Do this after Phase Two stabilizes (README already gestures at this direction).
10. **Make Monitor worker framework-dependent + ReadyToRun**. Since the runner has already deployed the .NET runtime for Awake/Settings on the same machine, Monitor doesn't need to be self-contained. Replace its `Common.SelfContained.props` import with:
    ```xml
    <PropertyGroup>
      <SelfContained>false</SelfContained>
      <PublishReadyToRun>true</PublishReadyToRun>
    </PropertyGroup>
    ```
    Or keep self-contained but enable `PublishTrimmed=true` + `TrimMode=partial`. As a UI-less console worker, Monitor is the best trimming candidate.
11. **Delete the source files behind every `<Compile Remove>`**. The ~30 ViewModels/Pages already removed in `Settings.UI` should be physically deleted, not hidden via `Remove`. This cleans search/diff/merge results and severs the transitive surface from 30+ pages referencing `LanguageModelProvider`, `ManagedTelemetry`, etc. Before deleting, add negative static tests in `BuildCompatibility.cs` ("AdvancedPastePage.xaml.cs MUST NOT exist").
12. **Trim `src/common/` projects**. `Kit.slnx` includes `CalculatorEngineCommon`, `FilePreviewCommon`, `Common.Search`, `UITestAutomation`, `PowerToys.ModuleContracts`, etc., which active modules (Awake/LightSwitch/Monitor) don't need. Audit each shared project for "who references me"; remove from `Kit.slnx` anything not transitively referenced by an active module/Settings/runner. `PowerToys.Settings.csproj` still lists `Common.Search` / `Common.UI` as hack references — these are the priority untangling targets.
13. **DSC and CmdPal are not in the active module set but are in slnx** (`dsc/v3/PowerToys.DSC` is also self-contained). If the current phase doesn't need DSC, drop the entire `dsc/` folder from `Kit.slnx` — keep the project files but don't build them.
14. **Rename `Trace::EventLaunch`'s ETW provider to `Kit`**. The GUID must change (to avoid collision with the official PowerToys provider), and `trace.cpp` empty stubs should become an explicit "do-not-register" branch so future contributors don't think telemetry is alive.
15. **`Kit.exe` runner still hard-codes `PowerToys.Settings.exe` / `PowerToys.QuickAccess.exe` paths** (`settings_window.cpp` / `quick_access_host.cpp`). Suggest renaming the executables via csproj `<AssemblyName>` to `Kit.Settings.exe` / `Kit.QuickAccess.exe`, consistent with `Kit.exe`. Module DLLs continue to use `PowerToys.*ModuleInterface.dll` to "prove" upstream ABI compatibility.

### C. Long-Term / Refactor

16. **Phase Two starts with a "Kit Module SDK" abstraction**. The three native interface DLLs (`MonitorModuleInterface.vcxproj` / `LightSwitchModuleInterface.vcxproj` / `AwakeModuleInterface.vcxproj`) duplicate Enable/Disable/Worker-launch/exit-event logic. Add a `Kit.ModuleInterface` static library under `src/common/` to share this code; each module declares only its `Key`, worker exe name, and custom-action handlers. This stops C++ copy-paste when adding modules 4 and 5.
17. **Monitor Worker → Settings progress channel** (already on the README "Next Stabilization Checklist #1"): use the existing named-pipe / `SettingsAPI` to report real scan progress instead of a UI timer. Combine this with #16: add `IModuleProgressReporter` to the SDK.
18. **Module bootstrap scaffolding**. Building on `tools/project_template/ModuleTemplate`, ship a `dotnet new kit-module --name Foo` template that auto-generates lib + worker + module-interface + settings page + tests + registration. Start with a PowerShell `tools/build/new-module.ps1` that atomically updates `Kit.slnx` / `KitKnownModules` / Settings nav / Home metadata in all four places. Promote to a proper template in Phase Two.
19. **Tiered publish modes**:
    - `Configuration=Release` → trimmed self-contained, no PDB shipped.
    - `Configuration=Dev` → framework-dependent, portable PDBs, satellite locales skipped.
    - `Configuration=Debug` → current shape.
    The current Debug/Release dichotomy forces local development to be either slow or 1 GB, with no middle tier.
20. **CI/local consistency**: extend `tools/build/build.ps1` with a `-Slim` flag that turns on items #1–#7. This lets a PR validate the slimmed configuration still passes the three-module regression suite without touching source.

## 5. Next Development Recommendations (after the README's Phase One Closeout)

1. **Finish Monitor worker → Settings real progress** (already named in the README). Either named pipe, or worker periodically writes a progress file with Settings file-watch. This is the last blocker before Monitor is "production-stable".
2. **Extend the LightSwitch PowerDisplay-compatibility unit test**. Today's test covers `GeneralSettings.Enabled.PowerDisplay` + `profiles.json` parsing. Add an end-to-end ViewModel test for "PowerDisplay settings absent → Light Switch page degrades without throwing".
3. **Static lint: `KitKnownModules` ↔ `Kit.slnx` BuildDependency consistency test**, to prevent half-registered new modules. In `BuildCompatibility.cs`, parse both slnx and main.cpp string sets and assert equivalence.
4. **First new Phase-Two module candidate**: with Monitor stable, the next module should be a **native-only, no-WinUI** small utility from PowerToys-main (Awake-tier). Builds confidence in the SDK abstraction (#16) without re-pulling WinAppSDK. Avoid `PowerRename` / `FileLocksmith` for now (they bring WinUI3).
5. **Documentation cadence**: README's "Stability Direction" and devdoc's "Next Stabilization Checklist" already form a good "single source of truth". After completing Section 4-A, immediately reflect the changes back into README's "Artifact Cleanup" and devdoc's "Build And Test Lessons" — so the next reviewer doesn't have to re-do the archaeology.

## 6. Suggested Execution Order

If picking up A-section incrementally:
1. Items A.1–A.3 (locale + PDB + OOBE) — three changes, PR-friendly, zero behavior change, ~ -250 MB. Do these first.
2. Items A.5–A.6 (drop LanguageModelProvider + delete AI detection) — together ~ -100 MB and remove a confusing dead code path.
3. Items A.7–A.8 (drop WPF in Common.UI + lock down trimming) — needs more validation, more risk.
4. After A is fully landed, evaluate B.10 (Monitor framework-dependent) and B.11 (delete `<Compile Remove>` source files) as the first structural cleanup.

Each item should land as its own PR with a `BuildCompatibility.cs` regression test where applicable, so the slimmed shape can't silently regress.
