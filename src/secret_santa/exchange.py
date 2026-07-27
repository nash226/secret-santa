"""Immutable exchanges and thread-safe in-memory storage."""

from __future__ import annotations

import hmac
import random
import secrets
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol

from .models import Assignment, Person, RelationshipGraph
from .solver import SecretSantaService


class ExchangeNotFoundError(LookupError):
    """Raised when an exchange or private token does not exist."""


class ExchangeCollisionError(RuntimeError):
    """Raised when generated credentials collide with stored credentials."""


@dataclass(frozen=True, slots=True)
class Exchange:
    """A completed draw that cannot change after it is stored."""

    exchange_id: str
    organizer_token: str
    people: tuple[Person, ...]
    relationships: RelationshipGraph
    history: tuple[Mapping[str, str], ...]
    assignment: Mapping[str, str]
    reveal_tokens: Mapping[str, str]

    def __post_init__(self) -> None:
        person_ids = {person.person_id for person in self.people}
        if set(self.assignment) != person_ids:
            raise ValueError("assignment must contain every participant")
        if set(self.assignment.values()) != person_ids:
            raise ValueError("assignment must use every recipient exactly once")
        if set(self.reveal_tokens) != person_ids:
            raise ValueError("every participant needs a reveal token")
        if len(set(self.reveal_tokens.values())) != len(self.reveal_tokens):
            raise ValueError("reveal tokens must be unique")

        # Defensive copies keep completed exchanges immutable for every reader.
        object.__setattr__(
            self, "assignment", MappingProxyType(dict(self.assignment))
        )
        object.__setattr__(
            self,
            "history",
            tuple(MappingProxyType(dict(year)) for year in self.history),
        )
        object.__setattr__(
            self, "reveal_tokens", MappingProxyType(dict(self.reveal_tokens))
        )

    def person(self, person_id: str) -> Person:
        for person in self.people:
            if person.person_id == person_id:
                return person
        raise ExchangeNotFoundError("Participant not found.")


@dataclass(frozen=True, slots=True)
class Reveal:
    """The only assignment data returned for one private reveal token."""

    exchange_id: str
    giver: Person
    recipient: Person


class ExchangeRepository(Protocol):
    """Persistence boundary for completed exchanges."""

    def add(self, exchange: Exchange) -> None:
        """Store one exchange atomically."""

    def get(self, exchange_id: str) -> Exchange:
        """Return an exchange by its public identifier."""

    def get_by_reveal_token(self, reveal_token: str) -> tuple[Exchange, str]:
        """Return an exchange and giver ID for a private token."""


class InMemoryExchangeRepository:
    """Single-process repository safe for concurrent HTTP requests."""

    def __init__(self) -> None:
        self._exchanges: dict[str, Exchange] = {}
        self._reveal_index: dict[str, tuple[str, str]] = {}
        self._lock = threading.RLock()

    def add(self, exchange: Exchange) -> None:
        with self._lock:
            if exchange.exchange_id in self._exchanges:
                raise ExchangeCollisionError("exchange ID already exists")
            if any(
                token in self._reveal_index
                for token in exchange.reveal_tokens.values()
            ):
                raise ExchangeCollisionError("reveal token already exists")

            # Both indexes are updated while holding one lock, so readers never
            # observe an exchange without all of its reveal tokens.
            self._exchanges[exchange.exchange_id] = exchange
            for giver_id, token in exchange.reveal_tokens.items():
                self._reveal_index[token] = (exchange.exchange_id, giver_id)

    def get(self, exchange_id: str) -> Exchange:
        with self._lock:
            try:
                return self._exchanges[exchange_id]
            except KeyError as error:
                raise ExchangeNotFoundError("Exchange not found.") from error

    def get_by_reveal_token(self, reveal_token: str) -> tuple[Exchange, str]:
        with self._lock:
            try:
                exchange_id, giver_id = self._reveal_index[reveal_token]
                return self._exchanges[exchange_id], giver_id
            except KeyError as error:
                raise ExchangeNotFoundError("Reveal link not found.") from error

    def count(self) -> int:
        with self._lock:
            return len(self._exchanges)


class ExchangeService:
    """Generate once, store atomically, and reveal one assignment at a time."""

    MAX_CREDENTIAL_ATTEMPTS = 5

    def __init__(
        self,
        repository: ExchangeRepository,
        *,
        solver: SecretSantaService | None = None,
        token_factory: Callable[[], str] | None = None,
    ) -> None:
        self._repository = repository
        self._solver = solver or SecretSantaService()
        self._token_factory = token_factory or (
            lambda: secrets.token_urlsafe(32)
        )

    def create(
        self,
        people: Sequence[Person],
        *,
        history: Sequence[Mapping[str, str]] = (),
        relationships: RelationshipGraph | None = None,
        rng: random.Random | None = None,
    ) -> Exchange:
        """Generate and atomically store a completed exchange."""

        family = relationships or RelationshipGraph()
        assignment = self._solver.create_assignment(
            people,
            history=history,
            relationships=family,
            rng=rng,
        )

        for _ in range(self.MAX_CREDENTIAL_ATTEMPTS):
            try:
                exchange = self._build_exchange(
                    people, family, history, assignment
                )
                self._repository.add(exchange)
            except ExchangeCollisionError:
                continue
            return exchange
        raise RuntimeError("could not generate unique exchange credentials")

    def reveal(self, reveal_token: str) -> Reveal:
        """Return exactly one giver/recipient pair for a private token."""

        exchange, giver_id = self._repository.get_by_reveal_token(reveal_token)
        return Reveal(
            exchange_id=exchange.exchange_id,
            giver=exchange.person(giver_id),
            recipient=exchange.person(exchange.assignment[giver_id]),
        )

    def get_for_organizer(
        self, exchange_id: str, organizer_token: str
    ) -> Exchange:
        """Return an exchange only when its organizer credential matches."""

        exchange = self._repository.get(exchange_id)
        if not hmac.compare_digest(
            exchange.organizer_token, organizer_token
        ):
            # Use the same error as an unknown ID to avoid confirming that an
            # exchange exists to someone without its private organizer token.
            raise ExchangeNotFoundError("Exchange not found.")
        return exchange

    def _build_exchange(
        self,
        people: Sequence[Person],
        relationships: RelationshipGraph,
        history: Sequence[Mapping[str, str]],
        assignment: Assignment,
    ) -> Exchange:
        credentials = [
            self._token_factory() for _ in range(len(people) + 2)
        ]
        if any(not credential for credential in credentials) or len(
            credentials
        ) != len(set(credentials)):
            raise ExchangeCollisionError("generated credentials must be unique")

        exchange_id, organizer_token, *private_tokens = credentials
        reveal_tokens = dict(
            zip(
                (person.person_id for person in people),
                private_tokens,
                strict=True,
            )
        )
        return Exchange(
            exchange_id=exchange_id,
            organizer_token=organizer_token,
            people=tuple(people),
            relationships=relationships,
            history=tuple(history),
            assignment=assignment,
            reveal_tokens=reveal_tokens,
        )
