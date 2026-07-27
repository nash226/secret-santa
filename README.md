# Secret Santa

A small Python application that creates a Secret Santa draw while preventing:

- a participant from drawing themselves;
- a giver from drawing the same recipient more than once in a rolling
  three-exchange window; and
- spouses, parents, and children from drawing one another.

The repository includes both the intentionally naive Part One solution and the
constraint-aware solution used for Parts Two and Three.

## Requirements

- Python 3.11 or newer
- No runtime dependencies

## Run

Run the included example directly from the source tree:

```bash
PYTHONPATH=src python -m secret_santa.cli examples/family.json
```

Add `--seed 42` to make a draw reproducible for testing or demonstrations:

```bash
PYTHONPATH=src python -m secret_santa.cli examples/family.json --seed 42
```

For a conventional local installation:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
secret-santa examples/family.json
```

The output is a JSON object whose keys are givers and values are recipients.
In a real exchange, this complete result should be distributed privately rather
than shown to every participant.

## Input format

The input JSON contains:

- `people`: required objects with unique `id` and human-readable `name` values;
- `history`: optional assignments ordered oldest to newest, using IDs; and
- `immediate_family`: optional spouse or parent/child ID pairs.

See [`examples/family.json`](examples/family.json) for a complete example.
Sibling relationships are intentionally not inferred: the prompt excludes only
spouses, parents, and children.

## Test

The test suite uses only Python's standard library:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Design

### Part One: naive rejection sampling

`create_naive_assignment` copies and shuffles the participant IDs until it finds
a permutation with no self-assignment. It is concise and random, making it a
useful first implementation.

Its tradeoff is wasted work: a rejected shuffle contributes nothing to the next
attempt. Adding history and family rules makes valid full permutations rarer, so
rejection sampling can become slow and unpredictable. A maximum attempt count
keeps it from looping forever.

### Parts Two and Three: constrained matching

`SecretSantaService` models the draw as a bipartite graph. Givers are on one
side, recipients are on the other, and an edge exists only when a pairing is
allowed. An augmenting-path matching algorithm then finds a complete one-to-one
assignment or reports that the constraints are impossible.

Candidate order is shuffled, so repeated runs can produce different valid
draws. Givers with the fewest choices are processed first. The matching step is
`O(VE)` for `V` participants and `E` allowed giver/recipient pairs, compared
with the naive solution's unbounded number of full shuffles.

The result is randomized but not sampled uniformly from all valid assignments.
Uniform sampling would add significant complexity and is not needed to satisfy
the stated requirements; this is worth revisiting if statistical fairness
across many exchanges becomes a product requirement.

The service keeps no request-specific mutable state. Each invocation builds its
own candidate graph and assignment, allowing one service instance to be safely
used by concurrent callers. The supplied `random.Random` should still be owned
by a single call; omit it in production to create a fresh generator.

## Assumptions

- “At most once every 3 years” means one occurrence in any rolling window of
  three exchanges. Therefore, the current draw excludes pairs from the prior
  two history entries.
- An assignment is directed: `alice -> bob` means Alice buys for Bob.
  `bob -> alice` is a different pairing.
- Every participant gives one gift and receives one gift.
- Person IDs are stable and unique; names are display values and need not be
  unique.
- History is trusted as recorded past data. Only entries involving current
  participant IDs affect the current candidate graph.
- If family and history constraints leave no complete assignment, the
  application returns a clear error instead of silently relaxing a rule.

## Possible extensions

- Persist exchanges and relationships in a database with transactions.
- Add authentication and reveal only each giver's recipient.
- Use cryptographically secure randomness if draw unpredictability is a formal
  requirement.
- Explain which constraints conflict when no complete assignment exists.
