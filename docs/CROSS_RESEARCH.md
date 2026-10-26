# Cross Research

This document records the external evidence behind TestProof, the caveats that shaped the design, and the sources a reviewer can check.

## 1. Research question

Is "tests pass but the tests are weak" a real problem worth building for, especially when AI agents write both the code and the tests? And if it is real, what is already solved, what is crowded, and where is the defensible gap?

## 2. Findings

### 2.1 The problem is validated at industrial scale

Meta built Automated Compliance Hardening (ACH), which uses LLMs to generate relevant mutants and then generate tests that catch them. Meta reported that privacy engineers accepted 73 percent of the generated tests, with 36 percent judged privacy relevant. Meta's engineering post lists five barriers that historically blocked mutation testing: scale, unrealistic mutants, equivalent mutants, compute cost, and effort spent on low value mutants. The post argues that LLMs address each barrier.

Google generated almost 17 million mutants across 760,000 code changes and surfaced 2 million of them during code review, across 24,000 developers on 1,000 projects. This is strong evidence that mutation testing is not a theoretical idea. It is a practice at the largest software organizations.

Implication: the problem is real. The pitch does not need to convince a judge that mutation testing matters.

Source:

- Meta Engineering, "LLMs Are the Key to Mutation Testing and Better Compliance", September 2025.
- Meta ACH paper, arXiv 2501.12862.
- Google mutation testing at review scale, as summarized in the Augment Code guide.

### 2.2 LLM generated tests are often boundary blind

A practical guide on mutation testing for AI generated code reports that a vanilla LLM prompt reached a 53 percent mutation score on HumanEval Java. The same guide describes three failure modes:

- Boundary value blindness. The model checks values far from the boundary and misses the exact boundary.
- Assertions anchored to training data. The model asserts what it expects from training data instead of what the code does.
- Weak assertions. The model asserts that a call returns something, not that it returns the right thing.

A study of 22,374 test generation tasks found that over 99 percent of 23,977 tests that failed on mutated code passed on the original program. That is the failure TestProof is built to catch: a test that looks plausible but does not detect the change.

Implication: a model alone cannot be trusted to grade its own tests. The deterministic verifier is essential.

Sources:

- Augment Code, "Mutation Testing for AI Generated Code: A Practical Guide".
- MutGen, arXiv 2506.02954.

### 2.3 LLM mutants are more realistic but noisier

A 2026 ACM study evaluated BugFarm, LLMorpheus, and a new prompt across 851 real bugs from two Java benchmarks. LLM generated mutants reached a 77.4 percent real bug detection rate, compared with 41.6 percent for rule based mutants, a gain of 35.8 percentage points. But LLM mutants also had worse non compilability by 25.9 percentage points, worse duplication by 7.1 points, and worse equivalent mutant rates by 2.6 points.

Implication: rule based mutants are the right default for a 24 hour build because they are deterministic, cheap, and compile. LLM generated mutants are a roadmap feature for realism, not a Phase 1 requirement.

Source:

- ACM, "A Comprehensive Study on Large Language Models for Mutation Testing", 2026, DOI 10.1145/3805038.

### 2.4 Mutation score is a proxy, not proof

A 2026 ISSTA replicability study re examined the relationship between coverage, mutation score, and real bug detection for LLM generated test suites across 11 state of the art LLMs and over 100,000 test cases. The finding is nuanced:

- In regression style settings where the code under test can be assumed bug free, coverage and mutation score can provide meaningful signals when comparing across models.
- When the code under test may already be buggy and the goal is to expose the bug, coverage and mutation score are no longer reliable indicators.

Implication: the benchmark must report both mutation score and real bug detection. The product must never claim that a high score proves correctness. The report should say what the score measures and what it does not.

Source:

- Zhao, Zhou, Cohen, "Do Coverage and Mutation Scores of LLM Generated Test Suites Correlate with Their Effectiveness? (Replicability Study)", ISSTA 2026, arXiv 2607.22880.

### 2.5 The Python tool space is crowded but the reporting is weak

A static and dynamic comparison of four Python mutation tools (CosmicRay, MutPy, MutMut, Mutatest) found that MutMut and Mutatest lack intuitive report features. The comparison also notes that Java tool studies found PIT to be the most effective at killing mutants with broad coverage.

Stryker covers JavaScript, TypeScript, C#, and Scala. PIT covers Java. mutmut is the most cited Python option. There is already a GitHub Action that runs mutmut on changed lines and comments on a pull request.

Implication: do not compete on the mutation algorithm. Compete on the workflow: diff scoped, CI native, agent friendly, Alan native, and verified repair.

Sources:

- ACM, "Static and Dynamic Comparison of Mutation Testing Tools for Python", 2025, DOI 10.1145/3701625.3701659.
- Stryker Mutator documentation.
- mutmut documentation.
- GitHub Marketplace, "Python Mutation Report" Action.

### 2.6 Agent skills are a real distribution channel

The Agent Skills specification defines a portable `SKILL.md` format with YAML frontmatter, a required `name` and `description`, and optional `license`, `compatibility`, `metadata`, and `allowed-tools`. Skills are loaded progressively: metadata at startup, the body when activated, and referenced files only when needed. The format is supported by Claude Code, Codex, Cursor, Gemini CLI, OpenCode, and Alan.

Implication: a skill is the cheapest way to reach Alan users and non Alan users with the same artifact. It is also the right 24 hour integration path because it needs no hosting.

Sources:

- Agent Skills specification, agentskills.io/specification.
- Anthropic skills repository, github.com/anthropics/skills.
- Alan skills repository, github.com/tryalan-ai/alan-skills.

### 2.7 Alan's integration surface

Alan is a software factory. Work moves through tasks, agent sessions, artifacts, reviews, test evidence, and deploy gates. Alan connects GitHub, Azure DevOps, Slack, and Teams. It runs coding agents in local or cloud sandboxes. Its documentation warns against treating one green signal as full readiness.

Alan has four relevant surfaces:

1. Skills. A `SKILL.md` folder that works across SKILL.md compatible agents. Official examples include `alan-check-ci`, `alan-review-pr`, and `alan-test-feature`.
2. Plugins. A marketplace entry with `.cursor-plugin/plugin.json`, `mcp.json`, and a logo. The marketplace has 208 plugins in 21 categories, including Testing and QA. The contribution rules require remote HTTPS MCP servers because Alan does not run stdio servers yet.
3. GitHub integration. Pull requests, checks, and CI are first class. An automation can trigger on a PR event and run an agent session in a sandbox.
4. Automations. Triggers on schedule or event, runs as an agent session, produces artifacts. The docs recommend the GitHub "Review Requested" trigger for automatic review.

The Testing and QA category contains Cypress Cloud, mabl, Momentic, Chromatic, Sauce Labs, Postman, BugHerd, Jam, Meticulous, and Userback. None of them answer "are these tests strong enough to catch a bug". Alan's testing evidence guide treats passing unit tests as sufficient evidence for logic changes.

Implication: there is a real category gap. The skill and GitHub Action path is feasible in 24 hours. The marketplace plugin path requires a hosted remote MCP server and is a roadmap item.

Sources:

- Alan documentation, docs.tryalan.ai.
- Alan product page, tryalan.ai/product.
- Alan plugins repository, github.com/tryalan-ai/plugins.
- Alan skills repository, github.com/tryalan-ai/alan-skills.
- Alan pull requests and testing evidence docs.

## 3. What the research changes about the design

| Finding | Design consequence |
| --- | --- |
| Mutation testing is validated at scale | The problem statement is safe. Spend the pitch on the workflow, not on education |
| LLM tests are boundary blind | The repair prompt must include the mutant and the boundary, and the verifier must prove the kill |
| LLM mutants are realistic but noisy | Use rule based mutants first. Mark LLM mutants as a roadmap feature |
| Mutation score is a proxy | Report mutation score and real bug detection. Never claim proof of correctness |
| Python tools have weak reporting | Make the report a first class product surface |
| Skills are portable | Ship a `SKILL.md` as the primary Alan integration |
| Marketplace plugins need remote HTTPS | Do not attempt a hosted plugin in 24 hours |
| Alan treats passing unit tests as evidence | Position TestProof as the missing strength check, not another test runner |

## 4. Competitive positioning

TestProof is not the first mutation testing tool. It is the first one designed for the Alan verification loop and for AI written code.

The claim to make:

> Your tests pass and your coverage is high. TestProof tells you whether they would catch a bug, writes the missing tests with an open source model, and proves each new test kills the bug before it keeps it.

The claim not to make:

> TestProof proves your code is correct.

The first claim is true and demoable. The second is false and would be caught by a knowledgeable judge.

## 5. Open questions to ask in the Alan Discord

1. Does the tool need to run inside Alan, or is a skill plus a CI check enough for the OpenFire rules?
2. Which open source model provider do the 20 dollar credits use, and what is the API key format?
3. Does the marketplace accept a plugin whose MCP server is hosted, or can a skill ship without a marketplace entry?
4. Is there an Alan MCP tool for attaching a test report artifact from a local skill?

## 6. Source list

- Meta Engineering, "LLMs Are the Key to Mutation Testing and Better Compliance", 2025. https://engineering.fb.com/2025/09/30/security/llms-are-the-key-to-mutation-testing-and-better-compliance/
- Meta ACH paper. https://arxiv.org/pdf/2501.12862
- ACM, "A Comprehensive Study on Large Language Models for Mutation Testing", 2026. https://dl.acm.org/doi/10.1145/3805038
- Zhao, Zhou, Cohen, "Do Coverage and Mutation Scores of LLM Generated Test Suites Correlate with Their Effectiveness?", ISSTA 2026. https://arxiv.org/abs/2607.22880
- Augment Code, "Mutation Testing for AI Generated Code: A Practical Guide". https://www.augmentcode.com/guides/mutation-testing-ai-generated-code
- MutGen, arXiv 2506.02954. https://arxiv.org/abs/2506.02954
- ACM, "Static and Dynamic Comparison of Mutation Testing Tools for Python", 2025. https://dl.acm.org/doi/10.1145/3701625.3701659
- Stryker Mutator. https://stryker-mutator.io/
- Agent Skills specification. https://agentskills.io/specification
- Anthropic skills repository. https://github.com/anthropics/skills
- Alan documentation. https://docs.tryalan.ai
- Alan product page. https://tryalan.ai/product/
- Alan plugins repository. https://github.com/tryalan-ai/plugins
- Alan skills repository. https://github.com/tryalan-ai/alan-skills
- GitHub Marketplace, "Python Mutation Report". https://github.com/marketplace/actions/python-mutation-report
