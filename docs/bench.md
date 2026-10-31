# Bench

The bench measures whether a model follows a plugin's rule: it runs omp headless on task prompts,
many times, in throwaway sandboxes, for one or more versions of the plugin's files, then scores
each run with checks that give the same answer every time: what the agent's journal shows, and
probes that run the program it built. No model judges anything.

It is manual, never part of `bun run check` or CI: it uses your omp sign-in and subscription,
takes minutes, and a model's answers vary from run to run.

## Running

    just bench <suite> [--variants a,b] [--tasks a,b] [--repeats n] [--concurrency n] [--out dir] [--no-score]
    just bench-score [--baseline <results.json>] [--only <id,...>] [--jobs n] -- <out>

`just bench` (`bun tools/bench/run.ts`, `-h` for its usage) runs every chosen variant × task ×
repeat, `concurrency` at a time, into `<out>` (new or empty; a new temporary folder unless
given), then scores them. Bad usage or an invalid suite stops it before any sandbox starts. `just
bench-score` (`tools/bench/score.py`) scores a folder again, after a check changed or against a
baseline; `--only` scores the runs named and keeps the others' results. Both run in the dev
shell; the runs need omp signed in on this Mac, which each sandbox borrows through omp's auth
broker as the demos on this Mac do ([Demos](demos.md)). Stopping `just bench` midway leaves its
sandboxes in `/tmp/omp-demo-*`.

## Suites

A suite is a folder in `tools/bench/suites/`: `suite.json` (its schema is
`tools/bench/suite.schema.json`) and `checks.py`.

| Field | What it holds |
| --- | --- |
| `plugin` | the plugin under test |
| `project` | the made-up project each run starts from: a module exporting its files, as `demos/shop-api.ts` does |
| `agent`, `model`, `thinking` | `omp`, and the model and thinking level of `omp -p` |
| `repeats`, `concurrency`, `timeoutMinutes` | defaults the flags override |
| `guide` | the plugin's file whose reading the read checks look for |
| `variants` | name → files of the plugin replaced by files in the suite folder; `{}` is the plugin as checked out |
| `tasks` | id → the prompt and the checks that score it |

`checks.py` exports `CHECKS`, each name a function of the run that returns pass, fail or
unmeasured with what it saw. The generic parts (journal, CLI contract, JSON-RPC and MCP clients,
sample inputs from a JSON Schema, the report) are in `tools/bench/analysis/`.

## What a run leaves

    <out>/suite.json            the suite as run
    <out>/runs/<variant>.<task>.<n>/
        meta.json               exit code, seconds, timed out, error
        prompt.txt final.txt stderr.txt
        journal.jsonl           the agent's omp session journals
        diff.patch git-log.txt  what it changed and committed
        project/                the project afterwards, to run and read
    <out>/results.json          every check of every run
    <out>/report.md             a table per task, then each check not passing

## Reading the report

- A cell is passes over passes and fails; unmeasured runs are counted apart. A check is
  unmeasured when it can't run, such as a program with no tool list to probe.
- Check each line under "Not passing" against the run's `project/` before trusting it: probes
  guess a program's commands and inputs, and those guesses have been wrong before.
- Three repeats show only large drops (3/3 to 1/3); a smaller one needs about ten per cell.
- For a regression check, score a new run against a known-good `results.json` with
  `--baseline`: each cell then shows the earlier result beside it.

## Limits

- omp only. Claude Code and Codex run in the demos' sandboxes (`tools/demo/harness.ts`); the
  runner doesn't start them yet.
- Probes run programs an agent wrote, as you: each run gets its own HOME and XDG folders, removed
  after scoring, nothing more. The bench's own prompts don't ask for anything that signs in or
  stores a secret.
- A suite's checks may generate inputs into `<out>/cache/`: the interfaces suite's export of 4
  million carts takes about 440 MB.

## The interfaces suite

Measures piebird-workflow-rules' `interfaces` rule on the shop project, with Claude Sonnet 5.5:

| Task | Asks for | Checks |
| --- | --- | --- |
| `oneshot` | a command-line tool for cart totals and shipping | the rule read before the first edit; a real name, `-h` with an example, `--version`, `--help --json`, exit 2 on an unknown flag, a call through `--json --input -` |
| `session` | a tool staff use to build up a cart step by step | the same, plus `rpc` and `mcp` modes and a cart kept across calls |
| `slow` | re-pricing an export of millions of carts | the same, plus finishing 4 million carts within 5 minutes, MCP's progress and cancellation in both modes |
| `bugfix` | a bug fix | the rule not read: it doesn't apply |
