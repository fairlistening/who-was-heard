# Fair Listening — who-was-heard

> **The problem isn't new media — it's that we haven't learned to listen in it.**
> Tools for bringing public discourse together in the YouTube era — without losing the voices that get drowned out.

## Why

YouTube and other new media have changed who gets heard. A handful of channels and a handful of loud participants can fill a public conversation, and there is real concern about what that does to democracy. But the problem is not the medium itself. The environment changed; our ways of gathering public discourse did not.

"Broad listening" tools — Polis (2012), Talk to the City (2023), kouchou-ai (2025) — showed that AI can help read thousands of voices at once. This project asks the next question: **when you gather voices this way, how evenly did you listen?** *Broad* listening hears many; *fair* listening (고루듣기, *goru-deutgi*) also checks whose voices were dropped, drowned out, or reshaped by the machine.

This toolkit grew out of the Korean interactive series *YouTube Tribalism* (Hankook Ilbo, 2026), which measured 14 million live-chat messages on Korean political YouTube channels. The series is linked below; this repository contains the method and code, written independently, not the articles.

## What it does

Give it a table of texts (comments, speeches, petitions) with a group column (party, channel, region…). It writes **two reports**:

> **Works without any AI app.** The whole analysis runs in the browser screen, with no generative AI (LLM), no outside AI service and no API key. One open embedding model turns texts into numbers on this computer. Connecting an AI app such as Claude over MCP is an **option** for working by chat.

**Part 1 — What was discussed.** A map of the discourse: topics, their size, which groups raised them, representative statements and speakers (only for public officials' on-record statements), and a stability badge on every topic.

**Part 2 — How far to trust this map.**

> It tells you how far to trust an AI opinion map — not what it means.

- **Stability** — the same data clustered from several random starts; how often each topic reappears.
- **Who dropped out** — how much each group lost to cleaning rules and to "unclustered".
- **Concentration** — whether a few speakers fill the room.
- **Scale** — equal-sample view vs. original proportions.
- **Rounds & rules** — what people removed after seeing earlier rounds, and how much reviewers agreed (κ).
- **Choices** — every setting that produced the result, including the rule file's fingerprint.

By default the **public report** contains no raw texts (they are included only when the analyst chooses, e.g. for public officials' on-record statements or open deliberations). The **internal report** (`*_INTERNAL_do-not-share.html`) holds samples so that a person can read and name the topics on their own machine.

## The easiest way — the analysis screen

**No Python needed:** download the Windows or macOS build from [Releases](https://github.com/fairlistening/who-was-heard/releases), unzip, and run `who-was-heard.exe` (or `who-was-heard.app`). The app is unsigned, so the first launch shows a warning — on Windows click "More info → Run anyway"; on macOS right-click → Open.

Run the installer build — or, with Python, double-click `start.pyw` (`start.command` on macOS) — and click **Analyze →** on the setup page. Six steps in the browser. **New here? Start with the [usage guide](docs/USAGE.en.md).**

1. **Data** — upload a CSV, TSV or XLSX, or type its path — or **fetch directly**: U.S. Congressional Record (govinfo), Korean National Assembly minutes (NANET datasets or Open API), YouTube comments and live chat (your own API key; author IDs hashed), Polis, or any URL (files as tables, pages as paragraphs). Only column names, fill counts and average lengths are shown first.
2. **Settings** — text, group and author columns; text policy (no texts / texts without authors / public officials with names); details such as sample size, values to drop and cluster selection.
3. **Rounds** — round 1 runs with no rules, showing texts embedded and time left; stop and resume any time. Computed embeddings are reused across projects.
4. **Review** — read each cluster's samples, mark "not discourse" and name topics. Save one review per reviewer; κ appears immediately.
5. **Rules** — draft rules from the agreed clusters, edit or add patterns in a table, save — then run round 2, 3 … in step 3.
6. **Results** — open the last round's public report (to share) and internal report (with texts).

Everything is kept in `Documents/who-was-heard/<project>` (copy of the data, reports per round, reviews, rule files). The screen shows raw texts, but nothing leaves the computer.

## Try it from the command line — U.S. Congressional Record

The Congressional Record is a U.S. Government work in the public domain, and every speech comes with the speaker's name, party, state and chamber.

```bash
python install.py                       # installs, runs the tests
cd examples/us-congress
python fetch_congressional_record.py 2026-03-01 2026-03-31 crec.csv
who-was-heard report crec.csv --text text --group party --speaker speaker \
    --context date,chamber,title --preset none --text-policy public \
    --per-group 0 --embed-chars 1000 --out run --name r1
```

Then read `run/r1_INTERNAL_do-not-share.html`, decide (ideally with a second reviewer) which topics are procedure rather than discourse, and run round 2:

```bash
who-was-heard rules-draft --run run/r1 --reviews reviewerA.json,reviewerB.json --out my-rules.json
# read and edit my-rules.json
who-was-heard report crec.csv ... --preset my-rules.json --previous run/r1_public.json --name r2
who-was-heard label --run run/r2 --reviews reviewerA.json,reviewerB.json
```

There is no limit on the number of rounds. Each report records the chain of earlier rounds. See `examples/us-congress/` for the March 2026 run in three rounds — 33 topics with no rules, 19 after two rounds of human-edited rules — and why the rules removed more of the majority party's turns.

### Other examples

| | Data | Text | What it shows |
|---|---|---|---|
| `examples/polis/` | Polis citizen deliberation, Bowling Green KY (CC BY 4.0) | private | moderators rejected one opinion group's comments 1.5× more often; one setting turns 2 topics into 20 |
| `examples/youtube/` | YouTube comments — **fetch script only**, no data | private | run with your own key, keep the data locally; author IDs hashed on arrival |
| `examples/korean-assembly/` | Korean National Assembly minutes (NANET datasets) | public | conversion and speaker-name inference scripts; "Fetch directly → NANET" in the analysis screen does the same |

## How it groups topics

Open multilingual sentence embeddings (default `paraphrase-multilingual-mpnet-base-v2`, no API key) → UMAP to 5 dimensions → HDBSCAN. The 2-D map is for drawing only. No cap on the number of topics; unclustered texts stay visible. Everything is printed in the report's *Choices* section.

## Three layers

| | |
|---|---|
| `whowasheard/` | Python library — all calculations |
| `who-was-heard` | command line (installed with the library) |
| `servers/` | MCP servers for Claude and other MCP clients: `listen-check` (this tool), `ledger` (fact & banned-phrase checker for drafts), `survey-template` (survey lookups with denominator rules built in) |

### Using it in conversation — MCP

**Double-click `start.pyw`** (`start.command` on macOS). The three servers start in the background, with no console window, on a local address (`http://127.0.0.1:8730/…`), and a setup page opens — in English or Korean depending on the computer's region, switchable — with a *Stop MCP servers* button, a one-click **Register** button per app (the original settings are backed up; other servers are left alone) and copy-ready settings for Claude Code, Cursor, VS Code, Windsurf, Gemini CLI, Codex CLI, LM Studio, LibreChat and other MCP clients. Claude Desktop uses stdio: `python install.py --mcp`. Details: [`servers/CONNECT.md`](servers/CONNECT.md).

- The address is reachable **only from this computer** — not from other devices on the network, not from the internet.
- The servers return **aggregates only**; texts stay in the local internal report, so instructions hidden in someone else's text never reach the conversation.
- With default settings, Talk to the City and kouchou-ai send every text to an external LLM that reads and rewrites it. Here, only a person reads the texts; the embedding model just turns them into vectors, locally.

## What is not here

No raw chat messages, author hashes, survey microdata or interview transcripts from the reporting; no articles or newspaper graphics (those belong to Hankook Ilbo); no data from third parties. The Korean demo (`examples/korean-assembly/`) uses public National Assembly minutes.

## Principles, method notes, license

- `docs/USAGE.en.md` · `docs/USAGE.md` — usage guide (English, Korean)
- `methods/principles.md` — principles ⓪–⑧, with the measurement behind each (Korean + English)
- `methods/kouchou-ai-source-notes.md` — what the public kouchou-ai code shows
- `methods/preregistration/template.md` — pre-registration template
- Code: Apache-2.0 (`LICENSE`). Docs: CC BY 4.0 (`LICENSE-docs`). © 2026 Donghyeon Lee.
- This is an archival release. **Bug reports only** via [Issues](https://github.com/fairlistening/who-was-heard/issues) — no feature requests, pull requests or comments on the articles. Never paste raw texts from your data, internal reports or API keys into a report.

## The series

*YouTube Tribalism* — Hankook Ilbo (2026)

- English edition: <https://www.hankookilbo.com/interactive/youtubeTribalism/pages/englishEdition.html>
- Korean interactive: <https://www.hankookilbo.com/interactive/youtubeTribalism/>
