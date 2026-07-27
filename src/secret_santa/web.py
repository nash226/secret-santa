"""Small HTTP application that exposes the Secret Santa solver."""

from __future__ import annotations

import argparse
import json
import random
from collections.abc import Mapping, Sequence
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from typing import Any
from urllib.parse import parse_qs, urlparse

from .exchange import (
    Exchange,
    ExchangeNotFoundError,
    ExchangeService,
    InMemoryExchangeRepository,
)
from .models import Person, RelationshipGraph
from .solver import NoValidAssignmentError

MAX_REQUEST_BYTES = 1_000_000
ASSET_TYPES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/og.jpg": ("og.jpg", "image/jpeg"),
    "/holiday-tags.jpg": ("holiday-tags.jpg", "image/jpeg"),
}
EXCHANGE_REPOSITORY = InMemoryExchangeRepository()
EXCHANGE_SERVICE = ExchangeService(EXCHANGE_REPOSITORY)


class RequestError(ValueError):
    """An input error that is safe to show to the user."""


class SecretSantaHTTPServer(ThreadingHTTPServer):
    """Threaded server with enough backlog for short concurrent bursts."""

    daemon_threads = True
    request_queue_size = 128


def create_exchange(
    payload: Any,
    *,
    service: ExchangeService = EXCHANGE_SERVICE,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Validate, generate, and store one immutable exchange."""

    people, relationships, history = _parse_draw_input(payload)
    previous_exchange = payload.get("previous_exchange")
    if previous_exchange is not None:
        if not isinstance(previous_exchange, dict):
            raise RequestError("The previous exchange reference is invalid.")
        exchange_id = previous_exchange.get("exchange_id")
        organizer_token = previous_exchange.get("organizer_token")
        if not isinstance(exchange_id, str) or not isinstance(
            organizer_token, str
        ):
            raise RequestError("The previous exchange reference is invalid.")
        try:
            previous = service.get_for_organizer(
                exchange_id, organizer_token
            )
        except ExchangeNotFoundError as error:
            raise RequestError(
                "The saved previous draw is no longer available. "
                "Forget its history to begin a fresh three-year window."
            ) from error
        history = (*previous.history, previous.assignment)[-2:]

    try:
        exchange = service.create(
            people,
            history=history,
            relationships=relationships,
            rng=rng,
        )
    except NoValidAssignmentError as error:
        raise RequestError(
            "These family and history rules leave no valid draw. "
            "Try adding more people or removing a family connection."
        ) from error
    except ValueError as error:
        raise RequestError(str(error)) from error
    return _exchange_json(exchange, include_organizer_token=True)


def _parse_draw_input(
    payload: Any,
) -> tuple[
    list[Person],
    RelationshipGraph,
    Sequence[Mapping[str, str]],
]:
    if not isinstance(payload, dict):
        raise RequestError("The request must be a JSON object.")

    people_data = payload.get("people")
    if not isinstance(people_data, list):
        raise RequestError("Add at least two people before drawing names.")

    return (
        [_parse_person(item) for item in people_data],
        _parse_relationships(payload.get("immediate_family", [])),
        _parse_history(payload.get("history", [])),
    )


def _parse_person(item: Any) -> Person:
    if not isinstance(item, dict):
        raise RequestError("Each person needs an ID and name.")
    person_id = item.get("id")
    name = item.get("name")
    if not isinstance(person_id, str) or not isinstance(name, str):
        raise RequestError("Each person needs a valid ID and name.")
    try:
        return Person(person_id=person_id, name=name)
    except ValueError as error:
        raise RequestError(str(error)) from error


def _parse_relationships(value: Any) -> RelationshipGraph:
    if not isinstance(value, list):
        raise RequestError("Immediate-family connections must be a list.")

    pairs: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise RequestError("Each family connection must contain two people.")
        first_id = item.get("person_1")
        second_id = item.get("person_2")
        if not isinstance(first_id, str) or not isinstance(second_id, str):
            raise RequestError("Each family connection must contain two people.")
        pairs.append((first_id, second_id))

    try:
        return RelationshipGraph.from_pairs(pairs)
    except ValueError as error:
        raise RequestError(str(error)) from error


def _parse_history(value: Any) -> Sequence[Mapping[str, str]]:
    if not isinstance(value, list):
        raise RequestError("Draw history must be a list.")
    for assignment in value:
        if not isinstance(assignment, dict) or not all(
            isinstance(giver, str) and isinstance(recipient, str)
            for giver, recipient in assignment.items()
        ):
            raise RequestError("Each previous draw must map person IDs.")
    return value


def _person_json(person: Person) -> dict[str, str]:
    return {"id": person.person_id, "name": person.name}


def _exchange_json(
    exchange: Exchange, *, include_organizer_token: bool
) -> dict[str, Any]:
    participants = [
        {
            "person": _person_json(person),
            "reveal_token": exchange.reveal_tokens[person.person_id],
            "reveal_path": (
                f"/reveal/{exchange.reveal_tokens[person.person_id]}"
            ),
            "reveal_api_path": (
                f"/api/reveals/{exchange.reveal_tokens[person.person_id]}"
            ),
        }
        for person in exchange.people
    ]
    result: dict[str, Any] = {
        "exchange_id": exchange.exchange_id,
        "organizer_path": f"/api/exchanges/{exchange.exchange_id}",
        "participants": participants,
    }
    if include_organizer_token:
        result["organizer_token"] = exchange.organizer_token
    return result


class SecretSantaHandler(BaseHTTPRequestHandler):
    """Serve the browser application and its draw endpoint."""

    server_version = "SecretSanta/1.0"
    exchange_service = EXCHANGE_SERVICE

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        if path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return

        path_parts = path.strip("/").split("/")
        if len(path_parts) == 2 and path_parts[0] == "reveal":
            content = (
                files("secret_santa.web_assets")
                .joinpath("index.html")
                .read_bytes()
            )
            self._send(HTTPStatus.OK, content, "text/html; charset=utf-8")
            return

        try:
            if len(path_parts) == 3 and path_parts[:2] == ["api", "reveals"]:
                reveal = self.exchange_service.reveal(path_parts[2])
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "exchange_id": reveal.exchange_id,
                        "giver": _person_json(reveal.giver),
                        "recipient": _person_json(reveal.recipient),
                    },
                )
                return

            if len(path_parts) == 3 and path_parts[:2] == ["api", "exchanges"]:
                organizer_token = parse_qs(parsed_url.query).get(
                    "organizer_token", [""]
                )[0]
                exchange = self.exchange_service.get_for_organizer(
                    path_parts[2], organizer_token
                )
                self._send_json(
                    HTTPStatus.OK,
                    _exchange_json(
                        exchange, include_organizer_token=False
                    ),
                )
                return
        except ExchangeNotFoundError as error:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
            return

        asset = ASSET_TYPES.get(path)
        if asset is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return

        filename, content_type = asset
        content = files("secret_santa.web_assets").joinpath(filename).read_bytes()
        self._send(HTTPStatus.OK, content, content_type)

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        path = urlparse(self.path).path
        if path != "/api/exchanges":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length < 0:
                raise RequestError("The request length is invalid.")
            if content_length > MAX_REQUEST_BYTES:
                raise RequestError("The family list is too large to process.")
            payload = json.loads(self.rfile.read(content_length))
            result = create_exchange(payload, service=self.exchange_service)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(
                HTTPStatus.BAD_REQUEST, {"error": "The request was not valid JSON."}
            )
        except RequestError as error:
            self._send_json(
                HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)}
            )
        else:
            self._send_json(HTTPStatus.CREATED, result)

    def _send_json(self, status: HTTPStatus, payload: Mapping[str, Any]) -> None:
        content = json.dumps(payload).encode()
        self._send(status, content, "application/json; charset=utf-8")

    def _send(
        self, status: HTTPStatus, content: bytes, content_type: str
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; "
            "style-src 'self'; script-src 'self'; connect-src 'self'; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(content)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Secret Santa web app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    server = SecretSantaHTTPServer((args.host, args.port), SecretSantaHandler)
    print(f"Secret Santa is ready at http://{args.host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
