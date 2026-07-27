import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const assetDirectory = resolve(root, "src/secret_santa/web_assets");
const outputDirectory = resolve(root, "dist/server");
const template = await readFile(
  resolve(root, "hosting/worker-template.js"),
  "utf8"
);

const assets = {};
for (const [route, filename, encoding] of [
  ["/", "index.html", "utf8"],
  ["/styles.css", "styles.css", "utf8"],
  ["/app.js", "app.js", "utf8"],
  ["/og.jpg", "og.jpg", "base64"],
]) {
  assets[route] = {
    encoding,
    content: await readFile(resolve(assetDirectory, filename), encoding),
  };
}

await rm(resolve(root, "dist"), { recursive: true, force: true });
await mkdir(outputDirectory, { recursive: true });
await writeFile(
  resolve(outputDirectory, "index.js"),
  template.replace("__MERRY_MATCH_ASSETS__", JSON.stringify(assets))
);

console.log("Built dist/server/index.js");
