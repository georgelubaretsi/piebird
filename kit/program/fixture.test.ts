// A small plugin's program for the kit/program tests: its catalog, operations and handlers, and
// main.ts files that run it. Named .test.ts so the build leaves it out of the plugins' copies of
// kit/program; it holds no tests itself.
import type { Handlers, Outcome } from "../core/operations";
import type { Parts, Program } from "./cli";
import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import { Catalog } from "../core/model";
import { parseOperations } from "../core/operations";
import { addContext, allow, deny } from "./hook";
import { programPlace } from "./io";

type Messages = {
	instructions: { style: string };
	echo: undefined;
	echoed: { echoed: string };
	"echo.text": undefined;
	"echo.upper": undefined;
	refuse: undefined;
	"refuse-refused": undefined;
	boom: undefined;
	placed: undefined;
	"hook-denied": undefined;
	"hook-context": undefined;
	"error-crashed": { cause: string };
	"error-arguments": { problem: string };
};

export const catalog = new Catalog<Messages>(`
instructions = Use echo, in the { $style } style.
echoed = { $echoed }
echo = Echo text back, upper-cased if asked.
    .text = The text to echo.
    .upper = Whether to upper-case it.
refuse = Refuse, always.
refuse-refused = Refused: there is nothing to do.
boom = Throw.
placed = Where the program runs.
hook-denied = web.run doesn't search here; use echo.
hook-context = The echo tool is here.
error-crashed = It broke: { $cause }
error-arguments = Those arguments don't fit: { $problem }
`);

const EMPTY = { type: "object", properties: {}, additionalProperties: false };

export const OPERATIONS = {
	operations: {
		echo: {
			input: {
				type: "object",
				properties: { text: { type: "string" }, upper: { type: "boolean" } },
				required: ["text"],
				additionalProperties: false,
			},
			output: { type: "object", properties: { echoed: { type: "string" } }, required: ["echoed"] },
			tool: { name: "echo", readOnly: true, idempotent: true, openWorld: false, alwaysLoad: true },
		},
		refuse: {
			input: EMPTY,
			output: { type: "object" },
			errors: ["refused"],
			tool: { name: "refuse", destructive: true },
		},
		boom: { input: EMPTY, output: { type: "object" }, tool: { name: "boom" } },
		place: { input: EMPTY, output: { type: "object" } },
	},
};

const texts = new Map(
	(["echo", "echo.text", "echo.upper", "refuse", "boom"] as const).map(id => [id, catalog.text(id)]),
);
export const operations = parseOperations(JSON.stringify(OPERATIONS), texts, {
	crashed: cause => catalog.text("error-crashed", { cause }),
	badArguments: problem => catalog.text("error-arguments", { problem }),
});

async function echo(input: unknown): Promise<Outcome> {
	if (typeof input !== "object" || input === null || !("text" in input) || typeof input.text !== "string") {
		throw new TypeError("echo takes text");
	}
	// As the plugins' handlers do, a field that is there but of the wrong kind is refused.
	const upper = "upper" in input ? input.upper : false;
	if (typeof upper !== "boolean") throw new TypeError("upper takes true or false");
	const echoed = upper ? input.text.toUpperCase() : input.text;
	return { ok: true, text: catalog.text("echoed", { echoed }), data: { echoed } };
}

export const handlers: Handlers = {
	echo,
	refuse: async () => ({ ok: false, error: "refused", text: catalog.text("refuse-refused") }),
	boom: async () => {
		throw new Error("boom went the handler");
	},
	place: async () => ({ ok: true, text: catalog.text("placed"), data: programPlace() }),
};

export function parts(style = "plain"): Parts {
	return {
		name: "fixture",
		version: "1.2.3",
		operations,
		handlers,
		instructions: catalog.text("instructions", { style }),
		hook: async input => {
			if (input.hookEventName === "SessionStart") return addContext(catalog.text("hook-context"), "SessionStart");
			if (input.hookEventName === "PreToolUse" && input.toolName === "webrun")
				return deny(catalog.text("hook-denied"));
			return allow();
		},
	};
}

export const program: Program = { name: "fixture", parts: async () => parts() };

/** Writes `<dir>/main.ts`, a program's main.ts that runs the fixture; returns its path. */
export async function writeMain(dir: string): Promise<string> {
	const main = join(dir, "main.ts");
	const source = [
		`import { runProgram } from ${JSON.stringify(join(import.meta.dir, "cli.ts"))};`,
		`import { program } from ${JSON.stringify(join(import.meta.dir, "fixture.test.ts"))};`,
		"await runProgram(process.argv.slice(2), program);",
		"",
	].join("\n");
	await writeFile(main, source);
	return main;
}
