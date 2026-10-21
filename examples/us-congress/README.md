# U.S. Congressional Record — March 2026, three rounds

Floor speeches from both chambers, 1–31 March 2026 (21 session days, 2,697 speaking turns). The Congressional Record is a U.S. Government work and is in the public domain. Every turn carries the speaker's name, party, state and chamber, so the report runs with `--text-policy public`: representative statements and speaker names are shown.

The point of this example is the **rounds**. A map run with no rules shows what is actually in the data, including a lot of procedure. People then decide what is *not* public discourse, write that down as a rule file, and run again. Each report records the whole chain.

## Reproduce

```bash
python fetch_congressional_record.py 2026-03-01 2026-03-31 crec.csv

COMMON="--text text --group party --speaker speaker --context date,chamber,title \
  --text-policy public --per-group 0 --embed-chars 1000 --min-group-size 20 \
  --group-order Democrat,Republican --cache _cache --out run"

who-was-heard report crec.csv $COMMON --preset none --name r1
who-was-heard report crec.csv $COMMON --preset rules/us-congress-r2.json --previous run/r1_public.json --name r2
who-was-heard report crec.csv $COMMON --preset rules/us-congress-r3.json --previous run/r2_public.json --name r3
who-was-heard label --run run/r3 --reviews rules/reviewer-demo-r3.json
```

The first run downloads the embedding model and embeds every turn (CPU, roughly 10–20 minutes). Later rounds reuse `_cache/`.

## What each round did

| Round | Rules | Topics (5 random starts) | Unclustered | ARI mean | Removed by rules — Dem / Rep |
|---|---|---|---|---|---|
| 1 | none | 30–33 | 17.8–21.5% | 0.767 | 0 / 0 |
| 2 | `us-congress-r2` — 22 patterns | 17–21 | 15.0–22.5% | 0.747 | 175 / 402 |
| 3 | `us-congress-r3` — 29 patterns | 17–19 | 19.5–21.9% | 0.797 | 181 / 483 |

- **Round 1 → 2.** Of 33 topics, 17 were procedure: yielding time, unanimous-consent requests, cloture filings, quorum calls, roll calls, bill text read into the Record. `rules-draft` proposed 38 phrases from those clusters; a person kept 18, added 4, and capped them at 600 characters so a phrase inside a long speech does not delete the speech.
- **Round 2 → 3.** Five clusters were still procedure: committee meeting authorizations, cloture motions, suspension motions with the full bill text, statutory text, a roll call. The draft offered 9 new phrases. A person kept 3, dropped 6 (e.g. *section 1* and *as follows* also hit ordinary speeches; senator-name lists were fragile), and added 4 the draft missed. Every edit and its reason is in `rules/us-congress-r3.json` under `human_edits`.
- **Round 3.** 19 topics. The largest are the Homeland Security funding standoff, tributes, the war with Iran, and the SAVE America Act. Five clusters are still procedure (shown as *(procedure)* in the labels). This demo stops here; a round 4 would start from those five.

There is no "finished" round. Each one is a judgment, and the report shows it.

## Who the rules remove

After round 3, rules removed **16.3% of Democratic turns and 30.6% of Republican turns**. That is not a judgment about either party's speeches. In March 2026, Republicans held the majority in both chambers, and the majority runs the floor: its members move to suspend the rules, manage time on bills, file cloture and make the scheduling requests, so more of its turns are procedure. The report's *Who dropped out* section shows this split on every round. Whoever uses the map should see it before reading the topics.

## Reviewers

`rules/reviewer-demo.json` (round 1) and `rules/reviewer-demo-r3.json` (round 3) were written by one person while building the tool. They are **not independent second coders**, so no κ is reported for this example. With two or more reviewer files, `rules-draft --reviews A.json,B.json` and `label --reviews …` report Fleiss' κ and mark split decisions as "A / B".

## Files

| | |
|---|---|
| `fetch_congressional_record.py` | downloads the daily govinfo packages and splits them into speaking turns (stdlib only) |
| `rules/` | rule files for rounds 2 and 3, the round-3 draft as the tool wrote it, reviewer files |
| `report/r1_public.html` … `r3_public.html` | the public reports. Open them in a browser |

The internal reports are not included. They are just as public here (public-domain text), but the repository keeps the habit of never shipping `*_INTERNAL_do-not-share.*` files.
