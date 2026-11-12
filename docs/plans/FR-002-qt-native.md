# First native Qt and KDE application test

## Outcome and authority


Launch the installed Konsole binary with an isolated Qt 6.10.2 build that reproduces the selected rendering. Provide stock, linear-blend, and encoded-blend launches for visual judgment. The test covers application text. KWin decorations remain a separate process and roadmap task.

The user requests a private GitHub repository, incremental commits and pushes, a roadmap for GNOME and Wine, conditional Windows 11 work, and continuation to the first real-world test. The repository and roadmap are independent documentation checkpoints. This specification owns FR-002 in [the roadmap](../roadmap.md).

The rendering requirements come from the user's feedback and the [controlled experiment](../experiments/freetype-comparison.md): automatic monochrome hinting, grayscale output, integral glyph origins, and an explicit choice between linear-light and encoded blending. Font and effective size affect the preferred blend. No automatic cutoff is established.

Base: `6c543fc` on `integration/qt-native`, branched from `main` at `038dd179a673`. One writer uses the existing checkout. The prior [experiment specification](freetype-comparison.md) remains the reference for its existing application. The new task promotes an isolated native Qt integration from deferred research into implementation. Desktop-wide installation remains deferred. No prior requirement is superseded.

## Product boundary and operating model


Support the reference Qt 6.10.2 environment, FreeType, installed Noto Sans and DejaVu Sans TrueType outlines, and Konsole. Build generated Qt sources and libraries under ignored `build/qt-native/`. Keep only the patch, build and launch tools, checks, and documentation in Git. Use the official Qt archive with SHA-256 `aeb78d29291a2b5fd53cb55950f8f5065b4978c25fb1d77f627d695ab9adf21e`.

The Qt FreeType engine, Fontconfig setup, and raster text composition compose the integration. The patch changes these owners only under an opt-in environment switch. Existing Qt shaping, font selection, non-text painting, and installed application code remain opaque dependencies. The reference renderer remains unchanged. GNOME, Wine, Windows, Qt Quick, KWin, global configuration, and package replacement are deferred.

One user and one writer use normal local files and separate test processes. A real application test uses private XDG configuration, cache, data, and state directories. Copy the current KDE general configuration into that test directory to retain the selected font and palette. Never write the original. Disable terminal background transparency for the initial opaque-background blend comparison.

The first test must be ready for human comparison. Readiness does not claim that the user accepted its appearance or that every application renderer is covered. Color fonts, non-TrueType outlines, transformed text, and transparent intermediate surfaces are not rendering targets of this first proof. Their masks retain Qt's existing selection. The opt-in A8 transfer profile is shared with other fonts that already request gamma correction, so their appearance is not certified by this TrueType comparison.

## Smallest implementation


Keep the upstream source outside Git. Add one version-specific patch for Qt's FreeType hinting and grayscale selection, fractional-position support, and A8 text transfer profile. Use Qt's existing sRGB transfer-table implementation for linear blending. Preserve the upstream path when the opt-in switch is absent. Keep blend selection explicit.

Add a reproducible private build command and a process-local launcher. The launcher selects installed Qt for stock mode and the private libraries for the two modified modes. Reject unsupported modes or a missing private build clearly. Add a Konsole preview command that uses its separate-process and built-in-profile options. Each launch receives its own private XDG directories.

Add a native Qt probe and one integration check. The probe paints normal QFont/QPainter text in an actual QWidget and captures its backing pixels. QRawFont masks supply supporting diagnostics. Independent direct FreeType calls and sRGB math supply the oracles. Retain one widget and its glyph cache through a repaint and a change of pen/background colors. Include the repeated-prefix text `lllm` and check the final `m`. The probe records the loaded Qt library. The integration check invokes the real launch tools and contrasts stock, private-without-opt-in, and the two modified choices.

## Boundary inventory


| ID | Source clause and required behavior | Contrast and oracle | Entry points and scenarios |
| --- | --- | --- | --- |
| B1 | The selected automatic mono hinting and gray edges must reach actual Qt text, including scaled text | Stock or inactive private Qt versus enabled Qt. Selected glyph masks match independent FreeType auto-mono/normal-raster calls at the actual device size. | Patched Qt through native probe and application launcher; S1, S5 |
| B2 | Pixel alignment takes priority over outline fidelity | Integral and half-pixel origins produce integral, unsplit masks. Native text agrees with the independently placed mask. Qt's integral destination convention can differ from the experiment's nearest-origin convention. | QPainter text through patched placement and raster path; S2 |
| B3 | The preferred blend changes with effective size and font | Linear and encoded modes keep masks equal but follow their respective independent composition formulas. Test both polarities. Allow at most one channel value of transfer-table rounding error. | Both launch choices through native Qt text composition; S3 |
| B4 | The experiment must remain isolated and allow stock comparison | Stock mode removes Fontreal's private-library entry and rendering switches, even when inherited. Modified modes load the private library. Inactive private Qt preserves stock probe output. Non-text painting stays equal. | Build/run tools and native probe; S4 |
| B5 | Continue until a real-world test is ready | The installed Konsole runs in a separate process with the private library and selected treatment. Its menu and terminal text are available for native-scale judgment. Stock is also launchable. | Konsole preview command; S5 |
| B6 | Preserve the user's normal application and desktop configuration | Each preview uses separate XDG roots and reads only a copy of KDE configuration. Existing configuration bytes stay unchanged. Closing the process ends its library selection. | Preview lifecycle from launch through normal close; S5 |

Incremental publication clauses map to the publication checkpoints. The roadmap clauses map to `docs/roadmap.md`. GNOME, Wine, and conditional Windows 11 implementation are deferred from this first application test. The +/- one-pixel transition is calibration context, not an automatic policy. Non-native LCD resolution is excluded. No source clause introduces desktop installation.

## Scenario Proof


| Scenario | Discriminator and minimal contrast | Composed production path and terminal oracle | Runnable check |
| --- | --- | --- | --- |
| S1 | Rendering switch off versus on, holding face and device size equal | Real launcher → selected Qt library → actual QWidget paintEvent with normal QFont/QPainter → widget capture, plus QRawFont diagnostics. Independent FreeType matches enabled l/m/n/o/g for both fonts. Stock differs in at least one case. Include 13px at 1, 10px at 1.5, 11px at 1.5, 13px at 1.25, and the adjacent 15px/16px pair at 1. Retain the widget through cached repaint. | `python3 tests/qt_native_test.py` |
| S2 | Origin phase 0 versus 0.5 at fixed size and face | Real launcher → Qt positioning → glyph raster → QPainter image. Both sides retain integral origins and match the independently placed mask, without a two-column split caused by phase. | Same integration check |
| S3 | Linear versus encoded blend, then light versus dark polarity and one opaque nonendpoint color pair | Real launcher → same cached Qt mask → A8 compositor → actual QWidget capture. Raw masks stay equal and every text pixel follows independent blend math within one value. Decode each input color before interpolation for linear mode. Use a partial pixel that rejects output-only conversion. Retain the same widget/font through `lllm`, a pen/background change, and cached repaint. Independently check every resulting text pixel, including the final m. A painted non-text color remains identical. | Same integration check |
| S4 | Stock launch from a clean environment versus a Fontreal-modified parent environment | Real launcher → child dynamic loader → probe metadata and image. Both stock cases load installed Qt and agree. Both modified choices load the private Qt. Direct private launch without the opt-in switch agrees with stock. Invalid choice and absent private build fail clearly. | Same integration check, plus source inspection of output boundaries |
| S5 | Stock versus both modified Konsole launches, each with distinct private state | Real preview command → configuration snapshot → real launcher → installed Konsole separate process → Qt glyph calls and mapped private library → visible window. Observe actual selected FreeType flags in the application. Exercise normal repaint or size interaction in both modified modes. Close the smoke tests normally and make sure that private directories are removed and original configuration bytes stay equal. | Integration check and real application smoke check, then `python3 tools/preview-konsole.py stock`, `python3 tools/preview-konsole.py linear`, and `python3 tools/preview-konsole.py encoded` for viewing |

The native probe reaches the real Qt owners. It does not replace them with the reference renderer. A diagnostic pass-through FreeType trace can observe application calls without changing them. It does not prove visual quality. The visible Konsole launch is the final human comparison surface.

Use device x origin 60 for the phase comparison. It converts to an exact integral logical origin at all selected scales. This avoids an unrelated one-pixel floor difference caused by Qt's logical 26.6 coordinate quantization. The half-device-pixel contrast remains between that origin and 60.5. The required result is integral masks under Qt's destination convention, not a replacement positioning algorithm.

Qt text shaping remains opaque. Use its normal QTextLayout glyph identities and positions for the repeated-text oracle, with QPainter's resolved font and documented logical-coordinate quantization. Check every requested ASCII glyph against its independent FreeType identity. Rasterize and blend every expected pixel independently. A per-character QFontMetrics sum is not an oracle for HarfBuzz layout. The separate independent cold logical advance check still detects shared-face size corruption.

Collection semantics: every selected font, size, glyph, origin, and palette case produces an output and independent check. No grouping or deduplication discards later cases. Empty case sets are not a supported interface. A preview retains only its child process and private paths. Normal process completion removes those paths. Concurrent windows use distinct paths. Fault recovery, hostile files, signals, and arbitrary Qt versions are outside this local proof.

## Atomic subtask and checks


FR-002 owns the Qt patch, private build, launch tools, native probe, direct checks, and user procedure as one proof boundary. The existing experiment stays unchanged. Build with `python3 tools/build-qt.py`, then `cmake --build build`. Run the scenario check above and the existing CTest suite. Retain generated private libraries for the pending visual test.

Before native correctness review, finalize substantive documentation and obtain fresh trace closure for B1 through B6. Review the complete FR-002 candidate against `6c543fc`. A clean review permits its local commit and authorized push. The roadmap can then record that the first test is ready. Subsequent visual calibration remains FR-003.

## Decision Log


Use an isolated Qt build because the installed Qt trace proves that Fontconfig alone chooses a different hinting target. The [KDE investigation](../research/kde-integration.md) records that evidence and relevant upstream owners.

Use the matching [official Qt source archive](https://download.qt.io/archive/qt/6.10/6.10.2/submodules/) and a local build. Qt documents [separate source and build directories](https://doc.qt.io/qt-6.10/linux-building.html). No new rendering algorithm or font format is needed, so the current task is framework integration rather than an open algorithm choice.

The private build must retain the installed platform plugins' X11 and accessibility interfaces. Extract the missing Ubuntu development headers under the generated build directory and require those Qt features explicitly. Installed runtime packages remain unchanged.

Keep public data symbols available for normal ELF lookup with GNU ld's [`--dynamic-list-data`](https://sourceware.org/binutils/docs/ld/Options.html#index-_002d_002ddynamic_002dlist_002ddata). Konsole uses a copy relocation for `QCoreApplication::self`. Binding Qt's own reference locally leaves the application/plugin copy null. This linker choice preserves the installed binary's data-symbol contract without changing Qt source or disabling the existing function-binding optimization. A real Konsole launch and its normal window actions supply the direct regression check.

For B1 at fractional display scale, Qt's native glyph path must request the effective FreeType character size before hinting. Apply this only to enabled eligible fonts under positive uniform scale. Keep the original transformed glyph-cache key, remove the absorbed display scale from the outline matrix, and record the actual face size in existing shared-face bookkeeping. The next `lockFace` then restores logical size for metrics. Preserve other transforms and the engine's existing matrix. S1 includes a cold logical `W` advance request immediately after a scaled `l` capture, checked against independent logical-size FreeType. Qt's existing `shouldUseDesignMetrics` selector permits hinted or design advances. Both independent logical-size values are valid, and a stale effective-size advance must match neither. Then paint `W` through a new scaled cache miss before the existing cached/recolored `lllm` checks. A fresh two-phase scale preflight accepts this bounded correction without a new behavioral boundary.

Use Qt's existing piecewise sRGB transfer table. Its finite precision must pass the independent pixel comparison. Keep the blend manual because the user reports font-dependent transitions and has not accepted a universal cutoff.

Use Konsole's built-in profile and a copied KDE general configuration in separate XDG roots. This makes a real application test observable without persisting test choices into the user's normal profile. KWin title text remains outside this process.

The preview exposes `--family`, `--pixels`, and `--scale` for the two named sans fonts. Set the private KDE general font with an explicit Qt pixel-size descriptor. The UI's effective size is `pixels × scale` on the current scale-1 display. Compare 15px and 16px at scale 1 for each family, holding the font and size fixed between the two blends. Terminal text retains an appropriate fixed-pitch font. The procedure identifies UI text separately from terminal font selection and KWin title text.

The two-phase planning challenge requires actual widget captures, cached repaint with changed colors, nonendpoint colors, both real-app blend launches, and adjacent-size instructions. These are accepted in S1/S3/S5. No contract gap remains.
