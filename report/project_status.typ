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

/ `03`  prices: Downloads the one-minute price series. On hold, pending a decision on which series to use.

/ `04`  features: Measures each episode: time, length, emphasis, novelty with respect to recent episodes, and the variables that require reading: the direction of the conflicts affecting supply, intensity, specificity. These are annotated by hand.

/ `update`  update: Runs `00b`, `01` and `04` in sequence and adds the new episodes to the manual annotation file. It is meant to be run daily, because the situation keeps changing.

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
  [03 prices], [on hold], [test on March 2025],
  [04 features], [A, B, C done; D on hold], [#n.feature_columns columns; #n.manual.annotated of #n.manual.episodes episodes annotated],
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

= Price data

On hold. Test on March 2025, files in `download/`. A bar counts as real if it is not inside a constant-price stretch of at least one hour: Dukascopy fills closed-market periods by repeating the last price.

- *Brent*: unusable. Every Tuesday and Thursday of the month is missing, and the days present stop at 21 UTC.
- *WTI*: covers from Sunday 22 UTC to Friday 21, with a daily break between 21 and 22. The Sunday bars before 22 are filler.
- *Gold*: same structure, downloaded for one week only.

#pct(n.wti_coverage) of episodes fall at hours when WTI has a price (`query/post_coverage.py`). The `us_market_open` variable (#pct(n.us_market) of episodes) measures the equity session, not the oil one, and does not indicate how many episodes are lost.

Open questions:
+ *WTI coverage* beyond March 2025, not verified.
+ *Nature of the data*: these are a broker's CFD quotes, not exchange prices. Over windows of minutes the difference should be negligible, but it needs to be endorsed.
+ *Episodes without a price*: about a third. Accept the loss, look for a more continuous instrument, or change the design for that slot?

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

= Decisions to take together <decisions>

+ *The price series* (section 8). Until it is decided, the dependent variable does not exist.
+ *Rule or rule plus classifier.* The semantic second stage improves precision, but the definition of event becomes what the model learned from 482 examples, and it must be frozen and declared like a prompt.
+ *The boundary of the topic.* Pump prices, market comments, Greenland: today they are excluded by the annotation criterion. To be confirmed.
+ *The corpus cutoff date.* Every update changes the counts in this report. Before writing the results, the corpus must be closed at a fixed date.
+ *The Eastern-time week.* Declared exception in the validator or documented anomaly.

= Planned work

+ Remove reposts of his own posts during cleaning; add a column distinguishing reposts of other accounts.
+ Make the double-post filter conditional on the presence of text.
+ Extend the term lists for Russia/Ukraine and Venezuela, the two gaps found by the audit.
+ Annotate by hand the remaining episodes in `data/features/manual_annotations.csv`, then bring the manual variables into `episode_features.parquet`.
+ Have a second person annotate the 50 double episodes of the gold standard, before the final version.
+ Freeze the features and record the date.

= Change log

#let entry(date, text) = [/ #date: #text]

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
