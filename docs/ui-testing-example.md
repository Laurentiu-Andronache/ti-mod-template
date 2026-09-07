# Worked UI investigation: recruitment tab

These observations apply to **Terra Invicta 1.0.53a**, Assembly-CSharp SHA-256
`ff7916c2085ddbafa5acf1e8ea185d37e629096752be388ba6fa1f627f027bb5`,
Unity 2020.3.49f1 and UMM 0.33. Reinspect after a fingerprint change. They are
observations of the installed code and recorded UI tests, not permanent API contracts.

## Open and inspect the real lifecycle

In a disposable campaign, call `observe`, wait for initialization, and take a
screenshot. A ready campaign can still have an introduction over its UI. Clear
that cinematic through the appropriate visible control before testing the screen;
record an occluded click as a failed attempt, correct it, then retest.

Use MCP `ui_screen` with `show:"council"`, then helper `roots`, bounded `tree`, and
`inspect` to locate the actual Recruiting tab. Activate its real
`TabbedPaneController.TabButton` through helper `click` on the discovered handle.
In this build, calling `CouncilGridController.OnClickGridRecruitButton` directly
bypasses tab selection, raycaster activation and layout updates. Invisible rows
or failed raycasts can therefore be a test setup problem. Reacquire handles after
tab, screen or campaign transitions; confirm selection and layout before judging
the new control.

A cloned button needs review of persistent listeners as well as runtime
listeners, raycast targets, native sprite/font assets, text styles, anchors,
scaling, scroll bounds and controller registration. Register exactly one owned
handler and clean up only mod-owned controls/listeners. Check reopen and repeated
initialization, including already initialized screens.

## Cost and operation checks

Use the game's formatter for the native cash sprite, followed by one space and
the game's appropriate numeric formatting for the displayed amount:

```csharp
string moneyIcon = TIUtilities.InlineResourceStr(FactionResource.Money);
int scenarioStartYear = GameStateManager.Time().template.year;
int currentYear = GameStateManager.Time().Time_Now().year;
```

Reading current time supports date-derived prices without adding save state.
Capture the transaction quote once; use that same amount for the label/tooltip,
affordability check, charge and rollback. Revalidate affordability in the actual
handler. Check the rendered resource icon in screenshots: text markup or sprite
metadata alone does not prove the font/sprite asset renders correctly.

Trace the complete game operation before reusing it. In this build,
`TIFactionState.AddAvailableCouncilor` **hires** a councilor, despite its name;
candidate generation and insertion are separate operations. Follow registration,
appearance/location bookkeeping, notifications and caches. Resource operations
can raise events after changing the balance. Inject failures after generation
and after debit; verify partially registered objects are cleaned up and the
refund uses the captured quote, even if the displayed price has since changed.

## Evidence to collect

- Exercise the actual button with insufficient and exact funds; compare balances,
  pool membership and other resources before and after. Fixture generation alone
  proves neither affordability nor the player-facing operation.
- Repeat clicks, reopen the screen, change selection/faction, disable/re-enable,
  and start a second campaign. Check one control/listener and current state.
- Save an updated vanilla candidate, verify ordinary hiring, reload in a fresh
  process, and load with the project mod absent when only vanilla saved types are
  used. Record the actual scenarios/factions covered and compare exceptions with
  a baseline; generic template smoke tests do not prove recruitment behavior.
- Capture readable labels, native cost icons, tooltips, clipping and scroll/input
  behavior. Helper `click` is Unity event dispatch with a center raycast, not an OS
  pointer click. Report desktop input separately and retain occluded attempts.

Use [interactive sessions](interactive-testing.md) for this investigation and
[recipe assertions](testing.md) for repeatable acceptance. No councilor IDs, pool
sizes, custom fixtures or gameplay implementation are prescribed by this example.
