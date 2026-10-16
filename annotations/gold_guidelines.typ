// Gold standard annotation guidelines.
//
//   typst compile annotations/gold_guidelines.typ

#set document(title: "Gold standard annotation guidelines")
#set page(paper: "a4", margin: 2.8cm, numbering: "1")
#set text(font: "New Computer Modern", size: 11pt, lang: "en")
#set par(justify: true, leading: 0.65em, spacing: 0.65em)
#show raw: set text(font: "DejaVu Sans Mono", size: 1.1em)

#show heading: set block(above: 1.6em, below: 1em)
#show heading.where(level: 1): set text(size: 14pt)

#set list(spacing: 5pt, indent: 1em)
#set enum(spacing: 5pt, indent: 1em)

#let toprule = table.hline(stroke: 0.8pt)
#let midrule = table.hline(stroke: 0.4pt)
#let bottomrule = table.hline(stroke: 0.8pt)
#show table: set par(justify: false)

// --- Title ---
#align(center)[
  #text(size: 17pt)[Gold standard annotation guidelines] \
  #v(2pt)
  #text(size: 12pt)[_Version 2 — 9 October 2026_]
]
#v(1em)

Version 1 (frozen on 8 October 2026) did not cover several cases that the annotation treated as positive. Version 2 describes the criteria actually applied to the 145 gold episodes; the annotations themselves were not changed.

= Principles

- The whole episode is annotated.
- Judge with what was public at that moment. No prices, no later facts.
- Guiding question: does the episode signal that the conflicts affecting crude supply are moving toward resolution or toward escalation?
- The conflicts that matter are those involving oil producers and routes: Iran and the Strait of Hormuz, Venezuela, Russia and Ukraine, the Houthis and the Red Sea.
- Novelty is not judged: the `novelty` feature already measures it.

= Direction (−2 … +2)

Positive = toward resolution: the war ending or won, an agreement, routes and oil flows reopened. Negative = toward escalation.

+ Does it say anything about where these conflicts are heading? No → *0*.
+ Sign:
  - *Positive*: ceasefires; deals and negotiations making progress; attacks called off or postponed; the United States controlling or reopening the Strait of Hormuz, oil flowing; claims that the war is won, the enemy defeated or the conflict over; envoys, meetings and trade agreements aimed at peace or involving oil purchases; sanctions or pressure presented together with a demand for an immediate ceasefire.
  - *Negative*: attacks launched or announced; ultimatums and threats; blockades; sanctions and tariffs on producers or on buyers of their oil; leaders killed; talks breaking down or hard-line positions; statements that Iran will never have a nuclear weapon.
+ Strength: *±2* for decisive moments: a war starting or ending, a ceasefire agreed, a major attack launched or imminent, a leader killed, a blockade imposed, the Strait of Hormuz declared open with oil flowing, a deal reached or major concessions obtained; also strong claims that the war is won and oil will flow. *±1* for everything else: talks, threats, demands, commentary.

Mixed messages: the decisive element prevails. If they balance out, judge the overall tone.

= Intensity (1 … 3)

- *1* $->$ comment, opinion, forecast, claim
- *2* $->$ threat, ultimatum, demand, intention
- *3* $->$ action done, or imminent with a precise moment ("tonight", "within 48 hours")

= Specificity (0 / 1)

*1* if the episode is about a concrete action, threat or measure aimed at a precise target (a country, leader, group, place, facility or ship), or contains a quantity or a deadline. *0* for commentary, claims and generic statements, even when they name a country or a leader.

*Convention:* if `direction` = 0, then `intensity` = 1 and `specificity` = 0.

= Always 0

- Actor or mechanism mentioned in passing in a post about something else.
- Polls; op-eds and articles that only argue with critics or the media. An article that reports an action is judged on the action.
- Arguments about past decisions or with opponents that say nothing about how the conflict is going.
- Military facts unrelated to oil producers or routes (drug-trafficking boats, drones over Poland).
- Comments on prices that have already moved.
- Greenland.

= Examples

#align(center, table(
  columns: (1fr, auto, auto, auto),
  align: (left, center, center, center),
  stroke: none,
  inset: (x: 6pt, y: 4pt),
  toprule,
  [episode], [dir], [int], [spec],
  midrule,
  ["Complete and Total CEASEFIRE (in approximately 6 hours…)"], [+2], [3], [1],
  ["Oil is flowing like never before… the Strait of Hormuz is open"], [+2], [2], [1],
  ["Iran has officially responded… very weak response… 14 missiles"], [+1], [3], [1],
  ["very close to meeting our objectives as we consider winding down"], [+1], [2], [1],
  ["the nuclear sites in Iran are completely destroyed" (argument with CNN)], [+1], [1], [1],
  ["Countries that receive Oil through the Hormuz Strait must take care of that passage, and we will help"], [+1], [2], [1],
  ["Secondary Tariff on the Country of Venezuela"], [−1], [1], [1],
  ["Iran must stop the sending of these Supplies" (Houthis)], [−1], [2], [1],
  ["WE WILL NOT ALLOW ANY ENRICHMENT" (negotiation under way)], [−1], [2], [1],
  [Nigeria, "guns-a-blazing"], [−1], [1], [0],
  ["Khamenei… is dead"], [−2], [3], [1],
  ["If I didn't terminate… JCPOA"], [0], [1], [0],
  bottomrule,
))

= Procedure

+ Trial on 20 episodes, revise, freeze, start again from scratch.
+ Random order, not chronological.
+ Every doubt in `notes`.
+ The 50 double episodes to a second person. Target: weighted kappa ≥ 0.6 on direction.
+ Check: episodes labelled 0 in the rule versions must have `direction` 0.
