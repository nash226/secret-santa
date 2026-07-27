"""Public API for the Secret Santa assignment package."""

from .exchange import (
    Exchange,
    ExchangeNotFoundError,
    ExchangeService,
    InMemoryExchangeRepository,
    Reveal,
)
from .models import Assignment, Person, RelationshipGraph
from .naive import create_naive_assignment
from .solver import NoValidAssignmentError, SecretSantaService

__all__ = [
    "Assignment",
    "Exchange",
    "ExchangeNotFoundError",
    "ExchangeService",
    "InMemoryExchangeRepository",
    "NoValidAssignmentError",
    "Person",
    "RelationshipGraph",
    "Reveal",
    "SecretSantaService",
    "create_naive_assignment",
]
