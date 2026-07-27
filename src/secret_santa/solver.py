"""Parts Two and Three: constraint-aware bipartite matching."""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence

from .models import Assignment, Person, RelationshipGraph
from .naive import _validate_people


class NoValidAssignmentError(ValueError):
    """Raised when the supplied constraints make a complete draw impossible."""


class SecretSantaService:
    """Create independent, thread-safe Secret Santa assignments."""

    def __init__(self, repeat_window_years: int = 3) -> None:
        if repeat_window_years < 1:
            raise ValueError("repeat_window_years must be at least 1")
        self.repeat_window_years = repeat_window_years

    def create_assignment(
        self,
        people: Sequence[Person],
        *,
        history: Sequence[Mapping[str, str]] = (),
        relationships: RelationshipGraph | None = None,
        rng: random.Random | None = None,
    ) -> Assignment:
        """Return a complete assignment that satisfies every constraint."""

        _validate_people(people)
        family = relationships or RelationshipGraph()
        self._validate_relationships(people, family)

        person_ids = [person.person_id for person in people]
        recent_pairs = self._recent_pairs(history)
        candidates = {
            giver_id: [
                recipient_id
                for recipient_id in person_ids
                if self._is_allowed(
                    giver_id, recipient_id, recent_pairs, family
                )
            ]
            for giver_id in person_ids
        }

        if any(not choices for choices in candidates.values()):
            raise NoValidAssignmentError(
                "at least one person has no eligible recipient"
            )

        randomizer = rng or random.Random()
        for choices in candidates.values():
            randomizer.shuffle(choices)

        # Constrained givers go first, reducing failed augmenting-path searches.
        giver_order = list(person_ids)
        randomizer.shuffle(giver_order)
        giver_order.sort(key=lambda giver_id: len(candidates[giver_id]))

        recipient_to_giver: dict[str, str] = {}
        for giver_id in giver_order:
            if not self._find_match(
                giver_id, candidates, recipient_to_giver, set()
            ):
                raise NoValidAssignmentError(
                    "constraints do not allow a complete Secret Santa assignment"
                )

        return {
            giver_id: recipient_id
            for recipient_id, giver_id in recipient_to_giver.items()
        }

    def _recent_pairs(
        self, history: Sequence[Mapping[str, str]]
    ) -> set[tuple[str, str]]:
        # The current exchange counts as one year in the rolling window.
        prior_years = max(0, self.repeat_window_years - 1)
        recent_history = history[-prior_years:] if prior_years else ()
        return {
            (giver_id, recipient_id)
            for assignment in recent_history
            for giver_id, recipient_id in assignment.items()
        }

    @staticmethod
    def _is_allowed(
        giver_id: str,
        recipient_id: str,
        recent_pairs: set[tuple[str, str]],
        relationships: RelationshipGraph,
    ) -> bool:
        return (
            giver_id != recipient_id
            and recipient_id not in relationships.family_of(giver_id)
            and (giver_id, recipient_id) not in recent_pairs
        )

    def _find_match(
        self,
        giver_id: str,
        candidates: Mapping[str, Sequence[str]],
        recipient_to_giver: dict[str, str],
        visited_recipients: set[str],
    ) -> bool:
        """Find or rearrange an augmenting path for one giver."""

        for recipient_id in candidates[giver_id]:
            if recipient_id in visited_recipients:
                continue
            visited_recipients.add(recipient_id)

            current_giver = recipient_to_giver.get(recipient_id)
            if current_giver is None or self._find_match(
                current_giver,
                candidates,
                recipient_to_giver,
                visited_recipients,
            ):
                recipient_to_giver[recipient_id] = giver_id
                return True
        return False

    @staticmethod
    def _validate_relationships(
        people: Sequence[Person], relationships: RelationshipGraph
    ) -> None:
        person_ids = {person.person_id for person in people}
        unknown_ids = relationships.participant_ids() - person_ids
        if unknown_ids:
            unknown = ", ".join(sorted(unknown_ids))
            raise ValueError(f"relationships reference unknown IDs: {unknown}")
