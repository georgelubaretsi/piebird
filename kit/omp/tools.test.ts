// Registering a plugin's operations as omp tools: the definitions omp gets, the results the model
// sees for each kind of outcome, and refusing an operation nobody performs. omp is a fake `pi`.
import { describe, expect, test } from "bun:test";
import { Catalog, type ModelText } from "../core/model";
import { type Handlers, parseOperations } from "../core/operations";
import { type OmpTool, registerOperations } from "./tools";

const catalog = new Catalog<Record<string, undefined>>(`
search = Search the web.
    .query = What to search for.
fetch = Fetch a page.
    .url = The page's address.
rotate = Rotate the key.
run = Run code.
no-results = Nothing matched.
found = Found it.
error-crashed = It broke: { $cause }
error-arguments = Those arguments don't fit: { $problem }
`);

const text = (id: string): ModelText => catalog.text(id);

const operations = parseOperations(
	JSON.stringify({
		operations: {
			search: {
				input: { type: "object", properties: { query: { type: "string" } }, required: ["query"] },
				output: { type: "object" },
				errors: ["no-results"],
				tool: { name: "web_search_kagi", readOnly: true, alwaysLoad: true },
			},
			fetch: {
				input: { type: "object", properties: { url: { type: "string" } } },
				output: { type: "object" },
				tool: { name: "fetch_page" },
			},
			rotate: { input: { type: "object" }, output: { type: "object" }, vault: true },
			run: { input: { type: "object" }, output: { type: "object" }, tool: { name: "run_code", runsCode: true } },
		},
	}),
	new Map(["search", "search.query", "fetch", "fetch.url", "rotate", "run"].map(id => [id, text(id)])),
	{
		crashed: cause => catalog.textById("error-crashed", { cause }),
		badArguments: problem => catalog.textById("error-arguments", { problem }),
	},
);

/** The context omp passes a tool call; here only the session's folder. */
interface Ctx {
	folder: string;
}
type Tool = OmpTool<Ctx>;

/** A fake omp that keeps the tools registered with it, by name. */
function fakePi() {
	const tools = new Map<string, Tool>();
	return { tools, registerTool: (def: Tool) => void tools.set(def.name, def) };
}

function registered(handlers: Handlers): Map<string, Tool> {
	const pi = fakePi();
	registerOperations(pi, operations, () => handlers);
	return pi.tools;
}

function tool(tools: Map<string, Tool>, name: string): Tool {
	const found = tools.get(name);
	if (found === undefined) throw new Error(`no tool ${name}`);
	return found;
}

/** Calls the tool as omp does, from a session whose folder is `folder`. */
function call(t: Tool, params: unknown, folder = "/sessions/a") {
	return t.execute("call-1", params, undefined, undefined, { folder });
}

const idle: Handlers = {
	search: async () => ({ ok: true, text: text("found"), data: null }),
	fetch: async () => ({ ok: true, text: text("found"), data: null }),
	run: async () => ({ ok: true, text: text("found"), data: null }),
};

describe("registerOperations", () => {
	test("registers each operation with a tool as an omp tool, in its text and with its hints", () => {
		const tools = registered(idle);
		expect([...tools.keys()]).toEqual(["web_search_kagi", "fetch_page", "run_code"]);
		const search = tool(tools, "web_search_kagi");
		expect({ ...search, execute: undefined }).toEqual({
			name: "web_search_kagi",
			label: "web_search_kagi",
			description: "Search the web.",
			parameters: {
				type: "object",
				properties: { query: { type: "string", description: "What to search for." } },
				required: ["query"],
			},
			loadMode: "essential",
			approval: "read",
			strict: false,
			execute: undefined,
		});
		const fetch = tool(tools, "fetch_page");
		expect(fetch.loadMode).toBe("discoverable");
		expect(fetch.approval).toBe("write");
	});

	test("passes the call's arguments to the handler and returns its answer as text and data", async () => {
		const seen: unknown[] = [];
		const tools = registered({
			...idle,
			search: async input => {
				seen.push(input);
				return { ok: true, text: text("found"), data: { hits: 3 } };
			},
		});
		const result = await call(tool(tools, "web_search_kagi"), { query: "bun" });
		expect(seen).toEqual([{ query: "bun" }]);
		expect(result).toEqual({ content: [{ type: "text", text: "Found it." }], details: { hits: 3 } });
	});

	test("a field set to null reaches the handler as left out, as a caller that sends every field means it", async () => {
		const seen: unknown[] = [];
		const tools = registered({
			...idle,
			search: async input => {
				seen.push(input);
				return { ok: true, text: text("found"), data: null };
			},
		});
		await call(tool(tools, "web_search_kagi"), { query: "bun", limit: null });
		expect(seen).toEqual([{ query: "bun" }]);
	});

	test("a tool that runs the model's code is approved as code execution", () => {
		expect(tool(registered(idle), "run_code").approval).toBe("exec");
	});

	test("a declared error is a tool error in its text, with its id in details", async () => {
		const tools = registered({
			...idle,
			search: async () => ({ ok: false, error: "no-results", text: text("no-results") }),
		});
		expect(await call(tool(tools, "web_search_kagi"), { query: "zzz" })).toEqual({
			content: [{ type: "text", text: "Nothing matched." }],
			details: { error: "no-results" },
			isError: true,
		});
	});

	test("a handler that throws gives a tool error: the catalog's error-crashed with its message", async () => {
		const tools = registered({
			...idle,
			fetch: async () => {
				throw new Error("connection refused");
			},
		});
		expect(await call(tool(tools, "fetch_page"), { url: "https://x" })).toEqual({
			content: [{ type: "text", text: "It broke: connection refused" }],
			isError: true,
		});
	});

	test("makes each call's handlers from the calling session's context", async () => {
		const pi = fakePi();
		registerOperations(pi, operations, (ctx: Ctx) => ({
			...idle,
			search: async () => ({ ok: true, text: text("found"), data: { folder: ctx.folder } }),
		}));
		const search = tool(pi.tools, "web_search_kagi");
		expect((await call(search, { query: "a" }, "/sessions/a")).details).toEqual({ folder: "/sessions/a" });
		expect((await call(search, { query: "b" }, "/sessions/b")).details).toEqual({ folder: "/sessions/b" });
	});

	test("a call to an operation without a handler is a tool error naming it, in the catalog's words", async () => {
		const { fetch: _fetch, ...withoutFetch } = idle;
		expect(await call(tool(registered(withoutFetch), "fetch_page"), { url: "https://x" })).toEqual({
			content: [{ type: "text", text: "It broke: no handler for operation fetch (tool fetch_page)" }],
			isError: true,
		});
	});
});
