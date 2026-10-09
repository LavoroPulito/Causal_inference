# Gold standard annotation guidelines

Version 1 — forzen on oct 8 2026 

## Principles

- The whole episode is annotated (`joined_text`).
- Judge with what was public at that moment. No prices, no later facts.
- Guiding question: does the episode change what is expected for crude supply in the coming days?
- Novelty is not judged: the `novelty` feature already measures it.

## direction (−2 … +2)

Expected effect on **supply**. Negative = supply at risk (price expected to rise).

1. Does it change expectations on supply? No → **0** (even if the post is off topic).
2. Sign: threat, escalation, sanctions, blockades → negative. Agreements, ceasefires, reopened routes, more output → positive.
3. Strength: **±2** if it affects physical flows (Hormuz closed/reopened, attack on infrastructure, ceasefire concluded); **±1** if it affects probabilities (negotiations, demands, generic threats, sanctions on third parties).

Mixed messages: what changes the physical state prevails. If they balance out: 0 and a note.

## intensity (1 … 3)

- **1** comment, opinion, forecast
- **2** threat, ultimatum, demand, intention
- **3** action done, or imminent with a precise moment ("tonight", "within 48 hours")

## specificity (0 / 1)

**1** if it names at least one of: a specific place, facility or ship; a quantity; a deadline; a specific measure (tariff, agreement).

**Convention:** if `direction` = 0, then `intensity` = 1 and `specificity` = 0.

## Always 0

- Actor or mechanism mentioned in passing in a post about something else.
- Polls, linked op-eds, arguments about facts already known.
- Military facts unrelated to supply (drug trafficking, drones over Poland).
- Comments on prices that have already moved.
- Greenland.

## Examples

| episode | dir | int | spec |
|---|:-:|:-:|:-:|
| "Complete and Total CEASEFIRE (in approximately 6 hours…)" | +2 | 3 | 1 |
| "Iran has officially responded… very weak response… 14 missiles" | +1 | 3 | 1 |
| "very close to meeting our objectives as we consider winding down" | +1 | 2 | 1 |
| "Secondary Tariff on the Country of Venezuela" | −1 | 3 | 1 |
| "Iran must stop the sending of these Supplies" (Houthis) | −1 | 2 | 1 |
| "WE WILL NOT ALLOW ANY ENRICHMENT" (negotiation under way) | −1 | 2 | 1 |
| Nigeria, "guns-a-blazing" | −1 | 2 | 1 |
| "the nuclear sites in Iran are completely destroyed" (argument with CNN) | 0 | 1 | 0 |
| "If I didn't terminate… JCPOA" | 0 | 1 | 0 |

## Cases resolved during the trial

- "Oil is flowing like never before" — signal that routes will stay open (+1)
- "Countries that receive Oil through Hormuz must take…" — the US stepping back from protecting the strait (−1)? Yes it is. 

## Procedure

1. Trial on 20 episodes, revise, freeze, start again from scratch.
2. Random order, not chronological.
3. Every doubt in `notes`.
4. The 50 double episodes to a second person. Target: weighted kappa ≥ 0.6 on direction.
5. Check: episodes labelled 0 in the rule versions must have `direction` 0.
