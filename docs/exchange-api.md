# Private exchange API

The exchange API generates a draw once, stores it in the process, and exposes
each assignment through a separate private token.

## Create an exchange

`POST /api/exchanges`

The request accepts the existing draw shape:

```json
{
  "people": [
    {"id": "alice", "name": "Alice"},
    {"id": "bob", "name": "Bob"}
  ],
  "immediate_family": [],
  "history": []
}
```

The `201 Created` response contains organizer credentials and one private
reveal path per participant. It intentionally contains no recipients:

```json
{
  "exchange_id": "...",
  "organizer_token": "...",
  "organizer_path": "/api/exchanges/...",
  "participants": [
    {
      "person": {"id": "alice", "name": "Alice"},
      "reveal_token": "...",
      "reveal_path": "/api/reveals/..."
    }
  ]
}
```

## Reveal one assignment

`GET /api/reveals/{reveal_token}`

Returns only the giver and recipient associated with that token. Repeating the
request returns the stored result and never generates a new draw.

## Retrieve organizer links

`GET /api/exchanges/{exchange_id}?organizer_token={organizer_token}`

Returns the participant reveal links without exposing the completed assignment.
An unknown exchange or invalid organizer token returns `404`.

## Storage boundary

`ExchangeRepository` separates exchange behavior from storage.
`InMemoryExchangeRepository` is the take-home implementation:

- writes and indexes are protected by one lock;
- completed exchanges are immutable;
- concurrent families remain isolated; and
- data is lost on restart and is not shared across application processes.

A durable deployment can replace the repository with PostgreSQL without
changing the solver or HTTP contract.
