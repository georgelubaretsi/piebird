import { describe, expect, test } from "bun:test";
import { Catalog, type ModelText } from "./model";
import { parseOperations, withoutNulls } from "./operations";

const model = new Catalog<Record<string, undefined>>("find = Finds.\n    .query = What.\nlist = Lists.\n");

const SOURCE = JSON.stringify({
	operations: {
		status: { input: { type: "object" }, output: {}, errors: ["signed-out"], vault: true },
		list: { input: { type: "object" }, output: {}, tool: { name: "demo_list", readOnly: true, alwaysLoad: false } },
		find: {
			input: { type: "object", properties: { query: { type: "string" } }, required: ["query"] },
			output: { type: "object" },
			tool: { name: "demo_find" },
		},
	},
});

function text(ids: string[]): Map<string, ModelText> {
	return new Map(ids.map(id => [id, model.text(id)]));
}

describe("parseOperations", () => {
	const ops = parseOperations(SOURCE, text(["find", "find.query", "list"]));

	test("tools in declaration order, their arguments described from the text", () => {
		expect(ops.tools.map(t => t.tool.name)).toEqual(["demo_list", "demo_find"]);
		const find = ops.tools[1].tool;
		expect(find.description.text).toBe("Finds.");
		expect(find.inputSchema).toEqual({
			type: "object",
			properties: { query: { type: "string", description: "What." } },
			required: ["query"],
		});
		expect(ops.tools[0].tool.hints).toEqual({ readOnly: true, alwaysLoad: false });
	});

	test("an operation that is no tool is there by id", () => {
		expect(ops.byId.get("status")).toEqual({
			id: "status",
			input: { type: "object" },
			output: {},
			errors: ["signed-out"],
			vault: true,
		});
	});

	test("missing text throws, naming the id", () => {
		expect(() => parseOperations(SOURCE, text(["find", "list"]))).toThrow("model.ftl: no find.query");
		expect(() => parseOperations(SOURCE, text(["find.query", "list"]))).toThrow("model.ftl: no find");
	});
});

test("withoutNulls leaves out the fields set to null and keeps every other value as sent", () => {
	const kept = { query: "bun", limit: 0, json: false, note: "", list: [null], nested: { a: null } };
	expect(withoutNulls({ ...kept, time: null, format: null })).toEqual(kept);
	for (const input of [null, "x", 3, [null], {}]) expect(withoutNulls(input)).toEqual(input);
});
