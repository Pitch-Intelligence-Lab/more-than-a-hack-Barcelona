# Tooling Policy

## Decision

Codex is the primary engineering and integration environment. Cursor and DeepSeek are optional support tools, not project dependencies.

## Codex

Use Codex for:

- implementation;
- tests;
- code review;
- repository changes;
- technical documentation;
- coordination of small, independently verifiable tasks.

Codex remains responsible for integrating and reviewing delegated work.

## Cursor

Cursor may be used as:

- a manual code editor;
- an optional AI code assistant for public code;
- a tool for reviewing diffs and navigating the repository.

Do not open the competition data directory in Cursor. Do not pay for a model upgrade until an actual workflow bottleneck is demonstrated.

## DeepSeek

DeepSeek may be assigned narrow engineering tasks such as:

- implementing an isolated utility;
- writing tests for a defined interface;
- reviewing public code;
- checking documentation consistency.

DeepSeek must not:

- read competition data;
- choose possession rules independently;
- train or tune on the provided match;
- push unreviewed changes to `main`.

## Data boundary

All AI coding tools operate only on the code workspace. Competition data remains in a separate local data root and is accessed by code through `MTAH_DATA_DIR`.
