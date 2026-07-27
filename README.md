# Merry Match

A Christmas-themed Secret Santa application for nontechnical users. An
organizer adds the family, creates one fair draw, and sends each participant a
private reveal link.

The project includes the deliberately naive Part One solution and the
constraint-aware Python solver for Parts Two and Three.

## Run with Docker

```bash
docker build --target runtime -t secret-santa .
docker run --rm -p 8000:8000 secret-santa
```

Open [http://localhost:8000](http://localhost:8000).

The organizer can open or copy every private link locally. Another device on
the same network can use the links after replacing `localhost` with the Docker
host's local IP address.

## Run with Python

Requires Python 3.11+ and has no runtime dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
secret-santa
```

## Test

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Or run the same suite in Docker:

```bash
docker build --target test -t secret-santa-test .
docker run --rm secret-santa-test
```

## User flow

1. Add everyone participating in the exchange.
2. Optionally connect spouses, parents, and children.
3. Create the exchange once.
4. Copy one private reveal link for each participant.
5. Save the exchange as history before drawing the following year.

Each reveal token returns exactly one giver and recipient. Refreshing a reveal
link returns the stored assignment and never redraws names. Organizer
credentials can retrieve the reveal links without exposing recipients.

## Design

The naive solution shuffles complete recipient lists until nobody draws
themselves. It is easy to understand but wastes rejected work.

The optimized solution filters forbidden giver and recipient pairs, then finds
a complete assignment using randomized bipartite matching. It prevents:

- self-draws;
- pairings repeated within a rolling three-exchange window; and
- pairings between spouses, parents, and children.

`ExchangeRepository` separates storage from exchange behavior. The provided
`InMemoryExchangeRepository` uses a lock for atomic writes and concurrent
reads. Completed exchanges are immutable, and cryptographically secure tokens
protect organizer and participant access.

The in-memory design is intentional for this take-home. Exchanges disappear
when the process or container stops and are not shared across multiple server
processes. PostgreSQL could replace the repository without changing the solver
or HTTP contract.

## Scalability

Candidate storage is `O(n²)` and matching is `O(VE)`, or `O(n³)` in the worst
case. A local unconstrained benchmark produced:

| Participants | Time |
| ---: | ---: |
| 100 | 0.002 s |
| 500 | 0.050 s |
| 1,000 | 0.209 s |

The recursive matcher reached Python's recursion limit at 2,000 participants.
This is appropriate for family-sized exchanges.

## Assumptions

- A three-year window means the current exchange plus the prior two exchanges.
- Assignments are directed: `alice -> bob` differs from `bob -> alice`.
- Every participant gives once and receives once.
- IDs are unique; the interface asks duplicate names to use a nickname.
- Only spouses, parents, and children are excluded. Siblings remain eligible.
- Private links are capability tokens and should be shared only with the named
  participant.
