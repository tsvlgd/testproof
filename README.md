# TestProof

TestProof grades whether a test suite actually catches bugs. It runs mutation testing on the lines a pull request changed, reports the bugs the tests miss, and writes the missing tests itself. A deterministic engine keeps a test only when it passes on the original code and fails on the planted bug.

One line: passing tests are not the same as strong tests.

## How it works

```text
pull request diff
      |
      v
diff resolver  ->  Python adapter  ->  sandbox  ->  project test command
                                                        |
                                                        v
                                          killed, survived, invalid, timeout
                                                        |
                                                        v
                                               score and report
                                                        |
                                                        v
                                 deterministic probe and test templates
                                                        |
                                                        v
                                         open model fallback when needed
                                                        |
                                                        v
                                  verifier: pass on original, fail on mutant
                                                        |
                                                        v
                                            keep the test or reject it
```

The mutation engine is deterministic. No model call happens in discovery, execution, classification, or scoring. Repair builds candidate inputs from the mutation and proves them by running the original and the mutant in an isolated interpreter. The model is a fallback for survivors that templates cannot handle. The verifier decides what is kept.

## Install

Install the CLI as a local tool. No PyPI package is published yet, so install from the git repository:

```bash
# One off use with uvx
uvx --from git+https://github.com/tsvlgd/testproof testproof --version

# Persistent install with uv (recommended)
uv tool install git+https://github.com/tsvlgd/testproof
testproof --version

# Or with pipx
pipx install git+https://github.com/tsvlgd/testproof
```

From a local clone:

```bash
cd /path/to/testproof
uv tool install --editable .
```

After installation, `testproof` is on your PATH. You can use `testproof` directly without `uv run`.

## Verify the CLI

The verification order is: CLI first, then skill, then Alan. Same commands, same report schema. Do not move to the next step until the previous one is verified.

### 1. Grade the weak fixture

```bash
testproof grade \
  --repo fixtures/shop \
  --all \
  --test-cmd "python -m pytest -q" \
  --format json \
  --output /tmp/tp-report.json
```

Expect 5 killed, 1 survived, score about 83.33 percent. The survivor is the free shipping boundary at 50.

### 2. Repair in dry run

```bash
testproof repair \
  --repo fixtures/shop \
  --report /tmp/tp-report.json \
  --test-cmd "python -m pytest -q" \
  --dry-run
```

Expect Kept 1, template hits 1, model attempts 0. `Model unavailable` is a notice, not a failure. Templates do not need a model key.

### 3. Apply the verified test

```bash
testproof repair \
  --repo fixtures/shop \
  --report /tmp/tp-report.json \
  --test-cmd "python -m pytest -q" \
  --apply
```

### 4. Re grade

```bash
testproof grade \
  --repo fixtures/shop \
  --all \
  --test-cmd "python -m pytest -q" \
  --format json \
  --output /tmp/tp-fixed.json
```

Expect score 100, survived 0.

### 5. Inspect the applied test

Open `fixtures/shop/test_shipping.py` and look for `test_repair_`. That is the proof: a test that passed on the original code and failed on the planted mutant. The engine kept it only because it proved that.

## Measured results

Full corpus results are in `benchmark/results.md`. Reproduce with:

```bash
uv run python benchmark/build_corpus.py
uv run python benchmark/run.py
```

The benchmark runs 12 synthetic modules with weak suites and known bug versions. It grades, repairs with apply, re grades, then runs the repaired suite against the bug. Detection before repair is by construction: the weak suite passes on the bug. Detection after repair is measured.

| Evidence | Before | After | Kept | Model calls |
| --- | --- | --- | --- | --- |
| Fixture (6 mutants) | 83.33 percent | 100 percent | 1 | 0 |
| Real repository (19 mutants) | 36.84 percent | 89.47 percent | 10 | 0 |
| Benchmark corpus (68 mutants) | 57.35 percent | 92.65 percent | 24 | 6 |

Real repository evidence: a three module repository with 19 mutants moved from 36.84 percent to 89.47 percent after repair. The engine kept 10 tests with deterministic templates and made no model calls. The two remaining survivors are clamp comparisons that no valid input can distinguish, so they are marked likely equivalent.

## Use with Alan

Install the skill for any SKILL.md compatible agent:

```bash
mkdir -p ~/.claude/skills
cp -R skills/testproof ~/.claude/skills/testproof
```

Alan: open this repository as the workspace so `skills/testproof/` is already there, or point Alan's skill install at that folder. Confirm the agent lists a skill named `testproof` before you trust it.

Automation recipe:

1. Trigger: pull request opened, or review requested.
2. Instructions: run the testproof skill, grade the diff, attach the JSON and Markdown report, repair only if the score is under the threshold, re grade, post the before and after. Do not approve or merge.
3. Command the automation runs:

```bash
testproof grade --repo . --base "origin/$BASE_REF" --head HEAD \
  --test-cmd "pytest -q" --threshold 80 \
  --format json --output .testproof/report.json
```

4. Put `MODEL_API_KEY` in Alan's secret store only if you want the model fallback. Template repair works without it.
5. Run the automation once by hand on a test pull request. If the agent lists the skill but never loads it, the folder name and the `name` field in `SKILL.md` do not match.

## Design principles

- Measure deterministically. A score must be reproducible.
- Mutate only what changed. Full repository runs are opt in.
- Never touch the working tree. Every mutant runs in a sandbox.
- Cap the work and keep a time budget. Report a partial score honestly.
- Let the model propose. Let the engine verify.
- Treat the report as the contract. Every integration reads the same schema.
- Say what the score does not prove. A high score is evidence, not correctness.

## Repository layout

```text
testproof/
├── README.md
├── CONSTRAINTS.md
├── LICENSE
├── pyproject.toml
├── Makefile
├── benchmark/
│   ├── build_corpus.py    Builds and validates the 12 module corpus
│   ├── corpus/            Original modules with weak suites
│   ├── bugs/              Known bug versions
│   ├── run.py             Grade, repair, regrade, bug check
│   ├── results.md         Measured before and after
│   └── results/           Raw JSON per run
├── skills/testproof/
│   └── SKILL.md           Portable agent skill
├── src/testproof/
│   ├── cli.py             grade, repair, report, diff commands
│   ├── engine.py          Mutation discovery and scoring
│   ├── repair.py          Template first repair with model fallback
│   ├── probe.py           Isolated probe for candidate inputs
│   ├── templates.py       Deterministic test case generation
│   ├── model.py           OpenRouter model client
│   ├── sandbox.py         Sandboxed execution
│   ├── runner.py          Test command execution with timeouts
│   ├── report.py          JSON and Markdown rendering
│   ├── diff.py            Diff resolver
│   ├── models.py          Report schema
│   ├── config.py          Model config file support
│   └── adapters/          Python mutation adapter
├── tests/                 Unit tests
├── fixtures/shop/         Weak fixture for demos
└── .github/workflows/     CI and TestProof preview
```

## License

MIT. See `LICENSE`.
# test
