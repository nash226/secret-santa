import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

const worker = (
  await import(`${pathToFileURL(resolve("dist/server/index.js"))}?test=1`)
).default;

const home = await worker.fetch(new Request("https://example.test/"));
if (home.status !== 200 || !(await home.text()).includes("Merry Match")) {
  throw new Error("Hosted worker did not serve the application.");
}

const draw = await worker.fetch(
  new Request("https://example.test/api/draw", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      people: [
        { id: "alice", name: "Alice" },
        { id: "bob", name: "Bob" },
      ],
    }),
  })
);
const result = await draw.json();
if (
  draw.status !== 200 ||
  result.history_entry.alice !== "bob" ||
  result.history_entry.bob !== "alice"
) {
  throw new Error("Hosted worker did not create a valid draw.");
}

console.log("Hosted worker verified");
