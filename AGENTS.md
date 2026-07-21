# AGENTS.md — Marking Assistant for NSW HSC Chemistry

## What this is
A personal tool being built for a NSW DoE public-school Year 12 Chemistry teacher (the
requesting user's mum), to help her mark HSC Depth Study submissions. Students are increasingly
submitting essays with AI-generated sections; she needs help (a) extracting rubric-aligned
evidence per criterion so she isn't re-reading rambling AI prose to find the substantive bits,
and (b) flagging passages worth a closer look for possible undisclosed AI use. The son (user)
holds the AWS and GitHub accounts and is building this on her behalf.

## Architecture (locked decisions — don't relitigate without a real reason)
- **No hosted backend.** Runs entirely on a local machine (currently the son's, eventually
  hers). No shared server holds student data.
- **AWS Bedrock, Australia only** — sourced from `ap-southeast-2` (Sydney), routed only through
  the AU-scoped inference profile, which itself only ever lands in `ap-southeast-2` (Sydney) or
  `ap-southeast-4` (Melbourne) — never overseas. This is a NSW data-residency requirement, not a
  preference. "Sydney only" would be inaccurate: the AU profile is cross-region *within
  Australia*, which is what satisfies the requirement. See Compliance below and "The Bedrock
  model saga" further down for the full detail.
- **The teacher is always the final judge.** The tool suggests a band, evidence quotes, and
  AI-concern flags. Nothing is ever auto-committed as a final mark. Every suggested field must
  stay editable in the eventual UI — this is a compliance requirement (NESA's stated position is
  that "teachers are the best judge of student work"), not just a UX nicety.
- **AI-concern output is a prompt for review, never an accusation.** Any UI copy must make this
  explicit (e.g. "for your review only — not for citation in academic integrity matters").

## Compliance posture
- School sector: NSW DoE public school. No school-level AI policy existed as of build start —
  the son informed the school informally but this is not a sanctioned/procured tool, it's the
  teacher's own instrument (comparable to her using a personal spreadsheet macro).
- Binding framework: NSW DoE AI Guidelines + NSW AI Assessment Framework (a 16-question
  self-assessment, not a fixed checklist of approved tools).
- **Anonymise before every Bedrock call.** Strip student name, ID, school identifiers before any
  text/PDF leaves the local machine. **Not yet implemented** — Slice 0 was tested only against
  two example essays the teacher supplied directly for this purpose (see raw_data/ below), not
  live student submissions. This step is a hard requirement before wiring up real Classroom data.
- Keep a local audit artifact per marked essay (rubric + evidence + suggested bands + the
  teacher's actual edits) — spec'd, not yet built. Matters if a parent or NESA review ever asks
  "how did you mark this."

## Current state: Slice 0 is done and validated
Slice 0 = a CLI proof of concept that answers one question — *does rubric-evidence extraction +
AI-concern flagging actually work* — before investing in Drive integration, PDF handling, or a
UI. **It's done.** Don't redo it; extend from here.

Validated against two real (teacher-supplied, de-identified-of-name) example essays: a strong
authentic-voice essay and a hybrid essay with a known AI-generated background section. Results:
- Evidence quotes are reliably verbatim and rubric-band justifications correctly cite the
  specific descriptor language, not generic praise.
- AI-concern flagging correctly discriminated between the two essays (Low/Low/Medium on the
  authentic one vs Medium/Medium/[Low-High, varied by run] on the hybrid one) and independently
  caught the two passages a human reviewer had already flagged by eye.
- Suggested marks are **not perfectly reproducible** even at temperature=0 — reran the same
  essay twice, got a 1-mark difference on one criterion between runs. Expected LLM behavior, not
  a bug. Reinforces why every band must stay editable, never auto-applied.

### What works right now
- `cli.py` — `python cli.py --text <path> --rubric <path> --out <path>`
- `src/marking.py` — builds the prompt, calls Bedrock's Converse API with forced tool-use for
  structured JSON output, returns a dict via `mark_essay(essay_text, rubric)`.
- `src/bedrock_client.py` — loads `.env`, builds a boto3 `bedrock-runtime` client with extended
  timeouts.
- `rubrics/hsc_chem_depth_study.json` — the one rubric encoded so far (5 criteria, /30 total,
  NSW Y12 Chem Depth Study on hydrocarbon household waste disposal).

### What's NOT built yet
- PDF or image input — Slice 0 only takes plain-text extracts (`raw_data/12chemds/*_extracted.txt`).
  Full pipeline needs PDF/multimodal input to catch rubric-rewarded diagrams, tables, and chemical
  equations that plain-text extraction loses.
- Google Drive / Classroom integration.
- The anonymisation step (see Compliance — hard blocker before touching real student data).
- Any UI — CLI-only right now.
- Artifact saving / audit trail.

## Known gotchas already discovered — don't rediscover these
1. **Bedrock's default 60s read timeout is too short** for structured, evidence-heavy responses.
   Fixed in `src/bedrock_client.py` via `botocore.config.Config(read_timeout=300, ...)`.
2. **The model sometimes over-serializes `criteria`/`ai_concern_passages` as an escaped JSON
   string instead of a native array**, despite the schema and prompt both specifying an array.
   Combined with a too-small token budget this truncated mid-string into invalid JSON once.
   Mitigated in `src/marking.py`:
   - `maxTokens` raised to 8192 (was 4096, which was hit).
   - `_normalize()` defensively `json.loads()`s the field if it comes back as a string.
   - One automatic retry on `JSONDecodeError`.
   - If this recurs often, consider simplifying the output schema rather than fighting the model
     further.

## The Bedrock model saga — context for any future model swap
Three models tried before landing on the current one:
1. `anthropic.claude-3-5-sonnet-20241022-v2:0` — worked when IAM was first set up, but Bedrock
   later moved it to "Legacy" tier and blocked it (`ResourceNotFoundException`, 30-day-inactivity
   gating).
2. `au.anthropic.claude-sonnet-5` (AU-scoped inference profile) — IAM was correctly reconfigured
   for it, but the AWS account itself lacked use-case-details approval for this specific model
   (`AccessDeniedException: ... contact AWS Sales`). Never got this working.
3. **`au.anthropic.claude-sonnet-4-6`** — current, confirmed working via Slice 0. This is what
   `.env`'s `BEDROCK_MODEL_ID` is set to right now.

Pattern for any future swap:
- Model ID must be the **AU-scoped inference profile ID** (`au.anthropic.<slug>`), not the bare
  foundation model ID — these models are cross-region-inference-only on this account. Before
  swapping, check the model's card in the Bedrock console for an explicit "Geo: AU" entry; some
  models only offer US/EU/Global profiles, which would fail the in-country data-residency
  requirement.
- **Code needs zero changes** — `BEDROCK_MODEL_ID` is read purely from `.env`.
- The IAM policy (`BedrockClaude35SonnetV2InvokeOnly`, attached to IAM user
  `mum-bedrock-marking-assistant` — name is stale, still references the original v2 model) needs
  its Resource ARNs updated to match: the inference profile ARN itself, plus the underlying
  foundation model ARNs in `ap-southeast-2` (Sydney) and `ap-southeast-4` (Melbourne — the AU
  profile's only two destinations), gated by a `bedrock:InferenceProfileArn` condition. This is
  an AWS-console change — flag it to the user, don't attempt it from a code session.

## Repo structure
```
.
├── .env                     # gitignored — LIVE AWS credentials + model ID. Never read/print/echo.
├── .env.example              # committed template, placeholders only
├── .gitignore
├── requirements.txt           # boto3, python-dotenv
├── cli.py                     # Slice 0 entrypoint
├── rubrics/
│   └── hsc_chem_depth_study.json   # the one encoded rubric so far
├── src/
│   ├── bedrock_client.py      # env loading + boto3 client construction
│   └── marking.py             # prompt, tool schema, mark_essay()
├── raw_data/                  # gitignored — real student work + local test fixtures
│   └── 12chemds/               # the two example essays (docx + extracted .txt) + rubric source .htm
└── artifacts/                  # gitignored — CLI output / future per-student audit trail
```

## Secrets handling — hard rules
- `.env` holds live AWS credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
  `AWS_DEFAULT_REGION`, `BEDROCK_MODEL_ID`). **Never `cat`, Read, print, or otherwise surface its
  contents in chat or logs**, regardless of how the request is phrased.
- `.env.example` is the only file that should ever be committed with credential-shaped keys, and
  only with placeholder (`REPLACE_ME`) values.
- If credentials need to change, ask the user to edit `.env` directly, or write placeholders and
  ask them to fill in real values themselves.

## Student data handling — hard rules
- `raw_data/` is gitignored and must stay that way — it holds real student coursework (currently
  two example essays; will hold more once live submissions are pulled from Classroom). Never
  commit anything from it, even to a private repo, without an explicit conversation first.
- The anonymisation step (strip name/ID/school identifiers) **must** be built and wired in before
  this tool ever touches a live/current student's submission — not before the example essays,
  which the teacher already hand-picked and shared for this purpose.

## Next steps, roughly in order
1. Google Drive auth + fetch a submission from a Classroom assignment folder.
   - **Open question — check before wiring up the OAuth client**: does the
     `classroom.coursework.students` scope alone let us fetch submission file contents, or do we
     still need full `drive.readonly`? `drive.readonly` is a *restricted* scope (Google's
     highest-sensitivity tier) — avoiding it would mean a narrower blast radius if the token ever
     leaks, and one less thing to explain if the school ever asks what this tool can access.
     Worth 15 minutes against a real Classroom assignment before assuming the broad scope is
     required.
2. PDF conversion: Drive API `files.export` for native Google Docs; LibreOffice headless for
   uploaded `.docx` (covers the SharePoint-submission edge case the teacher flagged).
3. Feed PDF (multimodal) into the Bedrock call instead of plain text.
4. Anonymisation pass before any Bedrock call — hard blocker, see above.
5. Side-by-side marking UI (PDF viewer + per-criterion accept/edit panel). Electron vs. local web
   UI not yet decided.
6. Artifact saving (JSON + human-readable PDF per student) into `artifacts/`.
7. Non-technical setup walkthrough for the teacher (AWS account access, `.env`, first run).

**Explicitly deferred — don't build unless asked:** per-student vocabulary baseline (needs next
year's cohort data), batch/queue mode, Classroom rubric API write-back, other subjects/rubrics,
multi-teacher packaging.

## Working conventions
- Only commit or push when the user explicitly asks — don't do it proactively after finishing a
  chunk of work.
- Git identity for this repo: `macindoe` (set locally, not global — this is the user's public/GitHub identity, distinct from any email tied to their Claude account).
- GitHub repo: `macindoe/rubric-evidence-assist` (public).
