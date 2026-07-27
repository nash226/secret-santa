# AGENTS.md

This guide is for coding agents and contributors working in this repository.

## Purpose

Merry Match creates one immutable Secret Santa exchange and private reveal
links. A valid exchange assigns every participant exactly once while preventing
self-draws, recent repeat pairs, and immediate-family pairs.

The current exchange and prior two exchanges form the rolling three-exchange
window. Siblings remain eligible.

## Verify

From the repository root, run the application with Docker:

```bash
docker build --target runtime -t secret-santa .
docker run --rm -p 8000:8000 secret-santa
```

Open `http://localhost:8000`.

Run the test suite with Docker:

```bash
docker build --target test -t secret-santa-test .
docker run --rm secret-santa-test
```

## Codebase map

- `src/secret_santa/models.py`: participant and family relationship models.
- `src/secret_santa/naive.py`: Part One rejection-sampling implementation.
- `src/secret_santa/solver.py`: constraint filtering and bipartite matching.
- `src/secret_santa/exchange.py`: immutable exchanges, tokens, repository, and
  exchange service.
- `src/secret_santa/web.py`: validation, private APIs, assets, and HTTP server.
- `src/secret_santa/web_assets/`: organizer and participant browser interface.
- `tests/`: standard-library unit and concurrent HTTP tests.

## Invariants

- Assignments map `giver_id -> recipient_id`.
- IDs, not display names, are identity keys.
- Relationship edges are symmetric.
- History is ordered from oldest to newest.
- Never relax constraints silently.
- Generate and store an exchange once. Refreshes must never redraw it.
- Reveal endpoints return exactly one giver and recipient.
- Organizer endpoints return reveal links but no recipients.
- Repository writes remain atomic and safe for concurrent HTTP requests.
- Browser state may contain the family draft and organizer credentials, but
  never the complete assignment.

## Contribution guidance

- Support Python 3.11+ and prefer the standard library.
- Keep comments focused on intent and non-obvious tradeoffs.
- Add tests for normal behavior, edge cases, privacy, and concurrency.
- Exercise both organizer and participant flows before committing.
- Preserve the naive implementation as a contrast with the optimized solver.
- The recursive matcher becomes unreliable around Python's recursion limit.
  Replace it with an iterative matcher or Hopcroft-Karp before targeting
  thousands of participants.
- Never add a `Co-authored-by` trailer or attribute an AI assistant as a commit
  co-author.
