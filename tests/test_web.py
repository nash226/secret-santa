import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from secret_santa import ExchangeService, InMemoryExchangeRepository
from secret_santa.web import SecretSantaHandler, SecretSantaHTTPServer


class WebServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        class IsolatedHandler(SecretSantaHandler):
            exchange_service = ExchangeService(
                InMemoryExchangeRepository()
            )

            def log_message(self, format: str, *args: object) -> None:
                pass

        cls.server = SecretSantaHTTPServer(
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
            ("/holiday-tags.jpg", "image/jpeg"),
            ("/reveal/example-token", "text/html"),
        ):
            with self.subTest(path=path):
                with urlopen(f"{self.base_url}{path}") as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn(
                        expected_type, response.headers["Content-Type"]
                    )
                    self.assertTrue(response.read())

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

        reveal_api_path = result["participants"][0]["reveal_api_path"]
        with urlopen(f"{self.base_url}{reveal_api_path}") as response:
            reveal = json.load(response)

        self.assertEqual(
            set(reveal), {"exchange_id", "giver", "recipient"}
        )
        self.assertNotEqual(reveal["giver"]["id"], reveal["recipient"]["id"])
        self.assertTrue(
            result["participants"][0]["reveal_path"].startswith("/reveal/")
        )

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
            f"{self.base_url}/api/exchanges",
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

    def test_missing_previous_exchange_returns_user_safe_error(self) -> None:
        request = Request(
            f"{self.base_url}/api/exchanges",
            data=json.dumps(
                {
                    "people": [
                        {"id": "alice", "name": "Alice"},
                        {"id": "bob", "name": "Bob"},
                    ],
                    "previous_exchange": {
                        "exchange_id": "missing",
                        "organizer_token": "missing",
                    },
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with self.assertRaises(HTTPError) as context:
            urlopen(request)

        try:
            self.assertEqual(context.exception.code, 422)
            result = json.load(context.exception)
            self.assertIn("no longer available", result["error"])
        finally:
            context.exception.close()

    def test_legacy_draw_endpoint_is_removed(self) -> None:
        request = Request(
            f"{self.base_url}/api/draw",
            data=b'{"people": []}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with self.assertRaises(HTTPError) as context:
            urlopen(request)
        context.exception.close()
        self.assertEqual(context.exception.code, 404)

    def test_previous_exchange_prevents_a_repeat_pairing(self) -> None:
        people = [
            {"id": "alice", "name": "Alice"},
            {"id": "bob", "name": "Bob"},
            {"id": "carol", "name": "Carol"},
            {"id": "dave", "name": "Dave"},
        ]

        def post_exchange(payload):
            request = Request(
                f"{self.base_url}/api/exchanges",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request) as response:
                return json.load(response)

        def recipients(exchange):
            pairs = {}
            for participant in exchange["participants"]:
                with urlopen(
                    f"{self.base_url}{participant['reveal_api_path']}"
                ) as response:
                    reveal = json.load(response)
                pairs[reveal["giver"]["id"]] = reveal["recipient"]["id"]
            return pairs

        first = post_exchange({"people": people})
        second = post_exchange(
            {
                "people": people,
                "previous_exchange": {
                    "exchange_id": first["exchange_id"],
                    "organizer_token": first["organizer_token"],
                },
            }
        )

        first_pairs = recipients(first)
        second_pairs = recipients(second)
        self.assertTrue(
            all(first_pairs[giver] != second_pairs[giver] for giver in first_pairs)
        )

    def test_reveal_is_stable_and_responses_are_not_cached(self) -> None:
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
            exchange = json.load(response)

        reveal_url = (
            f"{self.base_url}"
            f"{exchange['participants'][0]['reveal_api_path']}"
        )
        reveals = []
        for _ in range(2):
            with urlopen(reveal_url) as response:
                reveals.append(json.load(response))
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertIn(
                    "frame-ancestors 'none'",
                    response.headers["Content-Security-Policy"],
                )

        self.assertEqual(reveals[0], reveals[1])


if __name__ == "__main__":
    unittest.main()
