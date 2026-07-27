import random
import unittest

from secret_santa import (
    NoValidAssignmentError,
    Person,
    RelationshipGraph,
    SecretSantaService,
)


class SecretSantaServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.people = [
            Person("alice", "Alice"),
            Person("bob", "Bob"),
            Person("carol", "Carol"),
            Person("dave", "Dave"),
            Person("erin", "Erin"),
            Person("frank", "Frank"),
        ]
        self.service = SecretSantaService()

    def test_creates_complete_assignment(self) -> None:
        assignment = self.service.create_assignment(
            self.people, rng=random.Random(4)
        )

        expected_ids = {person.person_id for person in self.people}
        self.assertEqual(set(assignment), expected_ids)
        self.assertEqual(set(assignment.values()), expected_ids)
        self.assertTrue(
            all(giver != recipient for giver, recipient in assignment.items())
        )

    def test_excludes_pairs_from_prior_two_years(self) -> None:
        history = [
            {
                "alice": "bob",
                "bob": "carol",
                "carol": "dave",
                "dave": "erin",
                "erin": "frank",
                "frank": "alice",
            },
            {
                "alice": "carol",
                "bob": "dave",
                "carol": "erin",
                "dave": "frank",
                "erin": "alice",
                "frank": "bob",
            },
        ]

        assignment = self.service.create_assignment(
            self.people, history=history, rng=random.Random(1)
        )

        recent_pairs = {
            pair for year in history for pair in year.items()
        }
        self.assertTrue(
            all(pair not in recent_pairs for pair in assignment.items())
        )

    def test_history_older_than_window_can_repeat(self) -> None:
        only_possible_draw = [
            Person("alice", "Alice"),
            Person("bob", "Bob"),
        ]

        assignment = self.service.create_assignment(
            only_possible_draw,
            history=[
                {"alice": "bob", "bob": "alice"},
                {},
                {},
            ],
            rng=random.Random(1),
        )

        self.assertEqual(assignment, {"alice": "bob", "bob": "alice"})

    def test_excludes_immediate_family(self) -> None:
        relationships = RelationshipGraph.from_pairs(
            [
                ("alice", "bob"),  # spouses
                ("carol", "dave"),  # parent and child
                ("erin", "frank"),  # parent and child
            ]
        )

        assignment = self.service.create_assignment(
            self.people,
            relationships=relationships,
            rng=random.Random(8),
        )

        self.assertTrue(
            all(
                recipient not in relationships.family_of(giver)
                for giver, recipient in assignment.items()
            )
        )

    def test_reports_when_constraints_are_impossible(self) -> None:
        two_people = self.people[:2]
        relationships = RelationshipGraph.from_pairs([("alice", "bob")])

        with self.assertRaises(NoValidAssignmentError):
            self.service.create_assignment(
                two_people, relationships=relationships
            )

    def test_rejects_relationships_with_unknown_people(self) -> None:
        relationships = RelationshipGraph.from_pairs([("alice", "unknown")])

        with self.assertRaisesRegex(ValueError, "unknown IDs"):
            self.service.create_assignment(
                self.people, relationships=relationships
            )

    def test_relationships_are_symmetric(self) -> None:
        relationships = RelationshipGraph.from_pairs([("alice", "bob")])

        self.assertIn("bob", relationships.family_of("alice"))
        self.assertIn("alice", relationships.family_of("bob"))

    def test_service_does_not_retain_draw_state(self) -> None:
        first = self.service.create_assignment(
            self.people, rng=random.Random(2)
        )
        second = self.service.create_assignment(
            self.people, rng=random.Random(2)
        )

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
