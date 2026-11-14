# Megagem bot strategies: three candidates

**Recommendation: build Bot 2, the Market Reader.** It contains Bot 1 as its fallback, so build Bot 1 first and grow it into Bot 2. Borrow Bot 3's tuning method to set Bot 2's handful of numbers.

All three bots are now built and tested. The tests confirmed Bot 2 as the strongest; see [results/RESULTS.md](results/RESULTS.md). The rest of this document is the design reasoning written before the tests, and the expected ranks of Bots 1 and 3 turned out the other way round.

## What the tournament rewards

- Round robin, 3–5 players, 10–20 games per lineup. The organiser said to optimise total points.
- Python standard library only. Each decision has a time limit (1 second by default, possibly 5–20 in grading).
- A bot's memory carries over between games in the same lineup.
- Submitted bots are public, so other entrants can read yours.

## Evidence found online

Megagem is new, so there is little written about it. Four sources are useful.

| Source | What it is | What it shows |
|---|---|---|
| [Strategy blog](https://djdumpling.github.io/2026/08/09/megagem.html) and [MegagemBench](https://github.com/djdumpling/MegagemBench) | Controlled experiments on thousands of 3-player games | Greedy per-auction bidding lost about 5 points a game. Charging each coin at 1.5× and predicting a range of opponent bids gained about 12. Simulating the rest of the game gave no measurable gain. |
| [Lachy-Dauth/mega-gem](https://github.com/Lachy-Dauth/mega-gem) (also forked as [L-ogii/mega-gem](https://github.com/L-ogii/mega-gem)) | A Python engine with six bots, four tuned by a genetic algorithm, and a benchmark table | See the table below. Opponent modelling added strength at each step. The tuned bots bid only about a quarter to a third of a gem's expected value. |
| [AlgoGem bot](https://github.com/ryanboanlai/algogem-auction-bot) | A fixed-rule bot from a Jane Street summer programme | Bids 4 per gem, 3 or 6 on loans and investments. A realistic picture of a simple classmate bot. |
| [Rules manual](https://drive.google.com/file/d/1UJ5vC_hiZxsjL1OTeSHdk22Rgfb9j4BM/view) | Official rules with editor notes | Roughly doubling your starting coins puts you in contention. |

Benchmark from the mega-gem repo: win rate of one challenger against three copies of an opponent, 4 players, 200 games per cell. An even match is 25%.

| Challenger | vs Random | vs Heuristic | vs Evo2 | vs Evo3 |
|---|---|---|---|---|
| Heuristic (bids 0.75 × expected value) | 80.5% | 20% | 4.5% | 3% |
| Evo2 (tuned weights, no opponent model) | 80.5% | 79.5% | 18.5% | 19% |
| Evo3 (adds a running read of opponent prices) | 96% | 87.5% | 39% | 18% |
| Evo4 (adds per-opponent bid prediction) | 95.5% | 85.5% | 44% | 46.5% |

Two cautions on that repo. Its tuning runs were short (5 generations, 4 players only). I did not check its rules engine against the tournament harness.

## Ideas all three bots share

- **Gem value.** A colour's final value depends on how many of it were dealt into hands. Each bot computes the expected value from its own hand and everything public, averaging over the possible counts.
- **Missions.** Add the mission points a gem would complete, plus part-credit for progress.
- **Safe output.** Always return a whole number within budget. The harness turns anything else into a bid of 0.

## Bot 1: Fair-Value Pacer

**Idea:** work out what each lot is worth, then bid a fixed share of it, with coins priced above face value.

How it bids:
- **Gems:** bid = share × (value − 2) ÷ (1 + premium).
  - The premium starts near 0.5 and falls to 0 by the last round.
  - The share starts near 0.6, which puts early bids at about 40% of value.
- **Investments:** bid up to bonus ÷ premium, capped at coins on hand. That is up to 10 or 20 coins early, and everything spare late.
- **Loans:** bid up to premium × loan ÷ (1 + premium). That is about 3 on a 10 loan and 6 or 7 on a 20 loan early, falling to 0 late. The AlgoGem bot's hand-picked 3 and 6 match this.
- **Reveal:** show a colour with no gems left to auction, or one it is not collecting.

Pros:
- About 150 lines, fast, and easy to test and explain.
- Hard to exploit, because it never pays more than a lot is worth.
- Beats bots that bid nothing, bid randomly, or misjudge gem values.

Cons:
- It ignores what opponents bid. Against passive bots it pays 5 where 1 would win.
- Against aggressive bots it keeps losing auctions by a coin or two.
- Its share and premium are guesses until tuned.

## Bot 2: Market Reader (recommended)

**Idea:** Bot 1's valuation, plus a model of each opponent, so it bids just enough to win.

How it bids:
- **Opponent model.** It records every bid each opponent makes, as a fraction of the lot's public value, split by auction type. From that it predicts a range of likely bids, capped at the coins that opponent holds.
- **Bid choice.** For every legal bid it computes (value − 2 − (1 + premium) × bid) × chance of winning, and picks the best. The chance of winning uses the tie order, which is public.
- **Cover bids.** When opponents are short of coins, it bids the most any of them can afford plus 1, or matches it when the tie order favours it.
- **Endgame.** In the last few rounds it works out the remaining auctions exactly.
- **Memory.** It keeps its opponent models between games and resets a seat's model when that seat starts behaving differently.
- **Fallback.** With no data on an opponent, it bids as Bot 1.

Pros:
- Both independent sources show opponent modelling is where the points are: +12 a game in the blog, and Evo3 and Evo4 over Evo2 in the benchmark.
- It adapts to each lineup, which matters because the tournament mixes many bot styles.
- It takes cheap gems from passive bots, which total-points scoring rewards most.
- 10–20 games per lineup gives it roughly 170–340 rounds of bids to learn from.

Cons:
- About three times the code of Bot 1, with more places for bugs.
- Its first few rounds against a new opponent are no better than Bot 1.
- A random or shifting opponent can mislead the model. The fallback and a minimum sample size limit the damage.
- If opponents read its public code, they can bid one coin above its predictable cover bids.

## Bot 3: Evolved Weights

**Idea:** let a genetic algorithm find the bidding formula. This is the mega-gem repo's approach.

How it bids:
- Three small formulas, one each for gems, investments and loans.
- Each is a weighted sum of features: rounds left, own coins, opponents' coins, gem value and its spread, and recent opponent prices.
- The weights come from breeding thousands of candidates against a pool of test bots.

Pros:
- It can find trade-offs nobody thought to code. It discovered low bids of about a third of value without being told.
- The finished bot is tiny and runs instantly.
- The tuning tool is reusable for the other bots.

Cons:
- It is only as good as the pool it trained against. The blog's trained bots learned tricks against one fixed opponent that did not carry over.
- The benchmark shows this: Evo2 beats the older tuned bot 71.5% of the time, while the stronger Evo4 manages only 50%.
- It needs a fast simulator and hours of runs, across 3, 4 and 5 players and five value charts.
- The weights are hard to interpret, so bad behaviour is hard to diagnose.
- A straight-line formula cannot express "bid their coins plus 1".

## Comparison

| | Bot 1: Fair-Value Pacer | Bot 2: Market Reader | Bot 3: Evolved Weights |
|---|---|---|---|
| Uses opponents' bids | No | Yes, per opponent | Only as a running average |
| Build effort | Low | Medium | Medium, plus long tuning runs |
| Strength vs simple bots | Good | Best | Good |
| Strength vs strong bots | Fair | Good | Depends on training pool |
| Risk | Leaves points unclaimed | Bugs, misled model | Overfitting |
| Expected rank | 3rd | 1st | 2nd |

## Why Bot 2

- The largest measured gains in both sources came from pricing coins above face value and modelling opponent bids. Bot 2 does both.
- It cannot do much worse than Bot 1, because it falls back to Bot 1 when unsure.
- Bot 3's best version (Evo4) is strong because it predicts opponents too. Bot 2 does that directly, per opponent, and can make exact cover bids.

## Build and test plan

1. Install Python 3.10 or newer and run the harness.
2. Build test opponents: zero-bid, fixed-bid, random, the 0.75 × value heuristic, the AlgoGem rules, and a one-third-of-value bidder.
3. Build Bot 1 and confirm it beats those opponents on total points.
4. Add Bot 2's parts one at a time. Keep each only if it gains points on the same deals with seats rotated.
5. Tune the share, premium and value offset with a small genetic or grid search across 3, 4 and 5 players and all five charts.
6. Submit late, since submissions are public.
