"""Command-line interface for JSON-based Secret Santa draws."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from .models import Person, RelationshipGraph
from .solver import NoValidAssignmentError, SecretSantaService


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a constraint-aware Secret Santa assignment."
    )
    parser.add_argument("input", type=Path, help="path to the input JSON file")
    parser.add_argument(
        "--seed",
        type=int,
        help="optional random seed for a reproducible draw",
    )
    args = parser.parse_args()

    try:
        data = _read_input(args.input)
        people = [
            Person(person["id"], person["name"]) for person in data["people"]
        ]
        relationships = RelationshipGraph.from_pairs(
            (pair["person_1"], pair["person_2"])
            for pair in data.get("immediate_family", [])
        )
        assignment = SecretSantaService().create_assignment(
            people,
            history=data.get("history", []),
            relationships=relationships,
            rng=random.Random(args.seed),
        )
    except (
        OSError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
        NoValidAssignmentError,
    ) as error:
        parser.error(str(error))

    names = {person.person_id: person.name for person in people}
    output = {
        names[giver_id]: names[recipient_id]
        for giver_id, recipient_id in assignment.items()
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


def _read_input(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as input_file:
        data = json.load(input_file)
    if not isinstance(data, dict):
        raise TypeError("input must be a JSON object")
    return data


if __name__ == "__main__":
    raise SystemExit(main())
