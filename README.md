# traders_analysis

**Time spent:** ~2 hours
**LLM use:** I used Claude (Claude Code) throughout. I started by using it to understand the problem: general trading background, the concepts in the data (contract sizes and point values, CME sessions, commissions, open positions) and how the tables relate to each other. Then I worked through the tasks making the decisions myself: what "unusually bad" means, which signals to use, the scoring rules and thresholds, who to exclude or list separately, and the label and metric for Task 2. I asked Claude for ideas along the way and chose among them. Claude wrote all of the code (loader, P&L, notebook, backtest) and drafted the README text from my decisions.

## Background

### Self-ratings

1 = never used · 2 = tutorial-level · 3 = shipped work with it · 4 = comfortable in production · 5 = could teach it

- Python: 4
- pandas: 4
- polars: 1
- SQL: 3
- Feature engineering: 3
- Model evaluation and validation: 2
- Time-series / sequential data: 4
- Taking a model into production: 2
- Experiment tracking (MLflow, Weights & Biases): 2
- Probabilistic models: 4

### Five short answers

- **What kind of modelling problem am I strongest with?**
Time-series and sequential problems where there is structure to model explicitly: forecasting, state filtering, probabilistic models. I also enjoy constrained optimisation problems.

- **What would be the steepest learning curve here?**
The trading domain. I have the mathematical and modelling foundation; rigorous evaluation and production deployment are areas I'm still growing in. What I need to build is intuition for how prop accounts, futures and risk rules behave in practice. My way of learning is to read, ask a lot of questions of the people who know the business, and build small prototypes early.

- **A core strength you haven't asked about:**
My mathematical background. I can read a paper and understand where a method comes from, not just how to call it. I also have practice working with non-technical teams, translating model results into decisions.

- **What I most want to do day-to-day:**
Model and experiment with real data: form hypotheses, build and validate models, and see what I build get used and have an impact. I like a balance between research and taking things to production, in a team where I can learn from more experienced people and be challenged intellectually.

- **What I most want to avoid:**
Highly repetitive work with no room to improve the method (e.g. only reports or dashboards), and environments where models get built but nobody uses them. I also prefer to avoid cultures that value hours in the chair over results; I do my best work with autonomy and some flexibility.

## Task 1 — Find the traders in trouble

Code: [`task1_traders.ipynb`](task1_traders.ipynb) runs top to bottom. It uses [`load.py`](load.py) (loads the data and assigns each fill to its CME session) and [`pnl.py`](pnl.py) (P&L per account and session), and reads the data from [`dataset/`](dataset/).

To run it (Python 3.11+, from the repo root):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
jupyter nbconvert --to notebook --execute --inplace task1_traders.ipynb
```

### What "unusually bad" means here

A session is unusually bad when, **compared with the trader's own history**:

1. they lost far more than they normally do,
2. they took on more risk than they ever have, or
3. they broke an account rule for the first time.


### Scoring: three independent questions, 0–3 points each

Many signals describe the same event (switching from MCL to CL lights up "big loss", "new product", "more risk" and "% of account lost" at once). Adding them all up would count one event several times, so the score asks three separate questions:

| Question | Measure | 0 | 1 | 2 | 3 |
| --- | --- | --- | --- | --- | --- |
| **A. Unusual loss for this trader?** | `pnl_z`: today's P&L vs. their own mean, in their own standard deviations | > −2 | −2 to −3 | −3 to −5 | ≤ −5 |
| **B. More risk than ever before?** | today's leverage / their highest previous leverage | < 1.2x | — | 1.2x–2x | > 2x |
| **C. Broke a rule for the first time?** | exceeded `max_position_size`, never had before | no | — | — | yes |

**Score = A + B + C** (0–9). **Tie-break:** most negative `pnl_z` first (money already lost outranks risk not yet realised).

### Decision rules

1. **Unit:** one row per trader per CME session (17:00–16:00 Chicago time, named after the closing day), summing all their accounts and instruments. Grouping by UTC date is wrong: it splits sessions and, for example, moves T-020's evening trades into the previous day.
2. **Minimum history:** traders with **fewer than 5 sessions before today** are excluded (T-024, T-025, T-026). Without history there is no "normal" to compare against.
3. **P&L:** realised (average-cost) + open positions marked at the cut − commissions, in USD using each contract's point value. Checked against an independent cash-flow calculation (max difference ~1e-10). Every historical session ends flat, so no settlement prices are needed; the code asserts this.
4. **"Normal" = the trader's own history, excluding today** (mean and std of P&L; median and max of leverage).
5. **Risk = leverage** (max exposure in USD / account balance), so that contracts of different sizes (MNQ vs NQ, MCL vs CL) and accounts of different sizes are comparable. Counting contracts would miss T-023, who traded the same number of contracts as always but in a contract 10× larger.
6. **Risk only scores when it exceeds the trader's maximum**, not their median, so traders who routinely alternate between micro and full-size contracts (T-001 to T-007) are not flagged for doing what they always do.
7. **A rule breach only scores if it is new.** Recurring breaches (T-013) are not an "unusual session"; they go to a separate control list.
8. **Today is compared against full days.** The cut is at 9:30 Chicago time, but today's session already contains a full day of activity (see data notes), and comparing against "the same time of day" made every trader look 2–3× more active than normal.
9. **Demo and restricted accounts stay in the scoring.** The demo account (T-043) and the restricted account with zero buying power that still trades today (T-041) are scored like any other; neither ends up in the top ten. The closed account (T-040) has no activity today.
10. **Thresholds (−2, −3, −5, 1.2x, 2x) are judgement calls**, not derived from data, so I tested whether moving them changes the list (below).

### The ten, worst first

| # | Trader | A | B | C | Score | Why |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | T-023 | 3 | 3 | 0 | 6 | Switched from MCL to CL (10× larger contract) with the same contract count: 7.4× their usual exposure, 6× their previous max. Lost $2,486 (usual swing ±$387) and holds an open short losing $2,340. |
| 2 | T-022 | 0 | 3 | 3 | 6 | Always traded 12 ES; today 32 against a limit of 20 — first breach. Leverage 60× the account vs. a previous max of 22.6×. Flat on the day (+$2), so a loss-based list would never show them. |
| 3 | T-009 | 2 | 3 | 0 | 5 | Switched from MES to ES: leverage 11.3× vs. previous max 4.7×. Lost $670 (usual swing ±$121), their worst session. |
| 4 | T-018 | 3 | 0 | 0 | 3 | Lost $1,517; usual swing ±$158 (z = −8.9). 4.3× their previous worst day. |
| 5 | T-019 | 3 | 0 | 0 | 3 | Lost $1,559; usual swing ±$305 (z = −5.1). 3.2× their previous worst day. |
| 6 | T-011 | 2 | 0 | 0 | 2 | Lost $759 (z = −4.6), 3.0% of the account; previous worst 1.0%. |
| 7 | T-012 | 2 | 0 | 0 | 2 | Lost $724 (z = −4.3), worst session. |
| 8 | T-020 | 2 | 0 | 0 | 2 | Lost $2,398 (z = −4.2), 3.2% of the account; 10 orders vs. their usual 6. Same position size as always. |
| 9 | T-010 | 2 | 0 | 0 | 2 | Lost $664 (z = −3.4), 2.7% of the account. |
| 10 | T-008 | 1 | 0 | 0 | 1 | Lost $459 (z = −2.8), 2.2× their previous worst day. |

T-006 and T-007 have the two largest dollar losses today (−$3,214, −$3,067) and are **not** on the list: their P&L normally swings about ±$2,000, so today is an ordinary day for them.

**Robustness:** moving the thresholds stricter or looser (loss cuts at −2.5/−3.5/−5.5 or −1.5/−2.5/−4.5; risk cuts at 1.5x/3x or 1.1x/1.5x) keeps the same ten traders in every variant, and T-023, T-022 and T-009 always in the top three.

### Outside the ranking, but worth a look

- **T-013** exceeded their contract limit in 7 of 12 sessions (180% today). That is a control failure, not a bad day. They trade MNQ (micro); if the firm counts 10 micros as 1 contract, it may not be a breach at all.
- **T-024** lost $1,580 on their first day of trading. No history to compare against.
- **T-025** first day; the account shows a balance of $0 (data to verify).
- **T-026** only one previous session.

### Data notes (things I checked before trusting the numbers)

- **Point values range from $2 (MNQ) to $125,000 (6E).** All sizes and P&L are computed per instrument before aggregating.
- **`commission_usd` is the total for the fill**, not per contract (commission / quantity is constant per instrument).
- **5,146 fills but 4,886 orders**: activity is counted in distinct `order_id`s.
- **Today's session is compressed into the morning.** No historical session has a single fill between 1:00 and 4:59 a.m. Chicago; today ~40% of fills fall there, nothing happens after 9:20, and there are already more fills (497) than an average full day (423). It looks like a full day squeezed before the cut, probably an artefact of how the data was generated. I compare against full days and do not use time of day as a signal.
- **Eight positions are open at the cut**, all in today's session; they are marked to `market_prices.csv`.
- **Special accounts:** one demo (T-043), one closed (T-040), one restricted with zero buying power but still trading today (T-041), one with a $0 balance (T-025).
- **`max_position_size` is ambiguous** for micros (counted here as 1 contract each). "Max contracts" is the per-instrument peak, not the simultaneous sum across instruments.

## Task 2 — Labels and evaluation

### (a) Labels

**Definition.**

 The label should be an **outcome the firm actually pays for**: *a session is bad if, in the next 3 sessions, the account breaches a rule* — daily loss limit, trailing drawdown floor or max position size. This is defensible because it is tied to money and to rules the client already enforces, and it does not depend on my opinion of what "unusual" means. Three sessions is long enough to catch a blow-up that starts today and lands tomorrow, short enough not to blame today for unrelated losses next week. This dataset only contains one real rule (`max_position_size`), so for the backtest below I used a proxy for the loss rule: *lost more than 2% of the account in a session*.

**Where it is ambiguous.** (1) A session where the trader took extreme risk but made money (T-022 today): bad behaviour, good outcome. I would keep a second, separate label for "rule breached" so these cases are not called "good". (2) Open positions at the cut: the outcome depends on a mark price, not a closed trade. (3) Traders with several accounts: is the unit the account (where the rule lives) or the trader? I'd label the account. (4) Choice of N: too short misses slow blow-ups, too long blames today for next week's unrelated losses. (5) New traders, who breach often and have no baseline.

**Checking agreement.** Write a one-page labelling guide with worked edge cases, have two risk analysts label the same sample independently (stratified so borderline sessions are over-represented, not just obvious blow-ups), and measure Cohen's kappa. Below ~0.6, the disagreements tell me which rule in the guide is unclear; fix it and repeat. Where the label is mechanical (a breach either happened or not), agreement should be near-perfect, and the interesting disagreements are on the behaviour label.

**First model.** Target: the account breaches a rule in the next 3 sessions. Unit: account × session, scored at a fixed time inside the session (so it matches how it would run live). Features, all computed only from data available at scoring time: the trader's rolling baseline from *previous* sessions (P&L mean/std, median and max leverage, usual instruments, orders per session), today-so-far deviations from that baseline (P&L z-score, leverage vs. own max, new or larger contract, limit usage, open loss), and account context (type, balance, limit, distance to drawdown floor). Model: logistic regression first (each coefficient can be explained to the risk desk), gradient-boosted trees only if they clearly beat it.

**Validation: walk-forward by time** — train on sessions up to day *t*, test on the following days, roll forward — never a random split, which would let the model see a trader's future to predict their past. I would also hold out a set of traders entirely, to check it works on people it has never seen (new accounts are where the firm loses most).

### (b) Evaluation

**What I'd measure.** **Recall@10**: of all the accounts that went on to breach a rule in the next 3 sessions, how many were on that day's list of ten? The reviewer can only look at ten names, so the question that matters is how many of the people heading for trouble we put in front of them. A recall number means nothing on its own, so I always compare against random selection (10 / eligible traders) and two simple rankings: biggest dollar loss today, and biggest loss as % of account. If my ranking doesn't beat "biggest loser first", the extra complexity isn't earning its keep.

**What happened when I tried it.** I rebuilt the ranking for each past session using only data up to that day, and checked who breached in the following 3 sessions. Only 4 sessions qualify (5 days of history before, 3 after). Average recall@10: **15% for my score, 19% for both simple rankings, ~27% for random**, and the picture holds with a 1.5% or 3% loss threshold. I would not read "worse than random" into 4 days and ~27 positives, but I would not claim the ranking works either. Looking at the misses was more useful than the number: most are T-013 (a recurrent limit breach I excluded on purpose) and traders like T-001, T-004 and T-006 who lose more than 2% of the account routinely. For them that is *normal*, so a ranking built on "unusual for this trader" ignores them, but an absolute loss rule catches them anyway. That is the real finding: "unusual for this trader" and "about to breach a rule" are different questions. A ranking the firm can act on probably needs both — deviation from the trader's own baseline *and* distance to the account's actual limits.

**What this dataset doesn't give me.** Outcomes (which accounts were actually breached or liquidated, and when); each account's real rule parameters (daily loss limit, drawdown floor, and whether micros count as 1/10 of a contract); enough history (12 sessions per trader is too few for a stable baseline or any seasonality); reviewer decisions; and real rather than synthetic data.

**One way this could look better than reality.** Circular labels: if "bad session" is defined as "lost more than 3× the trader's usual move", and my score is built on that same z-score, recall@10 will look close to perfect while proving nothing — the score is being graded against itself. The label must come from an independent, later outcome (a breach). A second trap specific to this data: today's session is cut at 9:30 Chicago time but already contains a full day of activity (40% of fills happen in overnight hours that are empty in every other session). Evaluating a "9:30 snapshot" on data like this would credit the model with information it would not have at 9:30 in production. And once the list is in use, it changes the outcome: traders the desk calls get de-risked and don't breach, so good flags start to look like false positives. Any evaluation after launch has to account for interventions.

## Task 3 — Explain it to the risk desk

Two slides: [`slides_risk_desk.pdf`](slides_risk_desk.pdf).

1. **How the list is built.** Each trader is compared with their own last two weeks, not with each other. Three questions (unusual loss, bigger position than ever, first rule break), each with a real example from today, and why the biggest dollar loser is not automatically on the list.
2. **Tomorrow's ten, and how far to trust them.** The ranked list in plain words, what the desk can rely on (stable under different cut-offs, P&L checked two ways) and what to be careful with (9:30 snapshot, two weeks of history, real loss limits unknown, not yet proven to predict blow-ups).

## Task 4 — Code review

**Verdict: request changes — does not ship.**

The structure is fine, but four things would produce a wrong model or a crash.

**Blocking**

- **`avg_session_pnl` includes today's session** The "how does this trader usually do" feature contains the very outcome we are trying to predict: a big loss today drags the average down, and `label_bad` is a big loss today.

- **`POINT_VALUE = 20` is hard-coded.** 8 instruments. Look up `point_value_usd` per instrument and compute notional per fill (or per instrument) before summing.

- **`label_bad = net_pnl < -1000` is the same for everyone.** $1,000 does not mean the same thing for every trader: it is a normal day for someone trading 10 NQ and a disaster for someone trading 1 MNQ.

- **`pace` divides by `minutes_active`, which can be 0**

**Comments **

- `fills` counts executions, not orders; one order can fill in several pieces, so `pace` overstates activity. Count distinct `order_id`s.
- High complexity from scratch average each iteration is O(n²); irrelevant at 12 sessions, worth a running sum later.

