"""Public API for the Secret Santa assignment package."""

from .models import Assignment, Person, RelationshipGraph
from .naive import create_naive_assignment
from .solver import NoValidAssignmentError, SecretSantaService

__all__ = [
    "Assignment",
    "NoValidAssignmentError",
    "Person",
    "RelationshipGraph",
    "SecretSantaService",
    "create_naive_assignment",
]
