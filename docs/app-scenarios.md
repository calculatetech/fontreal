# Repeat app-specific scenarios

Run commands from the repository root as your normal desktop user. Keep the checkout and active artifacts in place while Fontreal is enabled. Put `build` and `results` on the chosen build volume before building. All commands below use the existing app identity and ordinary sandbox.

The guides linked below own the full commands and prerequisites. Follow the [test policy](../CONTRIBUTING.md#when-to-run-tests) to distinguish development checks from routine deployment. A configured hook or loaded library alone does not prove that a live application uses the selected renderer.

## Choose the integration

| Application or system | Supported recipe | Current rendering boundary |
| --- | --- | --- |
| Firefox | [Working-profile browser recipe](experiments/browser-masks.md#enable-the-working-profile) | Selected native-normal coverage and weighted stems in supported native installations |
| Floorp | [Working-profile browser recipe](experiments/browser-masks.md#enable-the-working-profile) | Same selected method, separately enabled and checked |
| Teams for Linux Flatpak | [Application qualification and activation](experiments/chromium-flatpak.md#enable-teams-or-bitwarden-for-daily-use) | Current Teams resources with the saved selected Electron engine. Application updates do not disable treatment |
| System Qt 6 and KDE Plasma | [V3 comparison build](build-system.md#fontreal-v3-for-qt-and-plasma) | Experimental Qt packages for reproducing the V3 reference with stock KWin |
| Chrome, Edge, Brave, Vivaldi and other Chromium browsers | [Why these browsers are unsupported](experiments/chromium-flatpak.md#chromium-based-browsers-are-not-supported) | Unsupported. Fontreal has no supported way to apply its stroke adjustments inside their page text engine |
| Bitwarden Flatpak | [Application qualification and activation](experiments/chromium-flatpak.md#build-and-qualify-bitwarden) | Separate selected engine with current native resources, disabled RunAsNode fuse, original process isolation and working data |
| Telegram Flatpak | [Owner inventory](experiments/chromium-flatpak.md#applications-without-activation) | Not qualified. Its bundled Qt and runtime FreeType require separate checks |
| Other GTK/GNOME apps, Qt 5, Wine and Windows | [Roadmap](roadmap.md) | No selected activation recipe yet |

Follow each integration guide. Build source revisions remain pinned. Application releases do not trigger repeated Fontreal qualification. A different rendering engine still needs an integration. Do not apply a Teams override to another Electron application.

The V2 integrations share one [O/K3 preference](build-system.md#choose-o-or-k3). O NORMAL is the default. Set `sh packaging/session/fontreal-session profile k3` for K3 NORMAL. Fully quit and reopen each application. V2 native Qt uses the next login. For subpixel rendering in the V3 reference build, use **Fonts** in Plasma System Settings.

## Firefox and Floorp: original working profiles

Follow [Requirements and build](experiments/browser-masks.md#requirements-and-build) before activation. Enable each browser separately:

```sh
python3 -B tools/browser.py enable firefox
python3 -B tools/browser.py enable floorp
```

Fully quit and reopen each browser normally. Run the corresponding `status` command from the [browser guide](experiments/browser-masks.md#enable-the-working-profile). Make sure that the intended original profile is selected and no parent still needs a restart.

For a Fontreal change, [Repeat the checks](experiments/browser-masks.md#repeat-the-checks) supplies development checks for masks, geometry, final pixels, launch routing and reversal. Keep each development report with its exact build record.

For an untreated Nimbus Sans request, follow the [CFF versus Type 1 diagnosis](experiments/browser-masks.md#when-nimbus-sans-looks-untreated). That optional font-selection rule is separate from activation and has its own removal step.

Browser updates keep the saved Fontreal library enabled. Rebuild and re-enable to receive upstream fixes in that private library. A missing or changed private artifact produces a diagnostic and native stock launch. To restore original preferences and hooks, fully quit the browser and use [Restore the original rendering](experiments/browser-masks.md#restore-the-original-rendering).

## Teams and Bitwarden: current application and original data

Follow [Enable Teams or Bitwarden for daily use](experiments/chromium-flatpak.md#enable-teams-or-bitwarden-for-daily-use). Build each engine and application view through that guide. Enable each target with its printed application record. Fully quit and reopen the target normally. Status must show `enabled: true` and `compatibility: null`.

An application update refreshes its code and resources on the next launch. It does not disable Fontreal or require another font test. The private engine receives upstream fixes when rebuilt. Preserve the full coherent engine and notices. The native absolute Flatpak command supplies stock rendering with the same account data.

Run [Checks when Fontreal changes](experiments/chromium-flatpak.md#checks-when-fontreal-changes) during Fontreal development. The focused launch check proves routing and reversal. The actual-app check proves selected text in the packaged Teams dialog or Bitwarden email input. The original-data lifecycle check covers ordinary reopening and stock restoration. The shared `apps.json` registry supports legacy Teams migration and independent disable. Disabling one target preserves the other target. These checks establish different results, so a configured hook alone is not a rendering claim.

## Native KDE: packages and fresh sessions

Use the [V3 native build guide](build-system.md#fontreal-v3-for-qt-and-plasma) to build, verify and prepare the Qt bundle. Follow its installation commands. Package and disposable Plasma session tests belong to Fontreal development under the test policy.

Keep the entire verified bundle, official rollback packages and deployment manifest together. Retain development reports when those checks run. Installation does not require new reports for each build. Run destructive session checks only inside the marked disposable VM.

After host activation, log out and back in normally. Run `fontreal-session status` in the new session. A preference for the next login does not establish the values inherited by the current session. Retain the exact predecessor bundle when testing an upgrade from an existing Fontreal installation.

## Record a reproducible comparison

Record the Git commit, OS, architecture, application package and runtime revisions, build record, named command, exit status and result directory. For a visible issue, also record the font file and format, style, point size, DPI, display scale, zoom and background. Keep original lossless images at one image pixel per display pixel.

Compare the same text and UI region under the same conditions. Keep stock and selected captures separate from enlarged pixel grids. Do not rescale or sharpen a capture before comparing it. Preserve independent reference results and exact artifact hashes with local evidence.

Before publishing evidence, remove account text and machine-specific paths from public copies. Follow [Contributing](../CONTRIBUTING.md) for portable documentation and images. Keep private result records local. Do not redistribute installed fonts or the stock engine baselines with incomplete notices.
