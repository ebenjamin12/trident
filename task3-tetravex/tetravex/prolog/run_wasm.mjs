/**
 * Fallback runner for tetravex.pl using the swipl-wasm build of SWI-Prolog.
 *
 * The Python driver prefers a native `swipl` binary; this exists so the
 * project still runs end to end on a machine where SWI-Prolog is not
 * installed. The Prolog source is identical in both paths -- only the way the
 * goal is invoked differs.
 *
 * Usage:  node run_wasm.mjs <facts.pl> <one|unique> <tetravex.pl>
 * Writes a single line of JSON to stdout.
 */
import { readFileSync } from "node:fs";
import SWIPL from "swipl-wasm";

async function main() {
  const [factsPath, mode, modelPath] = process.argv.slice(2);
  if (!factsPath || !mode || !modelPath) {
    process.stderr.write("usage: run_wasm.mjs <facts.pl> <one|unique> <tetravex.pl>\n");
    process.exit(2);
  }

  const swipl = await SWIPL({ arguments: ["-q"] });
  const prolog = swipl.prolog;

  // Stage both source files inside the WASM filesystem.
  swipl.FS.writeFile("/tetravex.pl", readFileSync(modelPath, "utf8"));
  swipl.FS.writeFile("/facts.pl", readFileSync(factsPath, "utf8"));

  const consulted = prolog.query("consult('/tetravex.pl').").once();
  if (!consulted || consulted.success === false) {
    process.stderr.write("failed to consult tetravex.pl\n");
    process.exit(3);
  }

  const answer = prolog.query(`run('/facts.pl', ${mode}, Json).`).once();
  if (!answer || answer.success === false || answer.Json === undefined) {
    process.stderr.write(`prolog goal failed: ${JSON.stringify(answer)}\n`);
    process.exit(4);
  }

  // swipl-wasm hands atoms back either as plain strings or as {$t:'s',v:...}.
  const json =
    typeof answer.Json === "string" ? answer.Json : String(answer.Json.v ?? answer.Json);
  process.stdout.write(json + "\n");
}

main().catch((err) => {
  process.stderr.write(String(err && err.stack ? err.stack : err) + "\n");
  process.exit(1);
});
