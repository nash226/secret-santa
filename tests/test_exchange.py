import random
import unittest
from concurrent.futures import ThreadPoolExecutor

from secret_santa import (
    ExchangeNotFoundError,
    ExchangeService,
    InMemoryExchangeRepository,
    NoValidAssignmentError,
    Person,
    RelationshipGraph,
)


class ExchangeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.people = [
            Person("alice", "Alice"),
            Person("bob", "Bob"),
            Person("carol", "Carol"),
            Person("dave", "Dave"),
        ]
        self.repository = InMemoryExchangeRepository()
        self.service = ExchangeService(self.repository)

    def test_generates_and_stores_one_immutable_exchange(self) -> None:
        history = [{"alice": "bob"}]
        exchange = self.service.create(
            self.people, history=history, rng=random.Random(4)
        )

        stored = self.repository.get(exchange.exchange_id)
        self.assertIs(stored, exchange)
        self.assertEqual(self.repository.count(), 1)
        with self.assertRaises(TypeError):
            exchange.assignment["alice"] = "bob"
        with self.assertRaises(TypeError):
            exchange.history[0]["alice"] = "carol"

    def test_each_private_token_reveals_exactly_one_pair(self) -> None:
        exchange = self.service.create(
            self.people, rng=random.Random(4)
        )

        reveals = [
            self.service.reveal(exchange.reveal_tokens[person.person_id])
            for person in self.people
        ]

        self.assertEqual(
            {reveal.giver.person_id for reveal in reveals},
            {person.person_id for person in self.people},
        )
        for reveal in reveals:
            self.assertEqual(
                reveal.recipient.person_id,
                exchange.assignment[reveal.giver.person_id],
            )

    def test_revealing_again_does_not_regenerate_the_draw(self) -> None:
        exchange = self.service.create(
            self.people, rng=random.Random(4)
        )
        token = exchange.reveal_tokens["alice"]

        first = self.service.reveal(token)
        second = self.service.reveal(token)

        self.assertEqual(first, second)
        self.assertIs(self.repository.get(exchange.exchange_id), exchange)
        self.assertEqual(self.repository.count(), 1)

    def test_invalid_private_credentials_do_not_disclose_exchange(self) -> None:
        exchange = self.service.create(self.people)

        with self.assertRaises(ExchangeNotFoundError):
            self.service.reveal("not-a-real-token")
        with self.assertRaises(ExchangeNotFoundError):
            self.service.get_for_organizer(
                exchange.exchange_id, "wrong-organizer-token"
            )

    def test_impossible_constraints_do_not_store_partial_exchange(self) -> None:
        relationships = RelationshipGraph.from_pairs([("alice", "bob")])

        with self.assertRaises(NoValidAssignmentError):
            self.service.create(
                self.people[:2], relationships=relationships
            )

        self.assertEqual(self.repository.count(), 0)

    def test_retries_if_generated_credentials_collide(self) -> None:
        credentials = iter(
            ["duplicate"] * 6
            + [
                "exchange",
                "organizer",
                "alice-token",
                "bob-token",
                "carol-token",
                "dave-token",
            ]
        )
        service = ExchangeService(
            self.repository, token_factory=lambda: next(credentials)
        )

        exchange = service.create(self.people)

        self.assertEqual(exchange.exchange_id, "exchange")
        self.assertEqual(self.repository.count(), 1)

    def test_concurrent_exchanges_remain_isolated(self) -> None:
        def create_exchange(index: int):
            people = [
                Person(f"{index}-{person.person_id}", person.name)
                for person in self.people
            ]
            return self.service.create(people)

        with ThreadPoolExecutor(max_workers=8) as executor:
            exchanges = list(executor.map(create_exchange, range(40)))

        self.assertEqual(self.repository.count(), 40)
        self.assertEqual(
            len({exchange.exchange_id for exchange in exchanges}), 40
        )
        all_tokens = [
            token
            for exchange in exchanges
            for token in exchange.reveal_tokens.values()
        ]
        self.assertEqual(len(all_tokens), len(set(all_tokens)))
        for index, exchange in enumerate(exchanges):
            prefix = f"{index}-"
            self.assertTrue(
                all(person.person_id.startswith(prefix) for person in exchange.people)
            )
            self.assertTrue(
                all(giver.startswith(prefix) for giver in exchange.assignment)
            )

    def test_concurrent_reveals_are_consistent(self) -> None:
        exchange = self.service.create(self.people)
        token = exchange.reveal_tokens["alice"]

        with ThreadPoolExecutor(max_workers=12) as executor:
            reveals = list(executor.map(self.service.reveal, [token] * 100))

        self.assertTrue(all(reveal == reveals[0] for reveal in reveals))
        self.assertEqual(self.repository.count(), 1)


if __name__ == "__main__":
    unittest.main()
