"""Part One: a deliberately simple rejection-sampling solution."""

from __future__ import annotations

import random
from collections.abc import Sequence

from .models import Assignment, Person


def create_naive_assignment(
    people: Sequence[Person],
    *,
    rng: random.Random | None = None,
    max_attempts: int = 10_000,
) -> Assignment:
    """Shuffle recipients until nobody draws themselves.

    This is easy to understand, but it repeatedly throws away work and does not
    scale well when more constraints are introduced. ``max_attempts`` prevents
    malformed or unlucky input from causing an infinite loop.
    """

    _validate_people(people)
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    randomizer = rng or random.Random()
    giver_ids = [person.person_id for person in people]

    for _ in range(max_attempts):
        recipient_ids = giver_ids.copy()
        randomizer.shuffle(recipient_ids)
        if all(giver != recipient for giver, recipient in zip(giver_ids, recipient_ids)):
            return dict(zip(giver_ids, recipient_ids))

    raise RuntimeError(f"no assignment found after {max_attempts} attempts")


def _validate_people(people: Sequence[Person]) -> None:
    if len(people) < 2:
        raise ValueError("at least two people are required")

    person_ids = [person.person_id for person in people]
    if len(person_ids) != len(set(person_ids)):
        raise ValueError("person IDs must be unique")
