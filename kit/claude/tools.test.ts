import { expect, test } from "bun:test";
import type { ModelText } from "../core/model";
import type { Handlers } from "../core/operations";
import { Catalog } from "../core/model";
import { parseOperations } from "../core/operations";
import { contextBlock } from "./context";
import { callResult, dispatch, toolArguments, toolName, toolNames, toolSpecs } from "./tools";

const model = new Catalog<Record<string, undefined>>(
	[
		"look = Looks a word up.",
		"    .word = The word.",
		"note = Notes it down.",
		"found = Found it.",
		"gone = It is gone.",
		"hint = Use look.",
		"error-crashed = It broke: { $cause }",
		"error-arguments = Those arguments don't fit: { $problem }",
	].join("\n"),
);
const text = new Map<string, ModelText>(["look", "look.word", "note"].map(id => [id, model.text(id)]));
const SOURCE = JSON.stringify({
	operations: {
		look: {
			input: { type: "object", properties: { word: { type: "string" } }, required: ["word"] },
			output: { type: "object" },
			errors: ["gone"],
			tool: { name: "look", alwaysLoad: true },
		},
		note: { input: { type: "object" }, output: { type: "object" }, tool: { name: "note_down" } },
		sync: { input: { type: "object" }, output: { type: "object" } },
	},
});
const operations = parseOperations(SOURCE, text, {
	crashed: cause => model.textById("error-crashed", { cause }),
	badArguments: problem => model.textById("error-arguments", { problem }),
});

test("each tool's spec: its text, its described input, and in front only when it always loads", () => {
	expect(toolSpecs(operations)).toEqual([
		{
			name: "look",
			description: "Looks a word up.",
			inputSchema: {
				type: "object",
				properties: { word: { type: "string", description: "The word." } },
				required: ["word"],
			},
			isDeferred: false,
		},
		{
			name: "note_down",
			description: "Notes it down.",
			inputSchema: { type: "object", properties: {} },
			isDeferred: true,
		},
	]);
});

test("tools are named mcp__<plugin>__<name>", () => {
	expect(toolName("piebird-x", "note_down")).toBe("mcp__piebird-x__note_down");
	expect(toolNames("piebird-x", operations)).toEqual(["mcp__piebird-x__look", "mcp__piebird-x__note_down"]);
});

test("a call's arguments are the event's fields but Claude Code's own", () => {
	const event = {
		tool: "mcp__p__look",
		tool_use_id: "toolu_1",
		agentId: "a1",
		requestMeta: {},
		consent: "yes",
		word: "pie",
		n: 2,
	};
	expect(toolArguments(event)).toEqual({ word: "pie", n: 2 });
});

test("an answer is the result's text, a declared error a refusal with its text", () => {
	expect(callResult({ ok: true, text: model.text("found"), data: { word: "pie" } })).toEqual({ result: "Found it." });
	expect(callResult({ ok: false, error: "gone", text: model.text("gone") })).toEqual({ deny: "It is gone." });
});

test("dispatch runs the handler of the operation the full name names", async () => {
	const seen: unknown[] = [];
	const handlers: Handlers = {
		look: input => {
			seen.push(input);
			return Promise.resolve({ ok: true, text: model.text("found"), data: {} });
		},
		note: () => Promise.resolve({ ok: false, error: "gone", text: model.text("gone") }),
	};
	expect(await dispatch(operations, handlers, "mcp__piebird-x__look", { word: "pie" })).toEqual({
		result: "Found it.",
	});
	// A field set to null is a field left out, as a caller that sends every field means it.
	await dispatch(operations, handlers, "mcp__piebird-x__look", { word: "tart", style: null });
	expect(seen).toEqual([{ word: "pie" }, { word: "tart" }]);
	expect(await dispatch(operations, handlers, "mcp__piebird-x__note_down", {})).toEqual({ deny: "It is gone." });
});

test("dispatch answers a thrown handler, or a missing one, as an error in the catalog's words", async () => {
	const handlers: Handlers = { look: () => Promise.reject(new Error("the lookup broke")) };
	expect(await dispatch(operations, handlers, "mcp__p__look", {})).toEqual({ deny: "It broke: the lookup broke" });
	expect(await dispatch(operations, handlers, "mcp__p__note_down", {})).toEqual({
		deny: "It broke: no handler for operation note",
	});
});

test("dispatch leaves a tool that is none of the operations' to the caller", async () => {
	const handlers: Handlers = { sync: () => Promise.reject(new Error("not a tool")) };
	for (const tool of ["mcp__p__sync", "mcp__p__other", "look", "mcp__look", "WebSearch"]) {
		expect(await dispatch(operations, handlers, tool, {})).toBeUndefined();
	}
});

test("a context block carries the model's text under its name", () => {
	expect(contextBlock("piebird-x", model.text("hint"))).toEqual({ name: "piebird-x", text: "Use look." });
});
