# Repeat app-specific scenarios

Run commands from the repository root as your normal desktop user. Keep the checkout and active artifacts in place while Fontreal is enabled. Put `build` and `results` on the chosen build volume before building. All commands below use the existing app identity and ordinary sandbox.

The guides linked below own the full commands and prerequisites. This page identifies which recipe to follow and what establishes success. A configured hook, loaded library, or successful engine fixture alone does not prove that a live application uses the selected renderer.

## Choose the integration

| Application or system | Supported recipe | Current rendering boundary |
| --- | --- | --- |
| Firefox | [Working-profile browser recipe](experiments/browser-masks.md#enable-the-working-profile) | Selected native-normal coverage and weighted stems in supported native installations |
| Floorp | [Working-profile browser recipe](experiments/browser-masks.md#enable-the-working-profile) | Same selected method, separately enabled and checked |
| Teams for Linux Flatpak | [Application qualification and activation](experiments/chromium-flatpak.md#teams-application-qualification) | Exact Teams 2.28.0 / Electron 44.9.0 / Chromium 152.0.7977.167 route only |
| System Qt 6, KDE and KWin | [Native package and session recipe](build-system.md) | Earlier raw profile. The selected weighted package port remains separate work |
| Edge and other Chromium browsers | [Owner inventory](experiments/chromium-flatpak.md#inspect-and-build) | Not qualified. Teams engine results do not establish browser support |
| Bitwarden Flatpak | Same owner inventory | Not qualified. Its engine and process-isolation wrapper require separate checks |
| Telegram Flatpak | Same owner inventory | Not qualified. Its bundled Qt and runtime FreeType require separate checks |
| Other GTK/GNOME apps, Qt 5, Wine and Windows | [Roadmap](roadmap.md) | No selected activation recipe yet |

Match the exact supported revisions in each guide. Another version, package format, architecture, runtime or bundled toolkit requires its own qualification. Do not apply a Teams override to another Electron application.

## Firefox and Floorp: original working profiles

Follow [Requirements and build](experiments/browser-masks.md#requirements-and-build) before activation. Enable each browser separately:

```sh
python3 -B tools/browser.py enable firefox
python3 -B tools/browser.py enable floorp
```

Fully quit and reopen each browser normally. Run the corresponding `status` command from the [browser guide](experiments/browser-masks.md#enable-the-working-profile). Make sure that the intended original profile is selected and no parent still needs a restart.

For automated reproduction, run [Repeat the checks](experiments/browser-masks.md#repeat-the-checks). Component checks establish masks and geometry. The actual browser checks establish placement and final pixels. The delivery check establishes ordinary launch routing, original preferences and reversal. Keep each report with its exact build record.

For an untreated Nimbus Sans request, follow the [CFF versus Type 1 diagnosis](experiments/browser-masks.md#when-nimbus-sans-looks-untreated). That optional font-selection rule is separate from activation and has its own removal step.

After an incompatible browser or FreeType update, the wrapper starts the installed browser without the private library. Re-enable only when the matching build route supports the new revisions. To restore original preferences and hooks, fully quit the browser and use [Restore the original rendering](experiments/browser-masks.md#restore-the-original-rendering).

## Teams: engine, real app, original data, update, activation

Follow the [engine guide](experiments/chromium-flatpak.md) in this order:

1. Run the owner inventory and native application startup prerequisite.
2. Build the stock and passive engine pair. Run `stock-fixture`.
3. Build the selected engine pair. Save the printed selected `build.json` as `C2_BUILD_JSON`.
4. Run `chromium_selected_test.py` with that exact selected record.
5. Assemble the application with `build-chromium-delivery.py`. Save its different application record as `TEAMS_BUILD_JSON`.
6. Run `actual-app` and `lifecycle`. Restore the stock instance, prepare the private update fixture, then run `update-cycle`. Use the same `C2_BUILD_JSON` throughout.
7. Enable Teams with `TEAMS_BUILD_JSON`, then fully quit and reopen normally.

The [guide](experiments/chromium-flatpak.md#teams-application-qualification) contains the exact commands. Replace record placeholders with paths printed by the corresponding builder. Never use an assumed newest directory or another machine's record. Cached artifacts must still match their recorded sources, tools and payload hashes.

The three application checks establish different results:

| Named check | Required observation | Data and final state |
| --- | --- | --- |
| `actual-app` | Original local Join Meeting dialog. Unsent W, WW and WWg. Exact stock/passive and selected normal/trace captures, independent masks, later glyph and repaint checks | Temporary comparison data. No message or account change |
| `lifecycle` | Ordinary desktop and command routes, later renderers, native escape, regenerated portal autostart, disable and stock reopen | Original working data. Normal quit/reopen. Original host stock restored |
| `update-cycle` | Genuine official package update invalidates the old qualification through the native autostart route | Private installation and private data. Temporary setup removed. Original host stock restored |

Each check must exit zero and produce `report.json` with `passed: true` below `results/chromium-delivery`. Inspect the named subresults too. A previous run's success does not certify a changed input. Original-data checks reopen the working application, so run them during an interval without unsaved work or competing launches. Leave the comparison dialog undisturbed during captures.

Follow [Enable Teams for daily use](experiments/chromium-flatpak.md#enable-teams-for-daily-use) after the checks. Status must report `enabled: true` and `compatibility: null`. A complete normal restart is required. For recovery, the same section gives the absolute native launch command and owned-hook removal commands.

## Native KDE: packages and fresh sessions

Use [Build for the running system](build-system.md) for the earlier raw profile. Its package tests and disposable Plasma session tests are required before installation. Do not use that workflow to claim selected weighted-stem deployment.

Keep the entire verified bundle, official rollback packages, deployment manifest and session reports together. The guide distinguishes container package checks, disposable VM sessions, browser-launched Qt helpers, host installation and recovery. Run destructive session checks only inside the marked disposable VM.

After host activation, log out and back in normally. Run `fontreal-session status` in the new session. A preference for the next login does not establish the values inherited by the current session. Retain the exact predecessor bundle when testing an upgrade from an existing Fontreal installation.

## Record a reproducible comparison

Record the Git commit, OS, architecture, application package and runtime revisions, build record, named command, exit status and result directory. For a visible issue, also record the font file and format, style, point size, DPI, display scale, zoom and background. Keep original lossless images at one image pixel per display pixel.

Compare the same text and UI region under the same conditions. Keep stock and selected captures separate from enlarged pixel grids. Do not rescale or sharpen a capture before comparing it. Preserve independent reference results and exact artifact hashes with local evidence.

Before publishing evidence, remove account text and machine-specific paths from public copies. Follow [Contributing](../CONTRIBUTING.md) for portable documentation and images. Keep private result records local. Do not redistribute installed fonts or the stock engine baselines with incomplete notices.
