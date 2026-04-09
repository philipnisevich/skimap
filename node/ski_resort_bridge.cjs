#!/usr/bin/env node
/**
 * JSON bridge for ski-resort-status (https://github.com/marcushyett/ski-lift-status).
 * Used by ski_trails.py — do not run interactively except for debugging.
 */
const { fetchResortStatus, getSupportedResorts } = require("ski-resort-status");

async function main() {
  const args = process.argv.slice(2);
  if (args[0] === "--list" || args[0] === "-l") {
    console.log(
      JSON.stringify({ ok: true, resorts: getSupportedResorts() }),
    );
    return;
  }
  const id = args[0];
  if (!id) {
    console.log(
      JSON.stringify({
        ok: false,
        error: "Missing resort id. Use --list for supported resorts.",
      }),
    );
    process.exit(1);
    return;
  }
  try {
    const data = await fetchResortStatus(id);
    console.log(JSON.stringify({ ok: true, data }));
  } catch (e) {
    const msg = e && e.message ? e.message : String(e);
    console.log(JSON.stringify({ ok: false, error: msg }));
    process.exit(1);
  }
}

main();
