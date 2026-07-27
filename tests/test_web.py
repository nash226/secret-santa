import json
import random
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from secret_santa import ExchangeService, InMemoryExchangeRepository
from secret_santa.web import RequestError, SecretSantaHandler, create_draw


class CreateDrawTests(unittest.TestCase):
    def setUp(self) -> None:
        self.people = [
            {"id": "alice", "name": "Alice"},
            {"id": "bob", "name": "Bob"},
            {"id": "carol", "name": "Carol"},
            {"id": "dave", "name": "Dave"},
        ]

    def test_returns_display_ready_complete_draw(self) -> None:
        result = create_draw(
            {
                "people": self.people,
                "immediate_family": [
                    {"person_1": "alice", "person_2": "bob"}
                ],
            },
            rng=random.Random(4),
        )

        self.assertEqual(len(result["assignments"]), 4)
        self.assertEqual(set(result["history_entry"]), {
            "alice",
            "bob",
            "carol",
            "dave",
        })
        self.assertNotEqual(result["history_entry"]["alice"], "bob")
        self.assertNotEqual(result["history_entry"]["bob"], "alice")

    def test_rejects_invalid_browser_payload(self) -> None:
        with self.assertRaisesRegex(RequestError, "at least two"):
            create_draw({"people": "Alice"})

    def test_turns_impossible_draw_into_helpful_message(self) -> None:
        with self.assertRaisesRegex(RequestError, "no valid draw"):
            create_draw(
                {
                    "people": self.people[:2],
                    "immediate_family": [
                        {"person_1": "alice", "person_2": "bob"}
                    ],
                }
            )


class WebServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        class IsolatedHandler(SecretSantaHandler):
            exchange_service = ExchangeService(
                InMemoryExchangeRepository()
            )

            def log_message(self, format: str, *args: object) -> None:
                pass

        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), IsolatedHandler
        )
        cls.thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True
        )
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_serves_the_browser_application_and_assets(self) -> None:
        for path, expected_type in (
            ("/", "text/html"),
            ("/styles.css", "text/css"),
            ("/app.js", "text/javascript"),
            ("/og.jpg", "image/jpeg"),
        ):
            with self.subTest(path=path):
                with urlopen(f"{self.base_url}{path}") as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn(
                        expected_type, response.headers["Content-Type"]
                    )
                    self.assertTrue(response.read())

    def test_draw_endpoint_returns_json(self) -> None:
        request = Request(
            f"{self.base_url}/api/draw",
            data=json.dumps(
                {
                    "people": [
                        {"id": "alice", "name": "Alice"},
                        {"id": "bob", "name": "Bob"},
                    ]
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urlopen(request) as response:
            result = json.load(response)

        self.assertEqual(response.status, 200)
        self.assertEqual(
            result["history_entry"], {"alice": "bob", "bob": "alice"}
        )

    def test_exchange_endpoint_creates_private_reveal_links(self) -> None:
        request = Request(
            f"{self.base_url}/api/exchanges",
            data=json.dumps(
                {
                    "people": [
                        {"id": "alice", "name": "Alice"},
                        {"id": "bob", "name": "Bob"},
                    ]
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urlopen(request) as response:
            result = json.load(response)

        self.assertEqual(response.status, 201)
        self.assertIn("organizer_token", result)
        self.assertEqual(len(result["participants"]), 2)
        self.assertNotIn("recipient", result["participants"][0])

        reveal_path = result["participants"][0]["reveal_path"]
        with urlopen(f"{self.base_url}{reveal_path}") as response:
            reveal = json.load(response)

        self.assertEqual(
            set(reveal), {"exchange_id", "giver", "recipient"}
        )
        self.assertNotEqual(reveal["giver"]["id"], reveal["recipient"]["id"])

    def test_organizer_token_controls_access_to_reveal_links(self) -> None:
        request = Request(
            f"{self.base_url}/api/exchanges",
            data=json.dumps(
                {
                    "people": [
                        {"id": "alice", "name": "Alice"},
                        {"id": "bob", "name": "Bob"},
                    ]
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            created = json.load(response)

        organizer_url = (
            f"{self.base_url}{created['organizer_path']}"
            f"?organizer_token={created['organizer_token']}"
        )
        with urlopen(organizer_url) as response:
            organizer_view = json.load(response)
        self.assertEqual(len(organizer_view["participants"]), 2)
        self.assertNotIn("organizer_token", organizer_view)

        with self.assertRaises(HTTPError) as context:
            urlopen(
                f"{self.base_url}{created['organizer_path']}"
                "?organizer_token=wrong"
            )
        context.exception.close()
        self.assertEqual(context.exception.code, 404)

    def test_concurrent_exchange_requests_remain_isolated(self) -> None:
        def create_exchange(index: int):
            request = Request(
                f"{self.base_url}/api/exchanges",
                data=json.dumps(
                    {
                        "people": [
                            {
                                "id": f"{index}-alice",
                                "name": "Alice",
                            },
                            {
                                "id": f"{index}-bob",
                                "name": "Bob",
                            },
                        ]
                    }
                ).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request) as response:
                return json.load(response)

        with ThreadPoolExecutor(max_workers=8) as executor:
            exchanges = list(executor.map(create_exchange, range(24)))

        self.assertEqual(
            len({exchange["exchange_id"] for exchange in exchanges}), 24
        )
        for index, exchange in enumerate(exchanges):
            self.assertTrue(
                all(
                    participant["person"]["id"].startswith(f"{index}-")
                    for participant in exchange["participants"]
                )
            )

    def test_invalid_draw_returns_user_safe_error(self) -> None:
        request = Request(
            f"{self.base_url}/api/draw",
            data=b'{"people": []}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with self.assertRaises(HTTPError) as context:
            urlopen(request)

        try:
            self.assertEqual(context.exception.code, 422)
            result = json.load(context.exception)
            self.assertIn("at least two", result["error"])
        finally:
            context.exception.close()


if __name__ == "__main__":
    unittest.main()
