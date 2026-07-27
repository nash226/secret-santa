# AGENTS.md

This guide is for coding agents and contributors working in this repository.

## Project purpose

The application creates one-to-one Secret Santa assignments. A valid draw:

- assigns every participant exactly one recipient;
- assigns every recipient exactly once;
- never assigns a participant to themselves;
- does not repeat a directed giver/recipient pair from either of the previous
  two exchanges; and
- does not pair spouses, parents, or children.

The current exchange and the prior two exchanges make up the rolling
three-exchange window. Siblings are allowed because they are not excluded by
the original requirements.

## Quick verification

The project has no runtime dependencies. From the repository root, run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m secret_santa.cli examples/family.json --seed 42
```

To verify installation as a package:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
secret-santa examples/family.json --seed 42
```

## Docker

Build and run the CLI image:

```bash
docker build --target runtime -t secret-santa .
docker run --rm \
  --mount type=bind,src="$PWD/examples",dst=/data,readonly \
  secret-santa /data/family.json --seed 42
```

Run the tests in the container:

```bash
docker build --target test -t secret-santa-test .
docker run --rm secret-santa-test
```

## Codebase map

- `src/secret_santa/models.py`: immutable participant and family relationship
  domain models.
- `src/secret_santa/naive.py`: Part One rejection-sampling implementation.
- `src/secret_santa/solver.py`: Parts Two and Three constraint filtering and
  augmenting-path matching.
- `src/secret_santa/cli.py`: JSON input parsing and display-name output.
- `tests/`: standard-library unit tests.
- `examples/family.json`: example input covering history and family rules.

## Design invariants

- Assignment dictionaries map `giver_id -> recipient_id`.
- Person IDs, rather than display names, are identity keys.
- Relationship edges are symmetric.
- History is ordered from oldest to newest.
- A draw must not silently relax constraints. Raise `NoValidAssignmentError`
  when a complete assignment is impossible.
- `SecretSantaService` must remain stateless across calls so callers can safely
  share a service instance.
- Random seeds are for reproducible tests and demonstrations, not production
  secrecy.

## Contribution guidance

- Support Python 3.11 and newer.
- Prefer the standard library unless a dependency provides clear value.
- Keep comments concise and focused on intent or non-obvious tradeoffs.
- Add or update tests for normal behavior, edge cases, and impossible draws.
- Run the unit tests and CLI example before committing.
- Preserve the naive implementation as an explicit contrast with the optimized
  solver.
- The recursive matcher currently approaches Python's recursion limit around
  1,000 participants and can fail near 2,000. If large exchanges are required,
  replace it with an iterative matcher or Hopcroft-Karp and add scale tests.
- Never add a `Co-authored-by` trailer or attribute an AI assistant as a commit
  co-author.
