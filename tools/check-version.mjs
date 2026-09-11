import { readFileSync } from "node:fs";

const releaseVersion = readFileSync("VERSION", "utf8").trim();
const pythonVersion = releaseVersion.replace(/-beta\.(\d+)$/, "b$1");
const packageFiles = ["package.json", "apps/web/package.json", "apps/bot/package.json", "packages/ui/package.json"];
const mismatches = [];

for (const file of packageFiles) {
  if (JSON.parse(readFileSync(file, "utf8")).version !== releaseVersion)
    mismatches.push(file);
}

const expected = [
  ["apps/api/pyproject.toml", `version = \"${pythonVersion}\"`],
  ["apps/api/uv.lock", `version = \"${pythonVersion}\"`],
  ["apps/api/app/config.py", `default=\"${releaseVersion}\"`],
  ["apps/web/lib/version.ts", `APP_VERSION = \"${releaseVersion}\"`],
];

for (const [file, value] of expected) {
  if (!readFileSync(file, "utf8").includes(value)) mismatches.push(file);
}

if (mismatches.length) {
  console.error(`Version ${releaseVersion} is not synchronized: ${mismatches.join(", ")}`);
  process.exit(1);
}

console.log(`Version metadata is synchronized at ${releaseVersion}.`);
