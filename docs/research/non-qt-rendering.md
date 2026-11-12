# Rendering beyond Qt

## Question

How can the accepted Qt rendering reach GTK applications, Firefox-based browsers, Electron, and Flatpak packages?

## Repository constraints

Keep the accepted Qt result. The reference uses automatic monochrome hints, grayscale output, mild contrast, integral device-pixel origins, and linear-light blending. Font family, style, effective size, and background remain part of a comparison condition. Include regular, bold, italic, and bold italic.

The user named Firefox-based browsers first, followed by Flatpak applications such as Teams for Linux. These applications need their own rendering work. Using GTK for Linux integration does not make all application text use GTK's renderer.

Use private test profiles and libraries. Keep generated data on `/storage`. Do not change the user's browser profiles, Teams account data, desktop configuration, installed packages, or Flatpak overrides during comparisons. Debian 13 remains a delivery target. An application's exact engine and packaging matter in addition to the host distro.

## Options

| Approach | Reach | Limit |
| --- | --- | --- |
| Existing Fontconfig and browser controls | A useful baseline without rebuilding an engine | Does not express the complete accepted treatment |
| Port the treatment into each actual rendering engine | Can address rasterization, placement, and final composition together | Needs independent pixel checks and an existing-app test for each path |
| Replace host libraries and assume all applications follow | Some applications using those libraries | Misses bundled engines and sandbox runtimes |

Start with existing controls as a baseline, then port the missing behavior into the owner that draws the text. The rendering method is already selected; this is an integration investigation rather than a new rasterization algorithm.

## Evidence

### Installed application and library inventory

The following versions were read on the investigation machine. They are observations, not supported-version promises.

| Target | Installed version | Text path or remaining question |
| --- | --- | --- |
| System GTK 3 | 3.24.52 | Pango/Cairo text; establish the actual image or display-surface compositor |
| System GTK 4 | 4.22.4 | Cairo glyph generation plus separate GSK GPU placement and composition |
| System Pango / Cairo | 1.57.0 / 1.18.4 | Shared font and drawing components, with different consumers |
| Firefox | 160.0 | Mozilla font configuration, WebRender glyph rasterization, and final composition |
| Floorp | 12.21.1, Gecko 159.0.1 | Related Mozilla paths; validate the actual fork independently |
| Teams for Linux Flatpak | 2.28.0 | Bundled Electron 44.9.0 and Chromium 152.0.7977.167 |
| Teams Flatpak runtime | Freedesktop 25.08 | Separate runtime libraries inside the sandbox |

Firefox's installed source stamp is `d84e7a6936554efe26097d9d9b24a0e11330e630` from `mozilla-release`. Teams' Electron and Chromium versions were read from its installed binary with `ELECTRON_RUN_AS_NODE=1` and `process.versions`, inside its Flatpak sandbox. This did not start the Teams application or read account data. The installed app commit is `2ebbb9bbdf90b5fabf35fb35cfa274884cb5069325f3666b5beb55e53a2aecda`; its runtime commit is `08713ee4ce58fee0b8ff2f5bb58e511ff2009c4d72209270d2ddd01fb0336a04`.

### GTK 3 and GTK 4 need separate composition checks

PangoCairo creates Cairo font faces and draws glyph strings. Cairo's FreeType backend selects load flags and creates glyph surfaces. The final Cairo compositor still determines how those surfaces blend with the destination. [PangoCairo documentation](https://docs.gtk.org/PangoCairo/), [Pango 1.57.0 font implementation](https://github.com/GNOME/pango/blob/1.57.0/pango/pangocairo-fcfont.c).

GTK 4.22.4's GPU glyph cache draws glyphs through PangoCairo into an atlas. It also retains scale and quarter-pixel offsets. The node processor then positions cached glyphs and selects colorize or texture operations. Matching Cairo's glyph masks would not establish matching final GPU pixels. Forcing GTK 4's Cairo renderer is useful as a control, but does not prove default GPU coverage. [GTK glyph cache](https://github.com/GNOME/gtk/blob/4.22.4/gsk/gpu/gskgpucachedglyph.c), [GPU node processor](https://github.com/GNOME/gtk/blob/4.22.4/gsk/gpu/gskgpunodeprocessor.c), [renderer selection](https://docs.gtk.org/gtk4/running.html#environment-variables).

### Firefox controls do not reproduce the Qt treatment

The inspected Firefox source converts Fontconfig settings into WebRender font options. With antialiasing enabled, full hinting uses the normal target for grayscale text. The monochrome hint target is selected with monochrome output when antialiasing is disabled. That differs from Fontreal's monochrome hinting with grayscale output. [Installed Firefox source: font options](https://hg.mozilla.org/releases/mozilla-release/file/d84e7a6936554efe26097d9d9b24a0e11330e630/gfx/2d/ScaledFontFontconfig.cpp), [WebRender rasterizer](https://hg.mozilla.org/releases/mozilla-release/file/d84e7a6936554efe26097d9d9b24a0e11330e630/gfx/wr/wr_glyph_rasterizer/src/platform/unix/font.rs).

Firefox exposes `gfx.text.subpixel-position.force-disabled`, `gfx.webrender.enable-subpixel-aa`, `gfx.font_rendering.freetype.gamma`, and `gfx.font_rendering.freetype.enhanced_contrast`. Gamma `0` selects the sRGB transfer in its preblend lookup table. That table guesses the background from the foreground color and adjusts glyph coverage before composition. It does not read the actual destination behind each glyph. It therefore is not the same as background-aware linear blending. Mozilla's enhanced-contrast formula also differs from Fontreal's mild coverage ramp. [Installed Firefox preferences](https://hg.mozilla.org/releases/mozilla-release/file/d84e7a6936554efe26097d9d9b24a0e11330e630/modules/libpref/init/StaticPrefList.yaml), [preblend implementation](https://hg.mozilla.org/releases/mozilla-release/file/d84e7a6936554efe26097d9d9b24a0e11330e630/gfx/wr/wr_glyph_rasterizer/src/gamma_lut.rs).

The native-control baseline compares fresh stock profiles with full automatic hinting, grayscale output, and whole-pixel positioning, then adds Mozilla's sRGB preblend. It uses Firefox and Floorp, 100% and 125% requested browser scale, light/dark colors, three requested font families, and four styles. These are headless browser captures. They establish visible effects of existing controls; they do not establish a Fontreal port, hardware-renderer equivalence, or browser-toolbar coverage.

A pass-through trace observed actual `libxul` FreeType loads. Stock sampled loads used the light target; the full/gray controls used the normal target. The trace did not intercept the final WebRender raster calls, so it cannot attest the complete rendering path. Source evidence and final-image measurements remain separate.

The user preferred full/auto hints, grayscale, and whole-pixel positions in this baseline. Regular text still looked blurry, and the chosen controls suffered on white. Clearer bold and italic rows did not establish acceptance of regular text.

Browser controls and page text need separate observations. WebRender renders pages through its own pipeline. GTK integration alone cannot establish that result. [Mozilla rendering overview](https://firefox-source-docs.mozilla.org/gfx/RenderingOverview.html).

### Private FreeType isolates the missing mask treatment

The installed Mozilla binaries dynamically load system FreeType. A private library can therefore test the missing mask treatment before a complete Mozilla rebuild. The experiment builds unmodified and patched FreeType from the same authenticated Ubuntu `2.14.2+dfsg-1ubuntu0.2` source archives. Both preserve distro security patches and dynamic HarfBuzz.

The patch selects scalable, non-color TrueType raster requests only when `FONTREAL_FT_RENDERING=1`. It requests automatic monochrome hints, then renders the retained outline as grayscale. `FONTREAL_FT_CONTRAST=mild` applies the accepted 32..223 coverage ramp once. Delayed rasterization leaves Mozilla's outline translation in place. Repeated rendering does not apply the ramp again. Non-raster requests and excluded font types retain their original path. See the [experiment and commands](../experiments/browser-masks.md) and [FreeType load/render contract](https://freetype.org/freetype2/docs/reference/ft2-glyph_retrieval.html).

The public FreeType probe compares masks, bearings, advances, outline state, repeated rendering, and the next load with unmodified-source references. A test-only build reports the bitmap from the actual browser raster call. Browser loader mappings alone cannot prove that the changed path draws the captured text.

Actual Firefox windows in a nested KWin Wayland session establish a stronger result than CLI headless screenshots. The CLI screenshot path produced identical candidate/control pictures without final-raster observations. It is not the proof path for this experiment. The headed tests use Mozilla's local test protocol for geometry and repainting, then capture the real window separately. They keep the normal browser sandbox and disposable profiles. [Mozilla test transport](https://hg.mozilla.org/releases/mozilla-release/file/d84e7a6936554efe26097d9d9b24a0e11330e630/testing/marionette/client/marionette_driver/transport.py).

For the measured regular 15px Noto Sans glyphs on white, the private masks with Mozilla sRGB preblend match the independent mild/linear reference exactly. With gamma disabled, the same masks match mild/encoded instead. The colored-background control exposes a residual difference from actual-background linear blending. These observations do not promote Mozilla preblend to a general background-aware implementation. Browser chrome also needs its own coverage result.

The user prefers the private masks with sRGB preblend. Keep this as the explicit browser preview choice. The accepted Qt linear mode already uses the actual background and the same sRGB transfer. It does not need a guessed-background preblend to reproduce the white-background reference.

A matched comparison of Noto Sans Regular at 15px and 100%, black on white, finds exact mild/linear pixels for `mnogWV` in both the retained native Qt gallery and the actual Firefox capture. The user then reports no perceptible difference. This establishes equality for those glyphs and conditions only. It does not justify a change to the accepted Qt implementation or establish equality across other applications, fonts, scales, or palettes.

### Electron is another rendering engine

Teams for Linux wraps the Teams web application with Electron. Electron uses Chromium renderer processes for web content, alongside native integration in its main process. The next trace must establish the font backend used by this exact Electron build, including whether relevant font work is bundled. Do not assume replacing host Cairo or FreeType reaches it. [Teams package source](https://github.com/IsmaelMartinez/teams-for-linux/blob/v2.28.0/package.json), [Electron process model](https://www.electronjs.org/docs/latest/tutorial/process-model).

Use a local text fixture in a disposable Electron test context before opening Teams. Preserve account data and ordinary sandboxing. Compare document text, controls, styles, scaling, and foreground/background colors before claiming application support.

### Flatpak changes the delivery boundary

Flatpak supplies a runtime and allows applications to bundle different library versions. Teams' manifest starts its bundled executable through Zypak. A host Qt package change does not replace those components. [Flatpak runtimes and bundled libraries](https://docs.flatpak.org/en/latest/basic-concepts.html), [Teams Flatpak manifest](https://github.com/flathub/com.github.IsmaelMartinez.teams_for_linux/blob/master/com.github.IsmaelMartinez.teams_for_linux.yml).

Treat packaging separately from rendering. First prove the treatment in the engine. Then build against the exact runtime or bundled-engine revision and provide a separate opt-in launch. A Qt or GTK Flatpak runtime and a bundled Electron engine need distinct checks. Do not point a sandbox at arbitrary host libraries or install broad permanent overrides as a substitute for a matching build.

## Decision

Prioritize Firefox/Floorp, then Electron with the Teams Flatpak as its first application. Keep GTK 3, GTK 4 GPU composition, and Flatpak delivery as explicit work rather than claiming they follow from the Qt result. The [roadmap](../roadmap.md) owns their order and status.

For each engine, retain a stock control and prove font eligibility, monochrome hint target with grayscale masks, mild contrast, device-pixel placement, and final blending independently. Check noneligible fonts and ordinary drawing immediately after eligible text. Test real application output before deployment. Human comparison at native image size remains necessary.

## Rejected options

Do not call Mozilla's gamma preference the full Fontreal treatment. Do not treat GTK 4's Cairo fallback as default GPU support. Do not treat Flatpak as one universal renderer. Do not rebuild or replace the working host Qt libraries to fix an unrelated browser engine.

## Revisit when

Recheck the paths when a browser changes its font backend, a runtime changes version, or a target application bundles a different engine. Existing controls may reduce the patch needed, but a matching label or preference value is not a pixel oracle.

## Sources

Primary documentation and exact source links are attached to the claims above. Installed application metadata, independent FreeType references, and disposable browser captures supply the machine-specific observations. The private mask experiment does not establish a desktop deployment, hardware-renderer equivalence, Electron coverage, or Flatpak delivery.
