# Phase 01 — UI Review

**Audited:** 2026-10-29
**Baseline:** abstract 6-pillar standards (no UI-SPEC.md), applied to a PySide6 / Qt Widgets (Fusion) desktop app
**Screenshots:** not captured (desktop Qt app, no dev server; code-only audit)
**Interaction captures:** off (workflow.ui_interaction_capture is false)

Scope: the GUI surface Phase 01 touched: `gui/app.py` (stage row and step label, Open log, inline failure and Retry, close confirmation, download step text) and `gui/runner.py` (how failures and timeouts reach the view). The layout itself is the old one; findings that are really about the shell redesign are marked **(Phase 3)** and are not counted against this phase's score.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | Causes are specific and honest, but the internal name "porter" is shown to players, and one string ends in a dangling " · " |
| 2. Visuals | 2/4 | A cancelled or failed run leaves the running stage marked "▶" for good; the Port tab's failure line is not red, and it has no Retry |
| 3. Color | 2/4 | Eight hex literals and no palette; the Games tab's `#000` fallback disappears on a dark theme; white text on `#ef6c00` is about 3:1 |
| 4. Typography | 3/4 | The scale is small and consistent; the log font is Menlo on Linux too, where it usually isn't installed |
| 5. Spacing | 2/4 | `dl_step` has no word wrap, so an 8-line stderr tail in the download row stretches the window |
| 6. Experience Design | 2/4 | The stop, timeout and close paths are solid, but a 1 GB download can't be cancelled, inspect data goes into rich text unescaped, and "stopping…" lands on the wrong tab |

**Overall: 14/24**

---

## Top 3 Priority Fixes

1. **The stage row stays at "▶" after a cancel or a failure that has no `stage_end`** (BLOCKER for the D-06/D-07 cancel story). The player sees a stage that still looks like it is running, with its timer frozen, under the word "cancelled". Fix: in `PortTab.on_finished` (gui/app.py:236), when `code != 0`, set every item whose `text(0) == '▶'` to `✗` (red), or to `–` on a cancel.
2. **Inspect data goes into the RichText card without escaping** (WARNING). The card at gui/app.py:121 (`Not a folder: {d}`), 131 (`info["name"]`), 134 (`info["pack"]`) and 136 (`info["reason"]`) is `Qt.RichText`. A folder path or reason with `<` or `&` in it breaks the card. `failed()` already escapes; these lines don't. Fix: wrap each one in `html.escape(..., quote=False)`.
3. **The tool download can't be cancelled, and its error label doesn't wrap** (WARNING). `SetupTab` starts `self.fetch` with no Cancel control, so the only way to stop a 1 GB download is to quit the app. `self.dl_step` (gui/app.py:277) never gets `setWordWrap(True)`, so the red multi-line failure widens the window. Fix: turn `dl_btn` into "Cancel download" while `self.fetch.running()` (it calls `self.fetch.stop()`; `fetched` already handles 130), and call `self.dl_step.setWordWrap(True)`.

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)
- PASS: the causes are concrete. `failed after 1:23: <cause>` (app.py:246), `porter didn't answer in 15 s` (app.py:34), and the close dialog's "The app on the device may be left half-installed." (app.py:412) names the actual risk. The buttons say what they do: "Stop and quit" and "Keep running", not OK/Cancel.
- WARNING: the internal name "porter" reaches players in `porter didn't answer…` and `porter gave no answer` (app.py:34–35), `porter failed` (app.py:39) and the device combo's `'porter: ' + cause` (app.py:150). Testers don't know what porter is. Use "nx2android" or "the port tool".
- WARNING: in app.py:315, when `step` is empty the label reads `NDK · ` with a trailing separator. Fix: `' · '.join(filter(None, [...]))`, as app.py:211 already does in effect.
- MINOR: the Port tab's failure has no "what next" text. The one-shots get Retry, but a failed port only says the cause; "Open log" is a separate button the player has to notice.

### Pillar 2: Visuals (2/4)
- BLOCKER: the leftover "▶" marker (Top fix 1). `on_tick` stops once `running()` is false, so the time freezes as well.
- WARNING: the Port tab's failure line `self.step` (app.py:97) is `Qt.PlainText` in the default colour, so a failure looks the same as `done in 1:23`. Only the log pane and the stage `✗` are red. The one-shot failures are red, so the two kinds of failure look different. Set a red stylesheet on `self.step` for failure and cancel, and clear it in `run()`.
- WARNING: after "Stop and quit", `closeEvent` writes `stopping…` to the Port tab (app.py:426) even when only the Setup download is running. The player is on the Setup tab and sees nothing change. Write it to `dl_step` too, or to the tab that owns the run.
- PASS: the focal point is clear. Port is bold and +2 pt with a 36 px minimum height (app.py:85–86), and the stage tree uses glyphs plus colour, so colour isn't the only signal.

### Pillar 3: Color (2/4)
- 8 distinct hex literals across about 14 sites: `#c62828` (red, 7 sites), `#2e7d32` (3), `#ef6c00` (4), `#757575` (2), `#000` (1), and `white` on the badge. There is no palette constant for red, even though the `[RED]` convention is the app's main signal. Add `RED = '#c62828'` and similar beside `STATUS_COLOUR`.
- WARNING: Games' fallback `QColor(STATUS_COLOUR.get(..., '#000'))` (app.py:389) is black text, which can't be read on a dark macOS or Linux theme. Fusion follows the system palette on macOS dark mode. Use `self.palette().text().color()` as the fallback.
- WARNING: the status badge is white on `#ef6c00`, about 3.0:1 contrast. That is below WCAG AA for the small text it uses (app.py:132). Darken it to `#c25100` or so, or use dark text. **(Phase 3** for the badge's redesign, but the contrast bug is live now.)
- PASS: the `[RED]` rule works end to end. The runner turns the last stderr line into a `[RED]` say (runner.py:538), `append` colours it, and `self.red` picks it up as the fallback cause (app.py:222, 244).

### Pillar 4: Typography (3/4)
- The scale is small: the system default, the Port button at +2 pt bold, `<b>` emphasis in the card and notes, and 9 pt mono in the log. That is consistent.
- MINOR: `QFont('Consolas' if nt else 'Menlo', 9)` (app.py:102). Linux usually has no Menlo, so Qt substitutes a proportional font unless you call `setStyleHint(QFont.Monospace)`, or use `QFontDatabase.systemFont(QFontDatabase.FixedFont)`. This matters now that Linux is a target.
- MINOR: the stderr tail in `failed()` is in the proportional UI font, so tracebacks lose their alignment. Wrapping it in `<pre>` or `<tt>` would fix that.

### Pillar 5: Spacing (2/4)
- WARNING: the unwrapped `dl_step` (Top fix 3). It shares an HBox with the button and the progress bar, and the red text can be up to 8 lines (runner.py:582).
- MINOR: the card's 60 px minimum height (app.py:63) fits a normal card, but an 8-line `failed()` tail pushes the Options group down while you read it. That's acceptable.
- No arbitrary margins. Every layout uses Qt's defaults, so the spacing is consistent but untuned. **(Phase 3)**

### Pillar 6: Experience Design (2/4)
- PASS: the stop path. Cancel shows `stopping…` and greys itself out (app.py:189), and says "cancelled" only once `finished` reports that the tree is gone. There is a 5 s grace before the force kill (runner.py:513), and a stop pressed before `started` can't hit the GUI's own group (runner.py:510–512).
- PASS: one-shot timeouts per command (runner.py:452). Every one-shot view gives an inline cause and Retry (card, `check_msg`, Games note, `dl_step`), and the device combo uses Refresh as its retry. The destroyed-owner guard means no callback hits a dead view.
- PASS: the close confirmation defaults to "Keep running", warns about a half install, and closes itself once nothing is left running (app.py:407–426).
- WARNING: there's no cancel for the download (Top fix 3).
- WARNING: the inspect card is unescaped (Top fix 2).
- WARNING: the stale "▶" marker (Top fix 1).
- MINOR: `start()` with Experimental ticked reads `self.info.get(...)` (app.py:171). That's safe only because the button is disabled when `info` is None; if a failed inspect leaves `info = None` and Port is enabled some other way, it crashes. Add a guard.
- MINOR: nothing shows that the one-shots are loading, except "Reading the game folder…" and "reading the download lists…". The Setup table and the Games table sit empty while doctor and profiles run (up to 30 s and 20 s). **(Phase 3)**

---

Registry audit: skipped (not a shadcn or web project).

## Files Audited
- /Volumes/Data/Dev/nx2android/gui/app.py
- /Volumes/Data/Dev/nx2android/gui/runner.py
- /Volumes/Data/Dev/nx2android/.planning/phases/01-bridge-bundles-and-ci/01-03-SUMMARY.md, 01-04-SUMMARY.md, 01-07-SUMMARY.md (skimmed for GUI scope)
