# Secret Santa

A Python application that creates one-to-one Secret Santa assignments while
preventing self-draws, recent repeat pairings, and immediate-family pairings.
It includes the naive Part One solution and the constraint-aware Parts Two and
Three solution.

## Requirements

- Python 3.11+
- No runtime dependencies

## Run

Run the included example:

```bash
PYTHONPATH=src python -m secret_santa.cli examples/family.json --seed 42
```

Or install the command locally:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
secret-santa examples/family.json
```

`--seed` is optional and makes demonstrations reproducible. Output maps each
giver's display name to their recipient's display name.

## Docker

```bash
docker build --target runtime -t secret-santa .
docker run --rm \
  --mount type=bind,src="$PWD/examples",dst=/data,readonly \
  secret-santa /data/family.json --seed 42
```

The runtime image uses a non-root user. To run the tests in Docker:

```bash
docker build --target test -t secret-santa-test .
docker run --rm secret-santa-test
```

## Input

The JSON input contains:

- `people`: required unique IDs and display names;
- `history`: optional assignments ordered oldest to newest; and
- `immediate_family`: optional spouse or parent/child ID pairs.

See [`examples/family.json`](examples/family.json) for a complete example.

## Test

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Design

The naive solution shuffles recipients until nobody draws themselves. It is
simple, but repeatedly discards invalid permutations and becomes unpredictable
as constraints increase.

The optimized solution builds a bipartite graph containing only allowed
giver/recipient pairs, then finds a complete assignment using randomized
augmenting-path matching. It returns a clear error when no complete assignment
exists. The service retains no draw state, so calls are independent and safe to
run concurrently.

The matching is randomized but not uniformly sampled from every possible valid
assignment. Uniform sampling was not required and would add substantial
complexity.

## Scalability

Candidate storage is `O(n²)` and matching is `O(VE)`, or `O(n³)` in the worst
case. A local benchmark of an unconstrained draw produced:

| Participants | Time |
| ---: | ---: |
| 100 | 0.002 s |
| 500 | 0.050 s |
| 1,000 | 0.209 s |

Times vary by machine and constraints. The recursive matcher reached Python's
recursion limit at 2,000 participants in this benchmark, so the current solution
is appropriate for family-sized exchanges but should be replaced with an
iterative matcher or Hopcroft-Karp before supporting thousands of participants.

This repository is a library and CLI, not a multi-user web application. A
production service should generate each exchange once, store it transactionally,
and serve individual results with authentication. Those reads would be `O(1)`;
concurrent regeneration of large draws would instead multiply CPU and memory
use.

## Assumptions

- A three-year window means the current exchange plus the prior two exchanges.
- Assignments are directed: `alice -> bob` differs from `bob -> alice`.
- Each participant gives once and receives once.
- IDs are stable and unique; display names need not be unique.
- Only spouses, parents, and children are excluded; siblings remain eligible.
- Constraints are never silently relaxed when a valid draw is impossible.
