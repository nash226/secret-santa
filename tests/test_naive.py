import random
import unittest

from secret_santa import Person, create_naive_assignment


class NaiveAssignmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.people = [
            Person("alice", "Alice"),
            Person("bob", "Bob"),
            Person("carol", "Carol"),
            Person("dave", "Dave"),
        ]

    def test_assigns_each_person_exactly_once(self) -> None:
        assignment = create_naive_assignment(
            self.people, rng=random.Random(12)
        )

        self.assertEqual(set(assignment), {person.person_id for person in self.people})
        self.assertEqual(
            set(assignment.values()), {person.person_id for person in self.people}
        )
        self.assertTrue(
            all(giver != recipient for giver, recipient in assignment.items())
        )

    def test_requires_at_least_two_people(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least two"):
            create_naive_assignment([self.people[0]])

    def test_rejects_duplicate_ids(self) -> None:
        duplicate = Person("alice", "A different Alice")

        with self.assertRaisesRegex(ValueError, "unique"):
            create_naive_assignment([self.people[0], duplicate])

    def test_rejects_invalid_attempt_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 1"):
            create_naive_assignment(self.people, max_attempts=0)


if __name__ == "__main__":
    unittest.main()
