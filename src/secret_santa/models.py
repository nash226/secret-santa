"""Domain models shared by the assignment implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Iterable, Mapping

Assignment = dict[str, str]


@dataclass(frozen=True, slots=True)
class Person:
    """A participant with a stable ID and a display name."""

    person_id: str
    name: str

    def __post_init__(self) -> None:
        if not self.person_id.strip():
            raise ValueError("person_id cannot be blank")
        if not self.name.strip():
            raise ValueError("name cannot be blank")


@dataclass(frozen=True, slots=True)
class RelationshipGraph:
    """Immediate-family relationships represented as undirected pairs."""

    _family_by_person: Mapping[str, frozenset[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Copy the input so callers cannot mutate relationships during a draw.
        normalized = {
            person_id: frozenset(relative_ids)
            for person_id, relative_ids in self._family_by_person.items()
        }
        for person_id, relative_ids in normalized.items():
            if person_id in relative_ids:
                raise ValueError(f"{person_id!r} cannot be their own relative")
            for relative_id in relative_ids:
                if person_id not in normalized.get(relative_id, frozenset()):
                    raise ValueError(
                        f"relationship {person_id!r} -> {relative_id!r} "
                        "must be symmetric"
                    )
        object.__setattr__(self, "_family_by_person", MappingProxyType(normalized))

    @classmethod
    def from_pairs(
        cls, pairs: Iterable[tuple[str, str]]
    ) -> RelationshipGraph:
        """Build symmetric relationships from spouse or parent/child pairs."""

        graph: dict[str, set[str]] = {}
        for first_id, second_id in pairs:
            if first_id == second_id:
                raise ValueError(f"{first_id!r} cannot be their own relative")
            graph.setdefault(first_id, set()).add(second_id)
            graph.setdefault(second_id, set()).add(first_id)
        return cls(
            {
                person_id: frozenset(relative_ids)
                for person_id, relative_ids in graph.items()
            }
        )

    def family_of(self, person_id: str) -> frozenset[str]:
        """Return the person's spouse, parents, and children."""

        return self._family_by_person.get(person_id, frozenset())

    def participant_ids(self) -> frozenset[str]:
        """Return every ID referenced by the graph."""

        return frozenset(self._family_by_person)
