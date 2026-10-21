# How to use who-was-heard (Fair Listening)

[한국어](USAGE.md) · [Back to README](../README.en.md)

A step-by-step guide for first-time users: install, first report, repeated rounds, connecting AI apps, and troubleshooting.

---

## 1. What you need

| | |
|---|---|
| OS | Windows 10/11, macOS, Linux |
| Python | 3.9 or later. On Windows, install from [python.org](https://www.python.org/downloads/) and **tick "Add python.exe to PATH"** |
| Disk | about 3 GB — 1–2 GB of packages, about 1.1 GB for the sentence-embedding model |
| Memory | 8 GB or more; 16 GB for data above 20,000 texts |
| Internet | Only the first time (packages and model) and when fetching data. The analysis itself runs on your computer |

No API key is required. You use your own key only to fetch from YouTube or the Korean National Assembly Open API.

## 2. Start

Download and unzip the repository (or `git clone` it), then:

| | |
|---|---|
| Windows | **double-click `start.pyw`** — runs in the background, no console window |
| macOS | **double-click `start.command`** — the first time, right-click → Open |
| Anywhere | `python start.py` — runs with a log window (for troubleshooting) |

- The **setup page** opens in your browser (`http://127.0.0.1:8730`)
- **The first run installs the needed packages in the background** (a few minutes). The log is `_logs/start.log`
- The page follows your computer's region (Korean or English); switch with the button at the top right
- To stop, click **"Stop MCP servers"** twice on the setup page
- The address opens only on this computer — not from other devices on the same Wi-Fi, not from the internet

Use another port with `python start.py --port 8740`.

## 3. The analysis screen, start to finish

Click **"Analyze →"** on the setup page to open **Who Was Heard Analysis** (`/studio`). Six steps, top to bottom.

> This screen shows raw texts. It opens only on this computer and nothing leaves it. Take care when sharing your screen.

### Project

No need to create one first: adding data in step 1 creates a project named after the file or source. Work is kept in **`Documents/who-was-heard/<project>`** (a copy of the data, reports per round, reviews, rule files). Set the `WWH_WORK` environment variable to use another folder. "Open work folder" opens it.

### Embedding model

An open model that turns texts into numbers (vectors). The default is [`paraphrase-multilingual-mpnet-base-v2`](https://huggingface.co/sentence-transformers/paraphrase-multilingual-mpnet-base-v2) (about 1.1 GB, Apache-2.0, 50+ languages). It downloads on the first run. In the "Embedding model" panel you can download it ahead of time, choose where it is stored (another drive, say), or delete it.

### ① Add data

**File** tab — upload a CSV, TSV or XLSX, or type its path. One row per text (speech, comment, opinion), with a text column and a group column (party, channel, committee …).

**Fetch directly** tab — the tool downloads the data.

| Source | You need | Notes |
|---|---|---|
| U.S. Congressional Record (govinfo) | a date range | No key, public domain. Speaker name, party, state and chamber. Up to 92 days at a time |
| Korean National Assembly — NANET datasets | the downloaded XLSX | Download minutes XLSX from the [National Assembly Library datasets](https://losi-open.nanet.go.kr/user/dataset/datasetList.do?category_cd=2) and upload them. Several files at once. Filter by dates, committee and meeting type. The speaker field is split into name, title and side (member / Assembly staff / government, agencies, witnesses) |
| Korean National Assembly — Open API | your own key and the API code | Some minutes APIs return only meeting lists, not the text |
| Polis open data | a conversation name | CC BY 4.0. Each author's opinion group and the moderation outcome are attached |
| YouTube comments | your own YouTube Data API key, video URLs | Author IDs are hashed on arrival. Do not redistribute the comments |
| YouTube live chat | your key, a video that is live now | The official API cannot fetch chat from ended streams. Mind the daily quota |
| URL | URLs | CSV, TSV, XLSX and JSON become tables; web pages are split into paragraphs |

- A NANET XLSX uploaded in the **File** tab is recognised and converted the NANET way automatically
- The tool never writes keys to disk. "Remember in this browser" keeps the key in this browser only
- Large files take over a minute to read. A progress panel shows, and step 2 opens when it finishes

After loading, only column names, fill counts and average lengths are shown.

### ② Settings

| Setting | Meaning |
|---|---|
| Text column * | The column holding the speeches or comments. A warning appears if its average length is too short (choosing an ID or name column clusters numbers) |
| Group column * | The groups to compare (party, channel, committee …). The report measures who dropped out, per group |
| Author / speaker column | If given, "Concentration" measures whether a few people fill the room |
| Columns shown next to quotes | Context such as date or committee |
| Put texts in the public report? | **No** (default) / **Texts only** (no authors — open deliberations, petitions, public comments; check terms, copyright and privacy yourself) / **Yes** (public officials' on-record statements — quotes with names) |

**More — detailed settings**

| Setting | Default | Meaning |
|---|---|---|
| Max texts per group | 0 (all) | A random sample per group. 1,000–2,000 for large data. The report says it is a sample |
| Drop texts shorter than (chars) | 5 | 0 keeps everything |
| Characters used for embedding | 400 | Fewer is faster (around 240 is about twice as fast) |
| Drop by column value | — | e.g. drop "government, agencies, witnesses" in the `side` column of Assembly data to keep members only |
| Merge groups smaller than this into Other | 0 | |
| Cluster selection / Minimum cluster size | eom / auto | Broad topics (eom) or fine ones (leaf; for small data) |

A warning appears above 20,000 texts: on a laptop that can take hours and run out of memory.

### ③ Rounds — run

**Round 1 clusters everything with no rules.** The progress panel shows the stage (cleaning → embeddings → clustering → summary), the number of texts embedded and the time left.

- **Time** — embeddings take most of it. An office laptop does about 10 texts a second; 80,000 texts take over two hours
- **Stop** — click twice. Embeddings computed so far are saved, so running again continues from there
- **Reuse** — computed embeddings are shared by all projects (`<work folder>/_cache/embeddings`, hashes and numbers only, no raw text). The same text is never computed twice
- The job keeps running if you close the window

When it finishes, the round card shows **Results: Public report (to share) · Internal report (with texts)** and **Next: Review this round**.

### ④ Review

For each cluster, read the representative statements and the random sample ("Read more texts" shows more from that cluster), then

- mark clusters that are not discourse (procedure, greetings, ads …) **"Not discourse — exclude"**
- write a **topic name**

Enter your reviewer name and **"Save my review"**. With two or more reviewers, agreement (κ) appears immediately. **"Put agreed names into the report"** adds the topic names to that round's reports.

### ⑤ Rules

**"Make a rules draft"** finds phrases common in the agreed Exclude clusters and rare elsewhere, and writes draft patterns (regular expressions). Read, edit and add to them, then **"Save as r2.json → use in round 2"** and run round 2 in step 3. Rounds 3, 4 … — no limit. Each report records the chain of earlier rounds.

### ⑥ Results

**Rounds 2 and 3 are optional. Whenever you stop, the last round's reports are the result.**

| File | What | Share? |
|---|---|---|
| `rounds/rN_public.html` · `.json` | **Public report** — the map of the discourse, topics, who dropped out per group, stability, concentration, every setting. Texts only as far as the policy in step 2 allows | Yes |
| `rounds/rN_INTERNAL_do-not-share.html` · `.json` | **Internal report** — sample texts and authors | **No** |

On the report's map, switch colours between topics, stability and a highlighted group. With many groups, click the group button to pick from (or search) the full list.

## 4. Connect AI apps (optional) — MCP

On the setup page, open your app's tab (Claude Code · Cursor · VS Code · Windsurf · Gemini CLI · Codex CLI · LM Studio · LibreChat · Claude Desktop) and click **"Register"**. The three servers are added to that app's config; the original config is backed up and other servers are left alone. The config to paste by hand is shown too. For LibreChat, paste it into `librechat.yaml`.

| Server | Does |
|---|---|
| `listen-check` | this tool — run diagnostics and read results from a chat |
| `ledger` | checks a draft's figures and banned phrasings |
| `survey-template` | a survey lookup template with the denominator rules built in |

The servers return **aggregates only** to the chat. Raw texts stay in the internal report on your computer. Details in [`servers/CONNECT.md`](../servers/CONNECT.md).

## 5. Command line

```bash
python install.py                    # install + tests
who-was-heard columns data.csv        # column names only
who-was-heard report data.csv --text text --group channel --speaker author \
    --preset none --out out --name r1 --cache out/cache
who-was-heard rules-draft --reviews A.json,B.json ...   # κ and a draft rule file
who-was-heard report data.csv ... --preset rules.json --previous out/r1_public.json --name r2
who-was-heard label --reviews A.json,B.json ...          # put agreed topic names in
```

See `who-was-heard <command> --help`. A full U.S. Congress walk-through is in [`examples/us-congress/`](../examples/us-congress/).

## 6. Troubleshooting

| Symptom | Do |
|---|---|
| Double-clicking does nothing | Start with `python start.py` and read the window, or open `_logs/start.log`. Check that Python is on PATH |
| `/studio` says "not found" | An older server is still running. Stop the MCP servers and start again |
| No change after an update | If only an `.html` file changed, press F5. If a Python file changed, stop and restart the server |
| "Nothing left after cleaning" | Check the text column, and that "Drop texts shorter than" isn't too high |
| Topics are clustered by numbers | An ID or number column was chosen as the text column. See the warning in step 2 |
| Embeddings take too long | Stop, lower "Max texts per group" or "Characters used for embedding", run again. Saved embeddings are reused |
| Out of memory, job dies | Use a smaller sample (20,000 texts or fewer) |
| YouTube live chat fetches nothing | The video must be live now, and your key's daily quota must not be used up |

## 7. Removing

- Model: "Delete model" (click twice) in the Embedding model panel
- Work: delete the `Documents/who-was-heard` folder
- App registrations: "Unregister" on the setup page. The config backup stays in that app's config folder
- The tool: delete the repository folder; packages with `pip uninstall who-was-heard sentence-transformers umap-learn hdbscan`
