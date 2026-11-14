# Megagem-Board-Game-Bot

Three bots for Megagem and a testing ground that simulates the y/cs Catalyst bot tournament.

- **What the bots do and why:** [BOT_STRATEGIES.md](BOT_STRATEGIES.md)
- **Test results and which bot to submit:** [results/RESULTS.md](results/RESULTS.md)

## Layout

| Path | What it holds |
|---|---|
| `otis_bots/otis_core.py` | Shared logic: gem values, mission value, coin pricing, reveal choice |
| `otis_bots/fair_value_pacer.py` | Bot 1, Fair-Value Pacer |
| `otis_bots/market_reader.py` | Bot 2, Market Reader |
| `otis_bots/evolved_weights.py` | Bot 3, Evolved Weights |
| `otis_bots/market_reader_v1.py` | Frozen first version of Bot 2, kept as a yardstick |
| `otis_bots/zoo.py` | Eleven test opponents |
| `arena/engine.py` | Runs games on the real harness engine, in-process for speed |
| `arena/tune.py` | Tunes a bot's numbers on training deals |
| `arena/evaluate.py` | Final tests on separate deals |
| `arena/report.py` | Prints the test results as tables |
| `arena/ablate.py` | Tests one change at a time against the current bot |
| `arena/compare_tuned.py` | Compares retuned versions with the first tuned bot |
| `tests/` | Checks for the maths, legal moves, harness match and export |
| `scripts/` | Harness setup and export to the Catalyst fork |

The course harness is fetched into `harness/` and is not committed here.

## Setup

Needs Python 3.10 or newer and no other packages. With `uv`:

```bash
./scripts/setup_harness.sh
```

```bash
uv run --no-project --python 3.12 python -m unittest discover -s tests -v
```

## Run the testing ground

Run these from the repo root with Python 3.10+ (prefix with `uv run --no-project --python 3.12` if needed).

```bash
python -m arena.evaluate --quick
```

```bash
python -m arena.report results/evaluation_quick.json
```

Drop `--quick` for the full run. To retune a bot:

```bash
python -m arena.tune MarketReader
```

To pull in classmates' submitted bots (into the uncommitted `harness/` folder):

```bash
python3 scripts/fetch_submissions.py
```

Read each fetched file before running it, then list it in `CLASS_BOTS` in `otis_bots/zoo.py`.

To test your own opponent, add a class to `otis_bots/zoo.py` and list its name in `TRAIN_ZOO` or `HOLDOUT_ZOO`.

## Submit to the Catalyst fork

The bot files work unchanged inside the harness. Clone your fork of `megagem-harness`, then copy the chosen bot in and register it:

```bash
python3 scripts/export_to_fork.py /path/to/your/megagem-harness MarketReader
```

That copies `otis_core.py` and the bot's file into `src/bot_definitions/` and adds the import to `src/custom_bots.py`. Leave the bot name off to export all three. Then commit in the fork and open the pull request.
