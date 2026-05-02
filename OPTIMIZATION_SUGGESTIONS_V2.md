# Kit Optimization Suggestions — V2

Re-review after the codex pass. Compares state against `OPTIMIZATION_SUGGESTIONS.md` (V1) and the current build output at `x64/1.0.2 beta1`.

## 0. Headline Numbers

| Snapshot | x64 size | Active version dir | Notes |
|---|---|---|---|
| Before V1 (`1.0.1`) | 1003 MB | 1003 MB | baseline |
| After codex (`1.0.2 beta1`) | 794 MB | 794 MB | **−209 MB / −20.8 %** |
| `x64/` total on disk | 4.0 GB | n/a | `1.0.0` 1003 MB + `1.0.1` 1003 MB + `1.0.2 beta1` 794 MB + `Debug` 1.2 GB |

The runtime drop is real (PDB elimination + locale satellite trim + LanguageModelProvider removal). The on-disk total grew because old version dirs are not auto-cleaned.

## 1. What V1 Items Codex Applied

Verified by reading `Directory.Build.props`, `Directory.Build.targets`, `Cpp.Build.props`, `PowerToys.Settings.csproj`, `Kit.slnx`, and `BuildCompatibility.cs`.

| V1 item | Status | Where | Test guard |
|---|---|---|---|
| A.1 SatelliteResourceLanguages=en-US (csproj) | ✅ | [Directory.Build.props:81](src/kit/Directory.Build.props#L81) | `ReleaseBuildShouldKeepSlimPublishDefaults` |
| A.1+ Post-build delete of stray locale dirs | ✅ (new) | [Directory.Build.targets:28-37](src/kit/Directory.Build.targets#L28-L37) — `KitRemoveNonEnglishSatelliteDirsFromCsprojOutput` enumerates 83 langs | same test |
| A.2 csproj DebugType=none / DebugSymbols=false | ✅ | [Directory.Build.props:84-87](src/kit/Directory.Build.props#L84-L87) + [Directory.Build.targets:13-16](src/kit/Directory.Build.targets#L13-L16) (CsWinRT was reverting it) | same test |
| A.2+ Post-build delete of stray PDBs | ✅ (new) | [Directory.Build.targets:18-26](src/kit/Directory.Build.targets#L18-L26) — `KitRemoveReleasePdbsFromCsprojOutput` | same test |
| A.2+ C++ Release: no debug info, no PDB | ✅ (new) | [Directory.Build.targets:39-46](src/kit/Directory.Build.targets#L39-L46) — `<DebugInformationFormat>None</DebugInformationFormat>` + `<GenerateDebugInformation>false</GenerateDebugInformation>` | same test |
| A.3 Stop publishing OOBE assets | ✅ (smarter) | [PowerToys.Settings.csproj:126,133](src/kit/src/settings-ui/Settings.UI/PowerToys.Settings.csproj#L126) — `<Content Remove>` + `<None Remove>` keep PNGs on disk for upstream-merge cleanliness, but exclude from publish | `KitSettingsShouldNotPublishInactiveOobeAssets` |
| A.5 Drop LanguageModelProvider | ✅ | Removed from Kit.slnx, Settings.UI.slnf, Settings.UI csproj ProjectReferences; FoundryLocalModelPicker xaml/cs `<Compile/Page Remove>` | `KitSettingsShouldNotBuildAdvancedPasteLanguageModelProvider` |
| .nuget-cache / .nuget-packages / .nuget-appdata gitignored | ✅ (new beyond V1) | `.gitignore` now covers all three local caches | `KitLocalPackageCachesShouldStayIgnored` |
| B.15 Rename runner exe to Kit.exe + path/registry/fallbacks | ✅ (new beyond V1) | `Kit.vcxproj`, `RunnerHelper.cs`, `PowerToysPathResolver.cs` | `KitRunnerExecutableShouldBePrimaryNameWithPowerToysFallbacks` |
| B.15+ Rename solution to Kit.slnx + project to Kit.vcxproj | ✅ (new beyond V1) | slnx + vcxproj rename | `KitMainSolutionAndRunnerProjectShouldUseKitNames` |
| Per-process singletons → Kit names | ✅ (new beyond V1) | `KIT_MSI_MUTEX_NAME`, `KitTrayIconWindow`, scheduler folder `\Kit`, named events (`KitAwakeExitEvent`, `KitMonitorExitEvent`, `Kit-LightSwitch-ToggleEvent`, `KitRunnerTerminateSettingsEvent`), pipe prefixes (`kit_runner_`, `kit_settings_`, `kit_quick_access_*`) | `KitRuntimeSingletonsShouldNotSharePowerToysGlobals`, `KitBundledRuntimeEventsShouldUseKitNames`, `KitRuntimePipePrefixesShouldUseKitNames`, `KitStartupTaskShouldUseKitSchedulerFolder` |
| XAML `x:Name` for Release backing fields | ✅ (new beyond V1) | AwakePage, GeneralPage | `SettingsXamlNamedElementsShouldUseXNameForReleaseGeneratedFields` |

The regression-test discipline is the standout improvement. Almost every meaningful change has a `BuildCompatibility.cs` assertion against the underlying file content. Future merges from PowerToys-main can't silently undo a slim setting without a red test. Keep this pattern.

## 2. What Codex Deliberately Left Differently

- **A.6 ImageResizer AI detection**: V1 wanted full removal. Codex kept the code but left it gated behind `is_image_resizer_registered_for_kit()` (false today, since ImageResizer is not in `KitKnownModules`). A new test (`KitRunnerShouldOnlyRunImageResizerAiDetectionWhenImageResizerIsActive`) explicitly asserts the guard exists. This is a defensible call: the gate is cheap, the function is dead until ImageResizer is ever added back, and removing it would create an upstream-merge conflict. V1's "delete `ai_detection.h`" recommendation should be **withdrawn**. Re-frame as: "make sure no code path can call `DetectAiCapabilitiesAsync` from a non-Kit module". Today the only call sites are `runner/main.cpp:263` (gated) and `general_settings.cpp` (settings-changed reapply) — verify the second site is also gated.
- **A.3 OOBE PNGs**: V1 said "delete files". Codex chose `<Content Remove>`/`<None Remove>` so the 26 MB stays on disk for upstream-merge sanity but doesn't ship. Reasonable for a self-use fork that still rebases on PowerToys-main.

## 3. What V1 Items Were NOT Applied (Re-Prioritized)

Sorted by current impact on the 794 MB number (and on-disk noise):

| V1 item | Estimated saving | Reason it matters now | Priority |
|---|---|---|---|
| A.4 Clean old version dirs | **−2.0 GB on disk** (1.0.0=1003 MB + 1.0.1=1003 MB) | Each `Version.props` bump leaves the previous tree behind. Confusion risk: stale 1.0.1 binaries could be loaded if a tool walks `x64/` instead of using the active version dir. | **High** |
| A.7 Drop `<UseWPF>`/`<UseWindowsForms>` from Common.UI | **~−40 MB** | `Common.UI.csproj:7-8` still has both on. Output still ships `PresentationFramework.dll` (16M), `PresentationCore.dll` (8.3M), `System.Windows.Forms.dll` (14M), `WindowsBase.dll`, `PresentationFramework.Aero*.dll`. The "DLL version alignment hack" comment may be obsolete with the slim publish. | **High** |
| A.8 Trimmer roots / runtime config | **~−20-50 MB** if combined with #A.7 | After A.7, `<TrimmerRootAssembly Include="...active modules..."/>` plus `<PublishTrimmed>partial</PublishTrimmed>` on Settings would lock down what re-pulls. | Medium |
| B.10 Monitor framework-dependent | **~−40 MB**, only in 1.0.2 dir | `PowerToys.Monitor.exe` is a headless CLI — it gets its own `Monitor.deps.json` and pulls .NET runtime DLLs. Since runner already deploys .NET on the same machine, change Monitor to `SelfContained=false` (or trim heavily). | Medium |
| B.11 Delete files behind `<Compile Remove>` / `<Page Remove>` | 0 MB binary; **−109 dead source-tree entries** | Codex went **further**: 62 `<Compile Remove>` + 34 `<Page Remove>` + 13 `<None Remove>` = 109 rules in `PowerToys.Settings.csproj`. `Settings.UI/SettingsXAML/Views/*.xaml.cs` still has 37 files on disk while ~30 are excluded. The cost is no longer hypothetical — search/grep/blame return dead code constantly. | **High (DX)** |
| B.12 Trim unused `src/common/*` projects from Kit.slnx | ~unknown, mostly DX | `CalculatorEngineCommon`, `FilePreviewCommon`, `Common.Search`, `UITestAutomation`, `PowerToys.ModuleContracts` still in slnx. None are transitively referenced by Awake/LightSwitch/Monitor/runner. | Medium |
| B.13 Drop DSC from slnx | minor binary, real DX | `dsc/v3/PowerToys.DSC` still in slnx (51 projects total). If DSC is not on the active surface, exclude. | Medium |
| B.14 Rename ETW provider GUID + `Trace::RegisterProvider` to Kit | 0 MB | Currently `trace.cpp` is empty stubs but provider GUID still inherits PowerToys identity. Cleanup item, not a blocker. | Low |

## 4. New Issues Surfaced By V2 Review

These weren't in V1 because PDBs (165 MB) were the dominant noise. With PDBs gone, the next layer is visible.

### N1. **180 MB of `.lib` files shipping to runtime output** ⚠ Biggest remaining waste

`x64/1.0.2 beta1/` contains 22 static-library archive files totaling ~182 MB:

```
40 MB  BackgroundActivator.lib
38 MB  spdlog.lib
34 MB  Notifications.lib
21 MB  SettingsAPI.lib
18 MB  logger.lib
14 MB  Themes.lib
14 MB  EtwTrace.lib
4.5 MB Display.lib
2.8 MB Version.lib
1.7 MB COMUtils.lib
... + 12 small .lib (the import libs for the module-interface DLLs, ~2 KB each)
```

Root cause: every `ConfigurationType=StaticLibrary` `.vcxproj` under `src/common/*` has `<OutDir>$(RepoRoot)$(Platform)\$(Configuration)\</OutDir>` (e.g., [logger.vcxproj](src/kit/src/common/logger/logger.vcxproj)). The shared OutDir is needed so downstream linkers find the `.lib`, but it co-locates the `.lib` with the runtime EXE/DLL output. `.lib` files are link-time only; they are never read by the running process.

**Fix options (rank: B is least disruptive):**

A. Redirect static libs to a sibling dir:
```xml
<!-- Cpp.Build.props or per-project for ConfigurationType=StaticLibrary -->
<PropertyGroup Condition="'$(ConfigurationType)' == 'StaticLibrary'">
  <OutDir>$(RepoRoot)$(Platform)\$(Configuration)\lib\</OutDir>
</PropertyGroup>
```
Then update consumer projects' `<AdditionalLibraryDirectories>` to include `$(RepoRoot)$(Platform)\$(Configuration)\lib\`. Cleanest, but touches all consumers.

B. Add a post-build target that prunes `.lib`/`.exp`/`.lib.lastcodeanalysissucceeded` from the runtime tree (mirror of the existing `KitRemoveReleasePdbsFromCsprojOutput`). Runs on the runner project (`Kit.vcxproj`) after Build. Lowest disruption:
```xml
<Target Name="KitRemoveStaticLibArtifactsFromRuntimeOutput"
        AfterTargets="Build"
        Condition="'$(Configuration)' == 'Release' and '$(MSBuildProjectName)' == 'Kit'">
  <ItemGroup>
    <KitStaticLibArtifacts Include="$(OutDir)*.lib;$(OutDir)*.exp;$(OutDir)*.lib.lastcodeanalysissucceeded" />
    <!-- Don't delete the small import .lib for module interface DLLs -->
    <KitStaticLibArtifacts Remove="$(OutDir)PowerToys.*ModuleInterface.lib" />
    <KitStaticLibArtifacts Remove="$(OutDir)PowerToys.GPOWrapper.lib" />
    <KitStaticLibArtifacts Remove="$(OutDir)PowerToys.Interop.lib" />
    <KitStaticLibArtifacts Remove="$(OutDir)PowerToys.BackgroundActivatorDLL.lib" />
  </ItemGroup>
  <Delete Files="@(KitStaticLibArtifacts)" TreatErrorsAsWarnings="true" />
</Target>
```
Validate: after build, the runtime trio (`Kit.exe`, `WinUI3Apps\PowerToys.Settings.exe`, `WinUI3Apps\PowerToys.QuickAccess.exe`) still launches.

C. Per-project `<TargetExt>` redirect — not recommended; breaks upstream merge.

**Estimated saving: ~180 MB** (from 794 MB → ~614 MB).

### N2. Old version dirs accumulating (`x64/1.0.0`, `x64/1.0.1` = 2.0 GB)

`Version.props` bumps to `1.0.2 beta1` produce a new sibling dir. Previous trees are never cleaned. Add to `Directory.Build.targets`:

```xml
<Target Name="KitCleanStaleVersionedOutputDirs"
        BeforeTargets="Build"
        Condition="'$(MSBuildProjectName)' == 'Kit' and '$(Configuration)' == 'Release'">
  <ItemGroup>
    <KitStaleVersionDirs Include="$([System.IO.Directory]::GetDirectories('$(RepoRoot)$(Platform)'))"
                         Exclude="$(RepoRoot)$(Platform)\$(Version)$(_DevSuffix);$(RepoRoot)$(Platform)\Debug" />
  </ItemGroup>
  <RemoveDir Directories="@(KitStaleVersionDirs)" Condition="'@(KitStaleVersionDirs)' != ''" />
</Target>
```
(`_DevSuffix` is `' ' + DevEnvironment` when `$(DevEnvironment)` != ''.) Test it manually first — getting the active dir name wrong wipes the current build.

Lower-risk alternative: a tools/build/clean-stale-versions.ps1 that the developer runs deliberately, plus a `BuildCompatibility` test asserting only one current version dir exists when running from a clean state.

### N3. `<Compile Remove>` proliferation now blocks DX

109 Remove rules in [PowerToys.Settings.csproj](src/kit/src/settings-ui/Settings.UI/PowerToys.Settings.csproj). Real cost today:

- Settings.UI/SettingsXAML/Views/*.xaml.cs → 37 files; ~30 excluded.
- Settings.UI/ViewModels/*.cs → many `*VewModel.cs` excluded by wildcard like `<Compile Remove="ViewModels\AdvancedPaste*.cs" />`.
- Grep for "AdvancedPasteViewModel" returns hits in dead files. New contributors waste cycles reading them.
- Upstream-merge conflicts always include 30+ files that we'll just re-`<Compile Remove>` again.

Recommendation: **physically delete the source files, then rely on regression tests to keep them gone.** Codex already created the test pattern — extend it:

```csharp
[TestMethod]
public void KitSettingsMustNotKeepInactiveModuleSourceFiles()
{
    string[] inactiveSources = new[] {
        "AdvancedPasteViewModel.cs",
        "AlwaysOnTopViewModel.cs",
        "FancyZonesViewModel.cs",
        // ...
        "AdvancedPastePage.xaml.cs",
        "FancyZonesPage.xaml.cs",
        // ...
    };
    foreach (var name in inactiveSources)
    {
        var matches = Directory.GetFiles(SettingsUiRoot, name, SearchOption.AllDirectories);
        Assert.AreEqual(0, matches.Length, $"Inactive source file {name} should be deleted, not <Compile Remove>'d.");
    }
}
```
Then drop the corresponding `<Compile Remove>` entries — they become unreachable when the file is gone.

A reasonable batch: delete in groups of "module + its viewmodels + its pages + its OOBE views + its converters". 8–10 modules × 3–5 files each = ~30–50 files per PR. Each PR adds a test and removes the `<Compile Remove>` rules for that module.

### N4. Settings.UI references to removed modules in code (compile-time risk)

[OobeWindow.xaml.cs:86-107](src/kit/src/settings-ui/Settings.UI/SettingsXAML/OobeWindow.xaml.cs#L86) still has `case "AdvancedPaste": NavigationFrame.Navigate(typeof(OobeAdvancedPaste));` etc. for AdvancedPaste, FancyZones, MouseUtils, MouseWithoutBorders, etc. — modules that aren't in Kit. Either:
- These `Oobe<Module>` types still compile (because `<Page Remove>` may not be removing them, or they live elsewhere) — verify with a clean Release build.
- Or the file is excluded too — search confirms `OobeWindow.xaml.cs` exists on disk; if it's compiled, those `typeof()` references must resolve.

When OOBE is excised in a future phase, this switch should reduce to `case "Awake"`/`"LightSwitch"`/`"Monitor"` only. Add a regression test for the navigation list.

### N5. Cpp.Build.props branch leaves Debug Release-PDB hybrid

`Cpp.Build.props:90` sets `<GenerateDebugInformation>true</GenerateDebugInformation>` unconditionally for some configs, then [Directory.Build.targets:43-45](src/kit/Directory.Build.targets#L43-L45) overrides it for Release. The override sequence relies on `Directory.Build.targets` running after the project file. For C++ this is generally true (ItemDefinitionGroup applies last), but it's fragile — a per-project `<Link>` block in a vcxproj would override the targets file. Recommend pinning it inside `Cpp.Build.props` directly under a Release condition, so the Release intent isn't split across files:

```xml
<ItemDefinitionGroup Condition="'$(Configuration)' == 'Release'">
  <ClCompile><DebugInformationFormat>None</DebugInformationFormat></ClCompile>
  <Link><GenerateDebugInformation>false</GenerateDebugInformation></Link>
</ItemDefinitionGroup>
```

### N6. 83 root-level locale dirs from C++/WinAppSDK runtime (3.6 MB)

The csproj-side trim doesn't catch these — they're satellite dirs created by the WindowsAppSDK manifest copy (or per-architecture loc resources from native DLLs). Total is small (~3.6 MB), but it's noise in the runtime tree.

`KitRemoveNonEnglishSatelliteDirsFromCsprojOutput` runs only for csproj targets. Either:
- Add a parallel target that runs against the runner output dir (after the Kit C++ build), or
- Extend the existing target to run for the active version dir.

Low priority; the 180 MB `.lib` cleanup is 50× more impactful.

## 5. Recommended PR Order (V2)

Rebuild with the slim configuration first to confirm the 794 MB number, then tackle in this order:

1. **PR-1: Static-lib pruning (N1).** Add `KitRemoveStaticLibArtifactsFromRuntimeOutput` post-build. Add test. Validate runtime trio launches. Expected: −180 MB → ~614 MB. ★ highest ROI single PR.
2. **PR-2: Drop WPF/WinForms in Common.UI (V1 A.7).** Set both to `false`, validate Settings UI loads (especially custom controls in Settings.UI.Controls). Expected: −30-40 MB.
3. **PR-3: Stale version dir cleanup (N2).** Either pre-build target or a manual `tools/build/clean-stale-versions.ps1`. Saves 2 GB **on disk only**, not in the active runtime. Do this before PR-2 so the size telemetry is honest.
4. **PR-4 to PR-Nn: Source-tree purge (N3).** One PR per module group — delete files, drop `<Compile Remove>` entries, add a `KitSettingsMustNotKeep<Module>SourceFiles` regression test. Expect 4–8 PRs.
5. **PR after settled: Trim slnx (B.12, B.13).** Remove unused `src/common/*` and `dsc/*` projects from `Kit.slnx`. Validates by building only `Kit.slnx` from a clean tree.
6. **PR after trim: Monitor framework-dependent (B.10).** Set `SelfContained=false` + `PublishReadyToRun=true` for `PowerToys.Monitor.csproj`. Validates by `--scan-once` + worker-launched lifetime tests.

After PR-1 + PR-2 + PR-3, runtime should be ~580 MB and `x64/` total around 1.3 GB instead of 4.0 GB.

## 6. Forward-Looking Recommendations (post-slim)

1. **Single-source manifest for active modules.** Today `KitKnownModules` (runner main.cpp), Kit.slnx BuildDependency, Settings nav dictionary, Home `KitDashboardModules`, `BuildCompatibility.cs` — five places. Codex's regression-test layer means "wrong" is caught at build time, but "have to update five places" is still real friction. A `KitModules.json` or T4-driven `KitModules.g.cs` + native equivalent is the next stability beat.

2. **Module SDK starter.** Three module-interface DLLs (Awake/LightSwitch/Monitor) duplicate Enable/Disable/exit-event pattern in C++. Refactor into `src/common/Kit.ModuleInterface` static lib so a fourth module (and beyond) declares only `Key`, `WorkerExeName`, and custom-action handlers.

3. **Tiered configurations.** Today: Debug (1.2 GB) or Release (794 MB → 580 MB after PR-1/2). Add `Dev`: framework-dependent, portable PDBs, satellite trim on. Useful for fast iteration without losing the slim defaults.

4. **Test the actual binary, not just the props.** `BuildCompatibility.cs` asserts that strings are present in source files. Add one assertion that, after Release build, the active version dir does not contain `.lib`, `.pdb`, `*.Foundry*.dll`, or non-English locale dirs. This catches the case where the right knob is set but transitive packages still drag artifacts in.

5. **Runner C++ "module loaded" dashboard.** Now that singletons/pipes/events are Kit-named, add a `--list-modules` CLI to `Kit.exe` that prints loaded module DLLs + worker PIDs. Useful for the second-machine comparison workflow described in `README.md` "self-use, compared against installed PowerToys".

6. **Documentation sync after PR-1.** README's "Recent Release Build Regression" section should grow a "Slim Publish" subsection once PR-1/PR-2 land — listing the post-build targets and the tests that guard them. Keeps the codex-style discipline visible to future reviewers.

## 7. What Not To Do

- Do not blanket-delete `<Compile Remove>` rules without a regression test for the deletion. The rules are protecting against upstream-merge re-introduction; the test must replace that protection.
- Do not change `OutDir` for `StaticLibrary` projects without auditing every consumer's `<AdditionalLibraryDirectories>`. PR-1's post-build delete is the safer path.
- Do not attempt to remove `ai_detection.h` and the `DetectAiCapabilitiesAsync` function. The codex test specifically asserts they remain — the gating test (`KitRunnerShouldOnlyRunImageResizerAiDetectionWhenImageResizerIsActive`) is now a contract.
- Do not rename `PowerToys.AwakeModuleInterface.dll` etc. to `Kit.*`. The whole compatibility model depends on these names matching upstream.

## 8. Quick Status Snapshot

```
V1 items applied:        7 / 8 in Section A, plus 4 new beyond V1
Build size:              1003 MB → 794 MB (−21 %)
On-disk x64 total:        4.0 GB (3 version dirs + Debug)
Tests in BuildCompatibility.cs: 19 (was 3 in V1)
Top remaining waste:     180 MB of .lib files in runtime output
Top DX waste:            109 <Compile/Page/None Remove> rules + ~30 dead .xaml.cs files
```

The trajectory is good. The codex pass got the easy 200 MB and added a strong regression-test discipline. The next 200 MB is one focused PR (#PR-1). The 2 GB on disk is one chore PR (#PR-3). After those two, the project is in healthy shape for Phase Two module work.
