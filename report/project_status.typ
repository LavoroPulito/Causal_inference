// Project status.
//
// Update:
//   python report/figures.py              (recomputes the figures in figures.json)
//   typst compile report/project_status.typ
//
// Figures marked #n.… come from figures.json and update themselves.
// The text is revised by hand; every change of method goes in the Change log at the end.

#let n = json("figures.json")

#set document(title: "Trump's posts and the price of crude oil — Project status")
#set page(paper: "a4", margin: 2.8cm, numbering: "1")
#set text(font: "New Computer Modern", size: 11pt, lang: "en")
#set par(justify: true, leading: 0.65em, spacing: 0.65em, first-line-indent: 1.5em)
#show raw: set text(font: "DejaVu Sans Mono", size: 1.1em)

#set heading(numbering: "1.1")
#show heading: set block(above: 1.6em, below: 1em)
#show heading.where(level: 1): set text(size: 14pt)
#show heading.where(level: 2): set text(size: 12pt)
#let sub(title) = heading(level: 2, numbering: none, title)

#set enum(spacing: 5pt, indent: 1em)
#set terms(separator: linebreak(), hanging-indent: 1.6cm, indent: 0pt, tight: false, spacing: 5pt)

#let toprule = table.hline(stroke: 0.8pt)
#let midrule = table.hline(stroke: 0.4pt)
#let bottomrule = table.hline(stroke: 0.8pt)
#show table: set par(first-line-indent: 0pt, justify: false)
#let grid-table(..args) = align(center, table(stroke: none, inset: (x: 6pt, y: 4pt), ..args))

// Number formatting
#let thou(x) = {
  let s = str(x)
  let out = ""
  for (i, c) in s.clusters().enumerate() {
    if i > 0 and calc.rem(s.len() - i, 3) == 0 { out += "," }
    out += c
  }
  out
}
#let pct(x, digits: 1) = str(calc.round(x * 100, digits: digits)) + "%"

// --- Title ---
#align(center)[
  #text(size: 17pt)[Trump's posts and the price of crude oil] \
  #v(2pt)
  #text(size: 14pt)[Project status]
  #v(1em)
  #text(size: 12pt)[updated on #n.date]
]
#v(1em)

= The processing chain

The question is whether Trump's posts that signal a risk to crude supply move the price of oil, and for how long. Three things are needed: knowing _when_ each post was published, precisely enough to isolate its effect; establishing _which_ posts count as events, with a replicable criterion; having a price series dense enough to measure the reaction in the following minutes.

The work is split into numbered scripts, each reading the output of the previous one.

/ `00`  corpus: Downloads the posts from the archive of the American Presidency Project (UCSB), up to 31 July 2026. The publication time is not read from the page but derived from the post identifier, which contains it by construction. The time printed on the page is only a check.

/ `00b`  integration: Adds the posts UCSB does not have, taken from CNN's public archive. Here too the time comes from the identifier, extracted from the post link: the two sources are treated the same way. After 31 July 2026 CNN is the only source: it is updated within hours, while UCSB publishes with days of delay, and it contains all the UCSB posts that pass the rule.

/ `01`  selection: Discards what has no text content, applies the rule that defines an oil event, groups close posts into episodes and measures how long the observation windows can be. The episode is the unit of analysis.

/ `02`  audit: Tests the rule with two unsupervised methods that do not know the term lists. It measures how much the rule misses; it does not define anything.

/ `03`  prices: Downloads one-minute quotes from Dukascopy. Used for a test on March 2025; the full download was refused by the server (@prices).

/ `03b`  synthetic prices: Generates synthetic WTI, gold and EUR/USD series with a known effect of the episodes, to test the analyses.

/ `03c`  prices: Downloads one-minute futures prices from Databento: WTI, Brent, gold, S&P 500, euro/dollar.

/ `04`  features: Measures each episode: time, length, emphasis, novelty with respect to recent episodes, and the variables that require reading: the direction of the conflicts affecting supply, intensity, specificity. These are annotated by hand.

/ `update`  update: Brings the dataset up to date with the latest posts. It runs `00b`, `01` and `04` in sequence and appends the new episodes to the manual annotation file, with the judgements empty. Annotations are matched to the episodes through the identifier of their first post, so they stay attached to the right episode even if the numbering changes; an annotated episode whose text has changed is marked for review.

/ `05`  episode table: Joins the features with the manual annotations, one row per episode, in a dated file.

/ `06`  event study: Price returns before and after each episode, regressed on the annotated variables.

/ `07`  causal discovery: PCMCI+ on a regular 5-minute grid, CD-NOD on the episodes.

Two support folders: `annotations/` keeps every version of the rule together with the annotated sample used to evaluate it; `query/` holds read-only scripts to query the data.

The features must be frozen before looking at prices: tuning them on returns would mean building the result instead of measuring it.

= Where we are

#grid-table(
  columns: 3,
  align: (left, left, right),
  toprule,
  [Step], [Status], [Output],
  midrule,
  [00–00b corpus], [done], [#thou(n.posts) posts up to #n.period_end],
  [01 selection], [done, rule #n.versions.last().version], [#thou(n.events) events, #thou(n.episodes) episodes],
  [02 audit], [done], [#n.audit.topics clusters, #n.audit.false_negatives candidate false negatives],
  [03–03c prices], [done], [5 Databento series, synthetic series],
  [04 features], [A, B, C done; D on hold], [#n.feature_columns columns; #n.manual.annotated of #n.manual.episodes episodes annotated],
  [05 episode table], [done], [one row per episode],
  [06 event study], [first runs], [@runs],
  [07 causal discovery], [first runs], [@runs],
  bottomrule,
)

= The corpus

#sub[Sources]

#grid-table(
  columns: 2,
  align: (left, right),
  toprule,
  [Source], [Posts],
  midrule,
  [American Presidency Project (UCSB)], [#thou(n.posts_ucsb)],
  [CNN archive, only posts missing from UCSB], [#thou(n.posts_cnn)],
  midrule,
  [Total, from 1/12/2024 to #n.period_end], [#thou(n.posts)],
  bottomrule,
)

UCSB is a curated, incomplete archive. Between December 2024 and July 2026 the CNN archive contains 2,811 posts that UCSB does not have; UCSB therefore covered about 75% of the actual output. Posts after 31 July 2026 come on top of these. Truth Social blocks automated access to its API (403 response), so it is not used as a direct source.

#sub[The timestamp]

Truth Social uses snowflake identifiers, whose high bits are the milliseconds since the Unix epoch:
$ t_"UTC" = ("post_id" >> 16) / 1000,
  quad
  "seq" = "post_id" thin \& thin "0xFFFF". $
The sequence field orders posts published within the same millisecond. For both sources the identifier is extracted from the post link.

Checks: the announcement of the strike on Fordow comes out at 19:50 EDT on 21 June 2025, the publicly known time; the date declared by CNN matches the one derived from the ID for every post, within one second; for UCSB the time on the page matches in #pct(n.verified_ucsb) of cases.

#sub[UCSB anomalies]

The archive prints the time in two formats: 24-hour (`18:11`) and 12-hour with a meridiem (`1:17 PM`). The first version of the parser ignored the meridiem, and the suffix ended up at the start of the post text. Fixed. The remaining anomalies do not affect the timestamps, which come from the ID:

#grid-table(
  columns: 3,
  align: (left, right, left),
  toprule,
  [Offset], [Rows], [Cause],
  midrule,
  [180 min], [105], [UCSB prints Eastern time from 15 to 21 September 2025],
  [other], [36], [isolated editorial errors],
  [missing], [15], [no time on the page],
  [720 min], [8], [24-hour page with a wrong time (`12:27` for `00:27`)],
  bottomrule,
)

= Cleaning

Of the #thou(n.posts) posts, #thou(n.clean_corpus) remain (#pct(n.clean_corpus / n.posts)).

#grid-table(
  columns: 3,
  align: (left, right, left),
  toprule,
  [Criterion], [Removed], [What it removes],
  midrule,
  [No content], [#thou(n.cleaning.placeholders)], [videos and images without a caption, placeholders],
  [Double posts within 2 minutes], [#thou(n.cleaning.doubles)], [identical texts close in time],
  [Endorsement boilerplate], [#thou(n.cleaning.boilerplate)], [the template of election endorsements],
  [Under 5 words], [#thou(n.cleaning.short)], [slogans and fragments],
  bottomrule,
)

Most removals are posts without text: Trump publishes many videos and images without writing anything. Once the file address is removed, an empty string or the word `Video` is left. Excluding them is unavoidable for a lexical rule, but it is a limit to declare: a video of a refinery being hit is market information, and no word-based rule can see it.

#sub[Open problems]

*Double posts.* The filter compares normalized texts (lowercase, no punctuation). All video-only posts have the same normalized text, `video`, and two different videos less than two minutes apart are merged as if they were a double post. The result does not change, because those posts would be discarded anyway, but it makes the counts in the table hard to read.

*Reposts.* The corpus contains 752 reposts (`RT`): 460 of Trump's own posts, 291 of other accounts, the rest links only. Reposts of his own posts are duplicates: same text, different identifier, published minutes or hours after the original. Today they enter as distinct events (see novelty, section 9). In the CNN format, moreover, the account name is glued to the text (`RT @realDonaldTrumpIran is…`), and removing mentions deletes the first word of the post.

= The rule

A post is an event if it contains at least one supply actor and at least one mechanism:
$ "event"_i = bb(1) lr([ |A inter T_i| >= 1 and |M inter T_i| >= 1 ]), $
with $T_i$ the tokens of the post, $A$ the list of actors, $M$ the list of mechanisms.

- *Actors*: Iran and Hormuz, Venezuela, Russia and Ukraine, OPEC and Saudi Arabia, the strategic reserve, routes (Red Sea, Houthis, Suez), Nigeria, explicit oil (`oil`, `crude`, `barrel`, `gasoline`, `fuel`).
- *Mechanisms*: physical disruption (blockade, mines, tankers, strait, ports, pipelines), military action, sanctions and tariffs, nuclear negotiation, regime change, ultimatum, flows resuming.

On the clean corpus: #thou(n.with_actor) posts with an actor, #thou(n.with_mechanism) with a mechanism, *#thou(n.events) events*. Of these, #n.weak rest only on weak mechanisms (`military`, `attack`, `strike`, `nuclear`): conflict terms that do not directly concern supply. Even so, most of these posts are of real interest, so weak mechanisms remain a valid tool.

#sub[Annotation criterion]

A post is relevant (label 1) if it concerns:

+ *the conflict with Iran and the Strait of Hormuz*: attacks, damage, ceasefires, negotiations, opening or closing of the strait. They shape expectations on the most important oil route.
+ *the Iranian nuclear programme*: including statements such as "Iran will never have a nuclear weapon", read as a sign of tension between Iran and the US.
+ *Venezuela*: the action of the Trump administration has affected Venezuelan oil flows.
+ *Russia and Ukraine*, when they touch sanctions, energy or the end of the war.

It is not relevant (label 0):

+ an actor or mechanism mentioned in passing in a post about something else (Bondi, Epstein, the Kennedy Center);
+ polls and linked op-eds, arguments with the media and opponents about facts already known;
+ military facts unrelated to supply (strikes on drug-trafficking boats, Russian drones over Poland);
+ comments on prices that have already moved ("Oil prices are down"): the information flows from the price to the post, not the other way round;
+ posts about Greenland, for now.

#sub[Versions]

Each version saves in `annotations/` the rule and the annotated sample: 100 posts captured by the rule (_inside_) and 50 meeting only one criterion (_boundary_). The share of relevant posts _inside_ is the precision; the share on the _boundary_ estimates how many relevant posts the rule misses. 95% confidence intervals (Wilson).

#grid-table(
  columns: (auto, 1fr, 1fr, auto, auto),
  align: (left, left, left, right, right),
  toprule,
  [], [Added], [Removed], [Precision], [Relevant on the boundary],
  midrule,
  ..n.versions.map(v => (
    v.version,
    if v.added.len() > 0 { v.added.map(raw).join(", ") } else [—],
    if v.removed.len() > 0 { v.removed.map(raw).join(", ") } else [—],
    [#pct(v.precision, digits: 0) \ #text(size: 8pt)[#pct(v.precision_ci.at(0), digits: 0)–#pct(v.precision_ci.at(1), digits: 0)]],
    [#pct(v.boundary, digits: 0) \ #text(size: 8pt)[#pct(v.boundary_ci.at(0), digits: 0)–#pct(v.boundary_ci.at(1), digits: 0)]],
  )).flatten(),
  bottomrule,
)

With the current version the _boundary_ counts #thou(n.boundary) posts. The estimated recall is about *#pct(n.recall, digits: 0)*: an upper bound, because it does not count relevant posts with neither actors nor mechanisms. With 100 and 50 annotated posts the intervals are wide, and the differences between neighbouring versions are not significant.

#sub[Structure of the rule]

The rule errs more by excess than by omission: Trump also uses the keywords to attack political opponents. On 482 posts annotated across all versions, proximity constraints between actor and mechanism (same sentence, within 20 words) remove almost as many relevant posts as irrelevant ones. False positives are not a lexical problem: in "Strong Majority Backs Trump in Stopping Iran's Nuclear Ambitions" actor and mechanism are adjacent, and it is the purpose of the post that makes it irrelevant.

A semantic classifier (logistic regression on embeddings) trained on the same 482 labels separates relevant and irrelevant posts with an AUC of 0.92 in cross-validation. Used as a second stage, it raises precision _inside_ from 80% to 87% while losing 6 relevant posts out of 217. It is an open decision (@decisions).

= Unsupervised audit

Last run on the full clean corpus (#thou(n.audit.corpus) posts): #n.audit.topics clusters, #pct(n.audit.outliers) outliers. The rule covers #pct(n.audit.top.at(0).coverage, digits: 0) of the largest Iran/Hormuz cluster (#n.audit.top.at(0).captured of #n.audit.top.at(0).n posts).

Clusters with an oil lexicon and low coverage:

#grid-table(
  columns: 3,
  align: (left, right, right),
  toprule,
  [Characteristic terms], [Captured], [Coverage],
  midrule,
  ..n.audit.suspicious.map(s => (s.terms, [#s.captured / #s.n], [#pct(s.coverage, digits: 0)])).flatten(),
  bottomrule,
)

Russia/Ukraine and Venezuela are inside the scope of the thesis: their low coverage is a real gap in the term lists, consistent with the posts on the Russia–Ukraine peace process found on the _boundary_, which name the actors but no mechanism. The energy-policy cluster (EPA) and the cluster on pump prices are outside the scope by construction.

The semantic search returns #n.audit.false_negatives candidate false negatives, posts close to the probe sentences but not captured by the rule.

= Episodes, window, power

Posts within 30 minutes form one episode, dated at the first post: #thou(n.events) events give *#thou(n.episodes) episodes*, #n.episodes_multipost of which with more than one post. Clustering in time is marked (June 2025, March–June 2026) and provides the regimes to compare with CD-NOD.

Episodes preceded by another within one hour: #pct(n.contaminated_60); within two hours: #pct(n.contaminated_120). With the 15% threshold the event window reaches two hours.

Minimum detectable effect, two-sided test, $alpha = 0.05$, power 0.8:
$ "MDE" = (z_(1-alpha\/2) + z_(1-beta)) / sqrt(n) sigma = 2.802 / sqrt(n) sigma. $
With $n = #n.episodes$: #n.mde standard deviations. On episodes with a WTI price (#pct(n.wti_coverage)): #calc.round(2.8016 / calc.sqrt(n.episodes * n.wti_coverage), digits: 3).

= Price data <prices>

#sub[Dukascopy test]

A first test was made on March 2025 with Dukascopy, a broker that publishes its one-minute quotes for free (files in `download/`). Dukascopy fills closed-market periods by repeating the last price, so a bar counts as real only if it is not inside a constant-price stretch of at least one hour.

- *Brent*: every Tuesday and Thursday of the month is missing, and the days present stop at 21 UTC.
- *WTI*: covers from Sunday 22 UTC to Friday 21, with a daily break between 21 and 22.
- *Gold*: same structure, downloaded for one week only.

The download of the whole WTI series, on 14 October 2026, failed. The server answered HTTP 429 ("too many requests") and `dukascopy-node` saved empty files without reporting an error. `03` now treats an empty file as a failure and spaces out its requests. The server was still refusing requests the following day.

#sub[Databento]

The series used now are futures prices from the exchanges, bought from Databento on 16 October 2026 for 21.64 \$ and downloaded with `03c`. They are one-minute bars (open, high, low, close, volume) from 24 November 2024: the week before the corpus serves for the windows of the first episodes.

#let db = n.prices.databento
#let db-row(name, label, exchange, symbol) = if name in db {
  let s = db.at(name)
  ([#label], [#exchange], [`#symbol`], [#thou(s.bars)], [#s.start – #s.end], [#s.rolls])
} else { ([#label], [#exchange], [`#symbol`], [–], [–], [–]) }

#grid-table(
  columns: 6,
  align: (left, left, left, right, left, right),
  toprule,
  [Series], [Exchange], [Symbol], [Bars], [Period], [Rolls],
  midrule,
  ..db-row("wti", [WTI crude oil], [CME (NYMEX)], "CL.v.0"),
  ..db-row("brent", [Brent crude oil], [ICE Futures Europe], "BRN.v.0"),
  ..db-row("gold", [Gold], [CME (COMEX)], "GC.v.0"),
  ..db-row("sp500", [S&P 500 E-mini], [CME], "ES.v.0"),
  ..db-row("eurusd", [Euro / dollar], [CME], "6E.v.0"),
  bottomrule,
)

A future expires every month, so a series over two years has to pass from one contract to the next. The symbols ending in `.v.0` follow, at any moment, the contract with the highest volume. Databento does not adjust prices at the change of contract (the _roll_): the price jumps by the difference between the two contracts. Every bar keeps the identifier of its contract, and `06` excludes the returns that span a roll.

Other properties of the data:
- A bar exists only in minutes with at least one trade. There are no filler bars.
- The Brent series changes contract 60 times instead of about 23: near expiry the volume alternates between two maturities, and the series follows it back and forth. It also has 8,209 bars without a closing price, which `03c` drops.
- Databento marks some days as "degraded", with partly incomplete data: 10 days for the CME and 17 for ICE. Days with episodes among them: 15, 16 and 21 March, 10 April, 24 May 2026 (CME); 5 February and 8 May 2025, 10 and 23 March, 14 May 2026 (ICE).

The data are licensed and are not versioned. `figures.py` reads them from `data/prices/databento/`.

#sub[Synthetic series]

To test the analyses before the real series were available, `03b` generates three one-minute series with the trading hours of WTI, written to `data/prices/synthetic/`:

- *EUR/USD*: pure noise.
- *WTI*: noise, plus half of the EUR/USD return, plus the effect of the episodes. An episode with direction +2 lowers the price by 0.2% over the 15 minutes after the first post, −2 raises it by as much, ±1 by half. During June 2025 and March–June 2026 the effect is #n.tests.truth.crisis_multiplier times larger.
- *Gold*: noise, plus an effect of the episodes of the same sign and half the size, which does not change over time.

After every episode volatility doubles for an hour. Intensity, specificity and novelty have no effect. The true values are written to `truth.json`.

= Features

`episode_features.parquet`: #n.episodes episodes, #n.feature_columns columns. Steps A (deterministic features), B (novelty) and C (gold standard sample) are computed. Step D, automatic annotation with a language model, was tested and is on hold (@kaggle).

#sub[Novelty]

$ "novelty"_i = 1 - max_(j : t_i - 30 "days" <= t_j < t_i) cos(e_i, e_j), $
with $e_i$ the embedding of the episode text. Median #n.novelty.median, 10th percentile #n.novelty.p10, 90th #n.novelty.p90. The values are relative: the variable serves as a ranking and has no natural threshold. Near 0 is the same text republished; around the median the same topic with different content; above 0.6 content with no recent precedent.

#n.novelty_low episodes have novelty below 0.15, and #n.novelty_low_rt of them are reposts of Trump's own posts: duplicates, not repetitions of content. The link with text length is weak (Spearman −0.11), but length stays as a control.

#sub[Gold standard]

#n.gold episodes, sampled by quarter, annotated by hand following `annotations/gold_guidelines.md`. They are 145 rather than 200 because the quota per quarter is fixed and quarters with few episodes do not fill it.

The guidelines changed during the work. Version 1 asked for the expected effect on supply and treated claims of victory as known facts, hence 0. Annotating, it became clear that several kinds of post carry a signal on where the conflict is going, and they were labelled as positive. Version 2 (9 October 2026) describes the criteria actually applied: direction measures whether the conflicts affecting crude supply are moving toward resolution (positive) or escalation (negative). Claims that the war is won, US control of the Strait of Hormuz, and envoys or meetings aimed at peace count as positive; statements that Iran will never have a nuclear weapon count as negative.

The double annotation of 50 gold episodes by a second person is postponed: without it, there is no measure of how far two people agree on the same guidelines.

#sub[Manual annotation]

`data/features/manual_annotations.csv` holds all #n.manual.episodes episodes: the gold standard ones, then the others in random order, then those added by the updates in chronological order. #n.manual.annotated are annotated so far.

The file is not matched to the episodes through `episode_id`, which is a running number: a post inserted before the end of the corpus would shift every later number, and the judgements would end up on the wrong episodes without any error. The key is `first_post`, the identifier of the first post of the episode, which does not change. When an update adds a post to an episode already annotated (a post within 30 minutes of the last one), the text is updated, the judgements are kept and the `text_changed` column marks the episode for review.

= Automatic annotation: tests on Kaggle <kaggle>

The judgement variables were meant to be assigned by a language model running locally, validated against the gold standard, so that only the 145 gold episodes would need reading. Three runs were made on Kaggle, with Ollama on two Tesla T4 GPUs (16 GB each), temperature 0 and seed 42. The prompt contains the annotation guidelines, read from `annotations/gold_guidelines.md`, without the examples: they are gold episodes, and the model would see the right answers.

Agreement with the manual labels is measured on the 145 gold episodes with Cohen's kappa, weighted quadratically: a disagreement counts by the square of its distance, so confusing −2 with +2 weighs sixteen times as much as confusing −1 with −2. The model was to be used above 0.6, and with caution between 0.4 and 0.6.

#grid-table(
  columns: 8,
  align: (left, left, center, right, right, right, right, right),
  toprule,
  [], [], [], table.cell(colspan: 3, align: center)[Weighted kappa], [Sign], [Labels 0],
  [Run], [Qwen2.5], [Guidelines], [direction], [intensity], [specificity], [reversals], [given a direction],
  midrule,
  [1], [14B], [v1], [0.43], [0.51], [0.40], [10], [2],
  [2], [32B], [v1], [0.43], [0.44], [0.37], [13], [6],
  [3], [32B], [v2], [0.51], [0.45], [0.40], [21], [22],
  bottomrule,
)

Both models are quantized to 4 bits. A sign reversal is an episode with a direction in the manual annotation that the model labels with the opposite sign; there are 97 such episodes in the gold. The 32B model takes about 6 seconds per episode.

- *The size of the model does not help.* With the same guidelines, the 14B and the 32B models reach the same kappa, 0.43. The 14B model is the most cautious: it sets 57% of the corpus to 0, against 33% in the manual annotation.
- *Version 2 of the guidelines raises the kappa to 0.51*, mostly because the model recognises more positive episodes: 28 of 48, against 17 with version 1. But sign reversals rise to 21 of 97, and 22 of the 48 episodes labelled 0 receive a direction.
- *The reversals go mostly one way*: 17 of the 21 are de-escalation read as escalation. In run 1, "we consider winding down our great Military efforts" is labelled −2: the model reacts to military vocabulary rather than to where the message points.

A reversed sign is worse than noise. Direction enters the event study with its sign, so a reversal subtracts effect instead of diluting it, and the kappa understates the damage. The confidence declared by the model cannot be used to filter its answers: it is 0.98 on right and wrong answers alike.

Two caveats on the numbers. Version 2 of the guidelines was written after annotating the gold, to describe it, so the kappa of run 3 is somewhat optimistic. And the gold has a single annotator, so there is no ceiling to compare the model against.

Automatic annotation is on hold: the remaining episodes are annotated by hand. The output of run 1 is in `data/features/`, the logs of runs 2 and 3 in `notebooks/logs/`, and `notebooks/llm_scoring_kaggle.ipynb` reproduces them.

= First runs <runs>

The chain from the episode table to the price reaction was run on the synthetic series, to check that it returns the effects put in, and on the Databento series. Horizons, return measure, controls and the treatment of weekend episodes have not been fixed yet: the numbers below are first runs.

#sub[Episode table]

`05` joins the features of `04` with the manual annotations, through the identifier of the first post, and writes `data/features/episode_table_<date>.parquet`. It stops if an episode lacks judgements, is marked `text_changed` or breaks the conventions of the guidelines. It adds the sign of direction, direction × intensity, an indicator for direction ±2 and the number of reposts in the episode.

#sub[Event study]

`06` takes as time zero the first post of the episode and as base price the close of the last bar ending before it. For each horizon it computes:
- the raw return (`ret`), the log change of the price from the base, in percent;
- the abnormal return (`car`), the raw return minus the mean one-minute return of the hour before the post times the horizon;
- the pre-trend: the raw return from 60, 30, 15 and 5 minutes before the post up to the post (negative horizons).

An episode is left out of a horizon when a price is missing within two minutes of the required time, when the hour before has fewer than 30 one-minute returns, when the window spans a roll, or when another episode starts in the window or in the hour before it. Each return is then regressed on direction (OLS, heteroskedasticity-robust standard errors).

*Synthetic series.* Direction coefficient at 15 minutes, raw return:

#let es = n.tests.event_study
#let at-h(label, h) = es.at(label).find(r => r.horizon == h)
#let fixed(x, d: 3) = {
  let parts = str(calc.round(calc.abs(x), digits: d)).split(".")
  let dec = if parts.len() > 1 { parts.at(1) } else { "" }
  while dec.len() < d { dec += "0" }
  (if x < 0 { "−" } else { "" }) + parts.at(0) + "." + dec
}
#let pval(p) = if p < 0.001 { "<0.001" } else { fixed(p) }
#let fmt(x) = [#fixed(x.coef) (#fixed(x.se))]

#grid-table(
  columns: 3,
  align: (left, right, right),
  toprule,
  [Series], [True value], [Estimated (s.e.)],
  midrule,
  [WTI], [#n.tests.truth.wti, #(n.tests.truth.wti * n.tests.truth.crisis_multiplier) in crisis], fmt(at-h("synthetic_wti", 15).ret),
  [Gold], [#n.tests.truth.gold], fmt(at-h("synthetic_gold", 15).ret),
  bottomrule,
)

*Power.* 200 synthetic series for each effect size, without crisis periods; share of runs in which the coefficient at 15 minutes is significant at 5%:

#grid-table(
  columns: 4,
  align: (right, right, right, right),
  toprule,
  [Effect of a +2 episode], [True coefficient], [Mean estimate], [Power],
  midrule,
  ..n.tests.power.map(r => ([#r.effect%], [#r.true], [#r.estimated], [#pct(r.power)])).flatten(),
  bottomrule,
)

*Databento series.* Direction coefficient on the raw return, with the p-value below in brackets; `n` is the number of episodes used for WTI. Negative minutes are the pre-trend:

#let series = ("wti", "brent", "gold", "sp500", "eurusd")
#let p-cell(label, h) = {
  let r = at-h(label, h)
  if r == none { [–] } else { [#fixed(r.ret.coef) \ #text(size: 9pt)[(#pval(r.ret.p))]] }
}
#grid-table(
  columns: 7,
  align: (right, right, right, right, right, right, right),
  toprule,
  [Minutes], [WTI], [Brent], [Gold], [S&P 500], [EUR/USD], [`n`],
  midrule,
  ..es.wti.map(r => (
    [#r.horizon],
    ..series.map(s => p-cell(s, r.horizon)),
    [#r.ret.n],
  )).flatten(),
  bottomrule,
)

The same coefficient for WTI on the abnormal return, after the post:

#grid-table(
  columns: 3,
  align: (right, right, right),
  toprule,
  [Minutes], [Raw return], [Abnormal return],
  midrule,
  ..es.wti.filter(r => r.horizon > 0).map(r => ([#r.horizon], fmt(r.ret), fmt(r.car))).flatten(),
  bottomrule,
)

#sub[PCMCI+]

`07` builds a regular grid of 5-minute bins with four variables: the post signal (the sum of the directions of the episodes starting in the bin, 0 elsewhere) and the returns of WTI, gold and EUR/USD. Bins without a price are missing. PCMCI+ (Tigramite) is run with partial correlation, lags up to 20 minutes and $alpha = 0.01$. In the same bin a link between the post and a price can only go from the post to the price; lagged links are free.

Links involving the post signal (lag in minutes, partial correlation):

#let pc = n.tests.pcmci
#grid-table(
  columns: 6,
  align: (left, left, center, left, right, right),
  toprule,
  [Series], [Cause], [], [Effect], [Lag], [Value],
  midrule,
  ..pc.synthetic.map(r => ([synthetic], [#r.cause], raw(r.link), [#r.effect], [#r.lag], [#fixed(r.val)])).flatten(),
  midrule,
  ..pc.databento.map(r => ([Databento], [#r.cause], raw(r.link), [#r.effect], [#r.lag], [#fixed(r.val)])).flatten(),
  bottomrule,
)

In the generating model of the synthetic series the post affects WTI and gold only; prices do not affect the post.

#sub[CD-NOD]

CD-NOD (causal-learn) is run on one row per episode: direction, intensity, specificity, novelty and the 15-minute abnormal returns of WTI and gold, with time (days since the first episode) as context variable. An edge from time to a variable means that its mechanism changes over the period. The test is Fisher-z, $alpha = 0.01$; a return cannot cause the annotated variables.

- Synthetic: #n.tests.cdnod.synthetic.map(e => raw(e)).join(", ").
- Databento: #n.tests.cdnod.databento.map(e => raw(e)).join(", ").

With the kernel test (KCI) on the same synthetic episodes, the dependence between the WTI and gold returns is not detected (p = 0.41, against 0.004 with Fisher-z). The change of the WTI effect in the crisis periods, varying its size in the synthetic series:

#grid-table(
  columns: 3,
  align: (left, left, left),
  toprule,
  [Effect in crisis], [Fisher-z], [KCI],
  midrule,
  [×2], [no time edge], [no time edge],
  [×4], [no time edge], [no time edge],
  [×8], [no time edge], [time → WTI],
  bottomrule,
)

= Decisions to take together <decisions>

+ *The dependent variable and its measure* (@prices, @runs). Five series are downloaded. To decide: WTI or Brent, the horizons, raw or abnormal return and the window for the expected return, the controls, the treatment of weekend episodes.
+ *Rule or rule plus classifier.* The semantic second stage improves precision, but the definition of event becomes what the model learned from 482 examples, and it must be frozen and declared like a prompt.
+ *The boundary of the topic.* Pump prices, market comments, Greenland: today they are excluded by the annotation criterion. To be confirmed.
+ *The corpus cutoff date.* Every update changes the counts in this report. Before writing the results, the corpus must be closed at a fixed date.
+ *The Eastern-time week.* Declared exception in the validator or documented anomaly.

= Planned work

+ Remove reposts of his own posts during cleaning; add a column distinguishing reposts of other accounts.
+ Make the double-post filter conditional on the presence of text.
+ Extend the term lists for Russia/Ukraine and Venezuela, the two gaps found by the audit.
+ Have a second person annotate the 50 double episodes of the gold standard, before the final version.
+ Freeze the features and record the date.

= Change log

#let entry(date, text) = [/ #date: #text]

#entry[16/10/2026][Futures prices bought from Databento and downloaded with `03c`: WTI, Brent, gold, S&P 500, euro/dollar, one-minute bars from 24 November 2024. `06` excludes returns spanning a change of contract, adds the pre-trend (returns in the hour before the post) and runs the regressions on both raw and abnormal returns; an episode is also left out of the pre-trend if another episode started in the hour before the window. Bars without a price are dropped. In `07` a price cannot cause a post in the same bin. Sections on price data and first runs (@prices, @runs). Guidelines also in Typst (`annotations/gold_guidelines.typ`).]

#entry[15/10/2026][Script `03b` for synthetic prices with a known effect of the episodes; `07` with PCMCI+ (Tigramite) and CD-NOD (causal-learn, new dependency). In CD-NOD the test is Fisher-z and returns cannot cause the annotated variables. `query/plot_series.py` plots the price series with the episodes marked by direction.]

#entry[14/10/2026][Script `05` for the episode table and `06` for the event study, with a power test on synthetic series. In `03` the end of the period is the current day, the current month is downloaded again at each run, an empty file counts as a failure, the requests are spaced out, and a month is no longer skipped because its start date appears in the name of the previous month's file. The full Dukascopy download was refused by the server (HTTP 429).]

#entry[12/10/2026][Script `update.py` for daily updates: new posts from CNN, rule, features, new episodes added to the manual annotation file. The annotations are matched to the episodes through the first post instead of `episode_id`. The cache of the text embeddings is now tied to the texts, not to the number of episodes; `most_similar_episode` holds an `episode_id` instead of a row number. Corpus updated to 12 October 2026: 7 new episodes to annotate.]

#entry[11/10/2026][Automatic annotation on hold. Three runs of local language models on Kaggle (Qwen2.5 14B and 32B) did not reach sufficient agreement with the manually annotated gold standard: the best reached a weighted kappa of 0.51 on direction, but reversed its sign in about one directional episode out of five (@kaggle). The remaining episodes will be annotated manually.]

#entry[9/10/2026][Gold standard annotated: 145 episodes. Annotation guidelines version 2: direction measures where the conflicts affecting supply are heading.]

#entry[5/10/2026][Repository translated into English: files, folders, data columns and the values `dentro`/`confine` (now `inside`/`boundary`). Data contents unchanged. Old-to-new names in `GLOSSARY.md`.]

#entry[3/10/2026][Audit rerun on the full corpus. Annotation guidelines for the gold standard (`annotations/gold_guidelines.md`).]

#entry[2/10/2026][Rule v6: removed `mine`, which also fired as a pronoun ("not mine"). Semantic novelty and gold standard sample computed. Scripts `query/series_hours.py` and `query/post_coverage.py` on the hourly coverage of the series.]

#entry[1/10/2026][#thou(n.posts_cnn) posts integrated from the CNN archive (`00b`), with the timestamp from the link. Rule v4: added `nigeria` and `tariff`. Rule v5: same rule, sample regenerated on the integrated corpus.]

#entry[29/9/2026][Rule v3: removed `market`, `markets` and the price terms (`down`, `boom`, `plummet`, `dropping`); they comment on prices that have already moved. Added `regime change`, `ultimatum`, `deadline`, `clock is ticking`, `to flow`. In v2 a missing comma had merged `dropping` and `regime change` into a single term (`droppingregime change` in the versions table): neither was active.]

#entry[29/9/2026][Rule v2: added `obliterate` and its variants.]

#entry[25/9/2026][Created the `annotations/` folder: each version keeps the rule and the annotated sample; `fill_labels.py` carries labels already given over to new samples. Rule v1 annotated, already without `war`: too generic, it fired on any war.]

#entry[21/9/2026][First draft. Fixed the parsing of 12-hour times in `00`; recovered 12 posts lost to the timestamp format in `01`.]
