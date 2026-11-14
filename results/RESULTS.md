# Test results: which bot to submit

**Submit the Market Reader (now version 2, see the last section).** Version 1 beat the other two bots in every test, by a margin far outside the noise. It averaged 101.2 points per game against the test opponents, against 82.3 for Evolved Weights and 75.8 for the Fair-Value Pacer.

The main caveat: the opponents are my stand-ins for classmates' bots, not the real entries. The ranking of the three bots is solid; the absolute scores will differ in the real tournament.

## How the tests were run

- **Engine:** the course harness's own rules and scoring code, called in-process for speed. A check confirms it gives exactly the same scores as the real process-isolated harness at 3, 4 and 5 players.
- **Format:** a "series" is one fixed seating playing 15 games, with bots keeping their memory, as in the tournament.
- **Coverage:** 3, 4 and 5 players and all five value charts, about 172,000 games in total.
- **Fair comparison:** the three bots were compared on the same seatings, opponents and deals.
- **Separate deals:** tuning, validation and final tests each used their own deals.
- **Opponents:** eleven test bots. Seven were used in tuning. Four were held back (AlgoGemBot, HalfBudgetBot, AggressiveBot, CollectorBot) to see how the bots cope with styles they were not tuned against.

## Results

### Against all test opponents (9,000 games per bot)

| Bot | Points per game | 95% range | Win rate |
|---|---|---|---|
| **Market Reader** | **101.2** | 98.7 to 103.6 | **89.3%** |
| Evolved Weights | 82.3 | 80.4 to 84.4 | 72.2% |
| Fair-Value Pacer | 75.8 | 72.8 to 78.6 | 52.5% |
| ThirdValueBot (reference) | 74.8 | 73.0 to 76.4 | 62.5% |
| HeuristicBot (reference) | 49.2 | 47.9 to 50.3 | 18.5% |

On the same series, the Market Reader scored 18.8 more points per game than Evolved Weights (95% range 18.0 to 19.7) and was ahead in 97.7% of series. It led in every player count and on every chart.

| Bot | 3 players | 4 players | 5 players | Chart A | Chart B | Chart C | Chart D | Chart E |
|---|---|---|---|---|---|---|---|---|
| Market Reader | 122.9 | 93.5 | 87.2 | 99.0 | 95.9 | 83.8 | 120.9 | 106.4 |
| Evolved Weights | 103.6 | 75.2 | 68.2 | 80.9 | 77.4 | 68.8 | 97.4 | 87.2 |
| Fair-Value Pacer | 97.4 | 66.5 | 63.4 | 71.0 | 71.9 | 59.0 | 94.4 | 82.3 |

### Against opponents never used in tuning (4,500 games per bot)

| Bot | Points per game | 95% range | Win rate | Lead over table average |
|---|---|---|---|---|
| **Market Reader** | **87.1** | 84.5 to 89.6 | **91.2%** | +48.4 |
| Evolved Weights | 66.6 | 64.4 to 68.7 | 58.6% | +21.5 |
| ThirdValueBot (reference) | 64.9 | 62.7 to 66.9 | 58.4% | +20.8 |
| Fair-Value Pacer | 49.3 | 46.6 to 52.1 | 26.2% | -4.3 |

This is the most telling test. The Market Reader kept its lead. The Fair-Value Pacer fell below the table average: tuning set it to bid only about 29% of value, which works on passive opponents and loses most auctions to anyone who bids more.

### All three at one table (13,500 games)

| Bot | Points per game | Win rate | 3 players | 4 players | 5 players |
|---|---|---|---|---|---|
| **Market Reader** | **86.2** | **76.9%** | 101.6 | 81.1 | 76.0 |
| Evolved Weights | 65.2 | 20.1% | 88.8 | 60.1 | 46.7 |
| Fair-Value Pacer | 31.7 | 0.8% | 39.5 | 29.5 | 26.1 |

### One bot against a table of copies of another (win rate)

An even match is about 29% (3 and 4 players mixed).

| Row vs copies of | Fair-Value Pacer | Market Reader | Evolved Weights | HeuristicBot | ThirdValueBot | AggressiveBot |
|---|---|---|---|---|---|---|
| Fair-Value Pacer | 28.9% | 0.0% | 0.6% | 78.4% | 2.6% | 86.1% |
| **Market Reader** | 97.9% | 31.7% | 49.5% | 94.1% | 69.6% | 98.9% |
| Evolved Weights | 78.3% | 31.9% | 30.2% | 82.6% | 39.6% | 91.9% |

The Market Reader is never below even. Against a table of Evolved Weights copies its lead is small (49.5% wins, 9 points over the table), so strong classmate bots would narrow the gap.

### Simulated league, chart A, all bots in one pool

Random line-ups drawn from the three bots plus all eleven test opponents, about 5,000 games per bot.

| Rank | Bot | Points per game | Win rate |
|---|---|---|---|
| 1 | **Market Reader** | 94.7 | 87.0% |
| 2 | Evolved Weights | 74.4 | 56.6% |
| 3 | AlgoGemBot | 73.8 | 54.4% |
| 4 | ThirdValueBot | 65.4 | 40.5% |
| 5 | Fair-Value Pacer | 59.4 | 32.3% |
| 6 | NaiveChartBot | 56.1 | 24.6% |
| 7 | CollectorBot | 53.2 | 17.4% |
| 8 | InvestorBot | 43.7 | 5.7% |
| 9 | HeuristicBot | 43.2 | 7.0% |
| 10 | HalfBudgetBot | 42.2 | 9.8% |
| 11 | AggressiveBot | 39.1 | 6.0% |
| 12 | OneBot | 37.4 | 7.9% |
| 13 | ZeroBot | 27.7 | 0.2% |
| 14 | RandomBot | 27.4 | 1.7% |

## What the tests showed

- **Reading opponents is worth about 19 to 25 points a game** over the other two designs. That matches the evidence in [BOT_STRATEGIES.md](../BOT_STRATEGIES.md).
- **Cheap bidding beats "fair" bidding in this field.** The simple fixed-bid AlgoGemBot and the one-third-of-value bot finished 3rd and 4th in the league. Bots that pay 75% or more of value finished near the bottom.
- **Memory across games helps a little.** The Market Reader averaged 98.4 points in games 1 to 3 of a series and 101.7 in games 10 to 15.
- **Tuning chose a high coin premium for the Market Reader** (1.84 at the start of a game, against the 0.5 I started from) and no value shading.
- **The Fair-Value Pacer was over-tuned** to the tuning opponents. It is useful as a baseline, not as an entry.

## Limits

- The test opponents are guesses at what classmates will submit. A field of strong, adaptive bots would shrink the Market Reader's margin, as the copies test shows.
- Tuning rewarded points plus a bonus for wins. If the organiser weights wins very differently, retuning may help.
- The harness's default one-second time limit was checked: every decision in the checks took under a quarter of a second, and the real isolated harness logged no timeouts or errors.
- Submitted bots are public, so a classmate could read the Market Reader and bid one coin above its cover bids. I did not test against a bot written to exploit it.

## Version 2 of the Market Reader

Eight possible improvements were built as switches and each was tested alone against version 1 on the same 450 series (6,750 games). The pool was tougher than before: the eleven test opponents plus Evolved Weights, the Fair-Value Pacer and the Market Reader itself. Version 1 scored 90.8 points per game there.

| Improvement | Change in points per game | 95% range | Outcome |
|---|---|---|---|
| 1. Retune with wider ranges and a stronger pool | +0.14 | -0.17 to +0.44 | Small gain; folded into 6 |
| 2. Look-ahead coin pricing, full strength | -8.41 | -9.39 to -7.45 | Rejected at full strength |
| 2. Look-ahead blended in at 25% | +0.25 | -0.12 to +0.61 | Kept at a small weight chosen by tuning (4% to 14%) |
| 3. Tune against real submissions | n/a | n/a | No submissions exist yet |
| 4. Infer rivals' hands from their bids | -0.12 to -0.55 | all at or below zero | Rejected, switched off |
| 5a. Separate one-gem and two-gem lots | -0.16 | -0.43 to +0.09 | Rejected, switched off |
| 5b. Treat all-in bids as a lower bound | -0.65 | -0.93 to -0.37 | Rejected, switched off |
| 5c. Reset when a seat's behaviour changes | +0.47 when seats swap, 0.00 otherwise | +0.29 to +0.66 | Kept |
| 6. Separate settings per player count | +1.52 | +1.14 to +1.87 | Kept; the main gain |
| Small: mission race penalty | +0.17 | -0.01 to +0.38 | Kept at a mild level chosen by tuning |
| Small: mission supply check | -0.02 | -0.09 to +0.06 | No effect, switched off |
| Small: charge for the forced reveal and lost tie order | -0.52 to -2.51 | all below zero | Rejected; tuning chose a small bonus for winning instead |

Rows 1 and 6 are from 600 series on selection deals. The look-ahead is an estimate built from gems left, going prices and rivals' coins, not an exact solution of the endgame.

### Version 2 against version 1 on fresh deals

Deals here were used for nothing else.

| Test | Version 1 | Version 2 | Change | 95% range |
|---|---|---|---|---|
| All opponents incl. strong bots (9,000 games) | 93.5 points, 78.9% wins | 95.0 points, 84.4% wins | +1.45 | +1.08 to +1.82 |
| Opponents never used in tuning (9,000 games) | 86.6 points, 91.2% wins | 87.5 points, 92.8% wins | +0.88 | +0.59 to +1.17 |
| Seats swap mid-series (4,500 games) | 90.6 points, 75.9% wins | 92.6 points, 81.5% wins | +2.00 | +1.54 to +2.47 |
| Both at the same table (9,000 games) | 62.8 points, 34.3% wins | 70.2 points, 58.1% wins | +7.4 | not computed |

Version 2 is better in every test, by 1 to 2 points per game against other bots and by more when the two meet directly. The gain is real but modest: most of the bot's strength was already in version 1. The earlier tables in this document are for version 1.

Classmates' bots can be pulled in with `python3 scripts/fetch_submissions.py` once they are submitted. As of Nov 13 there were none.

## Reproduce

```bash
python -m arena.ablate
```

```bash
python -m arena.compare_tuned confirm
```


```bash
python -m arena.evaluate
```

```bash
python -m arena.report
```

Raw numbers are in `results/evaluation.json`. Tuned settings and their validation scores are in `results/tuned_*.json`.
