# Merry Match

A Christmas-themed Secret Santa web app for nontechnical users. Families can
add participants, optionally connect spouses or parents and children, animate a
fair draw, and privately reveal one match at a time.

The project includes the intentionally naive Part One solution and the
constraint-aware Python solver used by the interface for Parts Two and Three.

## Run

Requires Python 3.11+ and has no runtime dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
secret-santa
```

Open [http://localhost:8000](http://localhost:8000). The family list,
connections, and two most recent draws are saved only in that browser. The
server does not persist them.

## Docker

```bash
docker build --target runtime -t secret-santa .
docker run --rm -p 8000:8000 secret-santa
```

Then open [http://localhost:8000](http://localhost:8000).

## Test

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Or run the same suite in Docker:

```bash
docker build --target test -t secret-santa-test .
docker run --rm secret-santa-test
```

## How the draw works

The naive solution shuffles recipients until nobody draws themselves. It is
easy to follow but repeatedly discards invalid permutations.

The optimized solution builds a bipartite graph containing only allowed
giver/recipient pairs, then finds a complete assignment using randomized
augmenting-path matching. It prevents:

- self-draws;
- a giver receiving the same recipient within a rolling three-exchange window;
  and
- pairings between spouses, parents, and children.

It returns a clear error instead of relaxing rules when no complete assignment
exists. Results are randomized but not uniformly sampled from every possible
valid assignment.

## Scalability

Candidate storage is `O(n²)` and matching is `O(VE)`, or `O(n³)` in the worst
case. A local unconstrained benchmark produced:

| Participants | Time |
| ---: | ---: |
| 100 | 0.002 s |
| 500 | 0.050 s |
| 1,000 | 0.209 s |

Times vary by machine and constraints. The recursive matcher reached Python's
recursion limit at 2,000 participants, so this version is appropriate for
family-sized exchanges.

The HTTP server handles requests concurrently and retains no draw state. A
production multi-user service would still need authentication, transactional
storage, HTTPS, and multiple worker processes. Generating an exchange once and
serving individual results would make subsequent reads `O(1)`.

## Assumptions

- A three-year window means the current exchange plus the prior two exchanges.
- Assignments are directed: `alice -> bob` differs from `bob -> alice`.
- Every participant gives once and receives once.
- IDs are unique; duplicate display names are disambiguated in the interface.
- Only spouses, parents, and children are excluded; siblings remain eligible.
