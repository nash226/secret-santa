const ASSETS = __MERRY_MATCH_ASSETS__;

const TYPES = {
  "/": "text/html; charset=utf-8",
  "/styles.css": "text/css; charset=utf-8",
  "/app.js": "text/javascript; charset=utf-8",
  "/og.jpg": "image/jpeg",
};

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

function shuffle(values) {
  for (let index = values.length - 1; index > 0; index -= 1) {
    const other = Math.floor(Math.random() * (index + 1));
    [values[index], values[other]] = [values[other], values[index]];
  }
}

function validatePayload(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("The request must be a JSON object.");
  }
  if (!Array.isArray(payload.people) || payload.people.length < 2) {
    throw new Error("Add at least two people before drawing names.");
  }

  const people = payload.people.map((person) => {
    if (
      !person ||
      typeof person.id !== "string" ||
      !person.id.trim() ||
      typeof person.name !== "string" ||
      !person.name.trim()
    ) {
      throw new Error("Each person needs a valid ID and name.");
    }
    return { id: person.id, name: person.name };
  });
  const ids = new Set(people.map((person) => person.id));
  if (ids.size !== people.length) {
    throw new Error("Person IDs must be unique.");
  }

  const relationships = payload.immediate_family ?? [];
  if (!Array.isArray(relationships)) {
    throw new Error("Immediate-family connections must be a list.");
  }
  for (const pair of relationships) {
    if (
      !pair ||
      typeof pair.person_1 !== "string" ||
      typeof pair.person_2 !== "string" ||
      !ids.has(pair.person_1) ||
      !ids.has(pair.person_2)
    ) {
      throw new Error("A family connection references an unknown person.");
    }
    if (pair.person_1 === pair.person_2) {
      throw new Error("A person cannot be their own relative.");
    }
  }

  const history = payload.history ?? [];
  if (
    !Array.isArray(history) ||
    history.some(
      (assignment) =>
        !assignment ||
        typeof assignment !== "object" ||
        Array.isArray(assignment) ||
        Object.entries(assignment).some(
          ([giver, recipient]) =>
            typeof giver !== "string" || typeof recipient !== "string"
        )
    )
  ) {
    throw new Error("Each previous draw must map person IDs.");
  }

  return { people, relationships, history };
}

function createDraw(payload) {
  const { people, relationships, history } = validatePayload(payload);
  const personIds = people.map((person) => person.id);
  const familyPairs = new Set();
  for (const pair of relationships) {
    familyPairs.add(`${pair.person_1}\0${pair.person_2}`);
    familyPairs.add(`${pair.person_2}\0${pair.person_1}`);
  }
  const recentPairs = new Set(
    history
      .slice(-2)
      .flatMap((assignment) =>
        Object.entries(assignment).map(
          ([giver, recipient]) => `${giver}\0${recipient}`
        )
      )
  );

  const candidates = new Map();
  for (const giver of personIds) {
    const choices = personIds.filter(
      (recipient) =>
        giver !== recipient &&
        !familyPairs.has(`${giver}\0${recipient}`) &&
        !recentPairs.has(`${giver}\0${recipient}`)
    );
    if (!choices.length) {
      throw new Error(
        "These family and history rules leave no valid draw. Try adding more people or removing a family connection."
      );
    }
    shuffle(choices);
    candidates.set(giver, choices);
  }

  const giverOrder = [...personIds];
  shuffle(giverOrder);
  giverOrder.sort(
    (first, second) =>
      candidates.get(first).length - candidates.get(second).length
  );

  const recipientToGiver = new Map();
  function findMatch(giver, visited) {
    for (const recipient of candidates.get(giver)) {
      if (visited.has(recipient)) continue;
      visited.add(recipient);
      const currentGiver = recipientToGiver.get(recipient);
      if (
        currentGiver === undefined ||
        findMatch(currentGiver, visited)
      ) {
        recipientToGiver.set(recipient, giver);
        return true;
      }
    }
    return false;
  }

  for (const giver of giverOrder) {
    if (!findMatch(giver, new Set())) {
      throw new Error(
        "These family and history rules leave no valid draw. Try adding more people or removing a family connection."
      );
    }
  }

  const assignment = Object.fromEntries(
    [...recipientToGiver].map(([recipient, giver]) => [giver, recipient])
  );
  const peopleById = new Map(people.map((person) => [person.id, person]));
  return {
    assignments: people.map((giver) => ({
      giver,
      recipient: peopleById.get(assignment[giver.id]),
    })),
    history_entry: assignment,
  };
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/health") {
      return jsonResponse({ status: "ok" });
    }

    if (request.method === "POST" && url.pathname === "/api/draw") {
      try {
        const payload = await request.json();
        return jsonResponse(createDraw(payload));
      } catch (error) {
        return jsonResponse(
          {
            error:
              error instanceof Error
                ? error.message
                : "The draw could not be completed.",
          },
          422
        );
      }
    }

    if (request.method !== "GET" || !(url.pathname in ASSETS)) {
      return jsonResponse({ error: "Not found." }, 404);
    }

    const asset = ASSETS[url.pathname];
    const textContent =
      url.pathname === "/"
        ? asset.content.replace(
            'content="/og.jpg"',
            `content="${url.origin}/og.jpg"`
          )
        : asset.content;
    const body = asset.encoding === "base64"
      ? Uint8Array.from(atob(asset.content), (character) =>
          character.charCodeAt(0)
        )
      : textContent;
    return new Response(body, {
      headers: {
        "Content-Type": TYPES[url.pathname],
        "Cache-Control":
          url.pathname === "/"
            ? "no-store"
            : "public, max-age=3600",
        "X-Content-Type-Options": "nosniff",
      },
    });
  },
};
