# From a request to a tested mod

These are investigation and acceptance-test designs, not claims that the example gameplay mods have already been implemented. Use actual installed types and methods; the scaffold does not hard-code speculative victory or recruitment APIs.

## Replace victory conditions

First establish the faction(s), scenario/DLC, the exact combination of conditions, what constitutes victory, whether the AI should use the rule, and whether an existing save must work. Conditions may be evaluated differently from the UI's displayed progress or the event that actually ends the campaign.

Search the local type index for victory, faction objectives and narrative-event types; search installed templates for the relevant faction/objectives. Decompile the evaluator, its callers, the display/progress calculation, and the terminal victory action. Identify polling/event timing, caches, scenario checks and serialized flags. Record these findings with the DLL hash.

Use native data when exposed conditions are genuinely data-driven. Use a narrow Harmony patch where the rule is compiled logic. Ensure the same intended requirements reach both the actual success decision and player-facing explanation. Preserve unrelated factions and ordinary game behavior outside the mod's scope.

Test with MCP fixtures or named setup assertions rather than playing to the end of a campaign:

| Case | Expected evidence |
|---|---|
| Each required condition false independently | No victory; correct progress/explanation |
| Just below and exactly at thresholds | Correct comparison boundary |
| All conditions satisfied | The genuine victory path triggers, not just a changed label |
| Evaluation repeated | No duplicate victory notifications or repeated rewards |
| Other faction/scenario | Original behavior remains applicable |
| Save/load before and after qualification | Consistent conditions, event flags and outcome |
| Mod disabled or removed, if supported | Documented behavior without stale patches or orphaned saved types |

If forced fixtures bypass a prerequisite, verify that prerequisite separately. Capture observed state, displayed explanation and the actual end-state action. An evaluator returning true in a standalone test does not prove its caller ever executes.

## Add a 30-influence recruitment button

See the [fingerprint-specific UI example](ui-testing-example.md) for actual tab
activation, native cost notation, transaction failures and save-removal checks.

Clarify what "advisor" means in the intended request: a councilor candidate, a hired councilor, or a different game object. Establish which faction pays, where the generated character appears, whether the pool/capacity changes, and whether there is a cooldown or limit.

Inspect the recruitment controller while its tab is open. Use DevTools `roots`/`tree`/`inspect` and screenshots to locate the current root, button prototype and text components. Trace creation, tab changes, refresh and teardown in the installed assembly. Inspect the game's own councilor generation and recruitment-pool insertion path, influence spending, bookkeeping and refresh notifications.

Create one owned control after the required UI exists. Remove inherited unwanted listeners from a clone, wire one handler, update the controller's relevant collections, and make repeated initialization harmless. The handler must recheck affordability and required state at click time, use the correct game operation, and handle failure without charging twice or creating duplicate candidates. Guard against references to a previous campaign or faction.

| Case | Expected evidence |
|---|---|
| Less than 30 influence | Disabled/unavailable control; attempted dispatch produces no payment or recruit |
| Exactly 30 influence | One action produces one appropriate recruit and leaves zero influence |
| More than 30 influence | Exactly 30 deducted; unrelated resources unchanged |
| Funds change while the tab is open | Availability refreshes and the handler revalidates the current amount |
| Two deliberate clicks with sufficient funds | Two distinct operations, not duplicate listeners on each click |
| Close/reopen, switch tab/selection/faction | One button and the correct payer/current pool |
| Save/load and a second campaign | No stale UI/state references; persisted recruit behaves normally |
| Long localization, display scaling, scroll bounds | Label, tooltip and control remain usable |
| Disable/re-enable | Only the mod's controls/listeners are removed/recreated |

Use MCP fixtures to prepare influence and pool state, then invoke the **button's event handler**, not the generic spawn action, for the payment assertion. Read back resources and the pool before and after. Finish with screenshots and actual pointer interaction when available. A generic `spawn_councilor` call proves neither the button nor its price.

## Add content or assets

For an org, technology or event, begin with a minimal native record and all required registration/localization entries. Check merged values at the main menu, then actual availability in the intended scenario. For a visual asset, build a small matching-version bundle before expanding the project; check the exact consuming screen. For ships, test designer, strategic display and tactical combat separately.

Use the [capability map](capabilities.md) for detailed source examples. Add only the required tooling profile and retain editable asset sources so a later game update can be rebuilt.
