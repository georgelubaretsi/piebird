import type { CallSignal, Outcome } from "../core/operations";
import type { FinishedCall, McpOptions } from "./mcp";
import { describe, expect, test } from "bun:test";
import { PassThrough } from "node:stream";
import { catalog, handlers, parts } from "./fixture.test";
import { serveMcp } from "./mcp";

type Message = { readonly id?: number; readonly result?: unknown; readonly error?: unknown };

const MODERN = {
	"io.modelcontextprotocol/protocolVersion": "2026-07-28",
	"io.modelcontextprotocol/clientInfo": { name: "claude-code", version: "2" },
	"io.modelcontextprotocol/clientCapabilities": {},
};

const INITIALIZE = {
	jsonrpc: "2.0",
	id: 1,
	method: "initialize",
	params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "codex", version: "0" } },
};
const INITIALIZED = { jsonrpc: "2.0", method: "notifications/initialized" };

function isMessage(value: unknown): value is Message {
	return typeof value === "object" && value !== null;
}

/** Sends `requests` to a server serving the fixture (with `options` over its own) and returns its answers, by request id. */
async function exchange(requests: readonly object[], options: Partial<McpOptions> = {}): Promise<Map<number, Message>> {
	const stdin = new PassThrough();
	const stdout = new PassThrough();
	const handle = serveMcp({ ...parts("loud"), ...options }, { stdin, stdout });
	const expected = requests.filter(r => "id" in r).length;
	const answers = new Map<number, Message>();
	let buffered = "";
	const done = new Promise<void>(resolve => {
		stdout.on("data", (chunk: Buffer) => {
			buffered += chunk.toString();
			const lines = buffered.split("\n");
			buffered = lines.pop() ?? "";
			for (const line of lines) {
				const message: unknown = JSON.parse(line);
				if (isMessage(message) && message.id !== undefined) answers.set(message.id, message);
			}
			if (answers.size >= expected) resolve();
		});
	});
	for (const request of requests) stdin.write(`${JSON.stringify(request)}\n`);
	await done;
	await handle.close();
	return answers;
}

const ECHO_LISTED = {
	name: "echo",
	description: "Echo text back, upper-cased if asked.",
	inputSchema: {
		type: "object",
		properties: {
			text: { type: "string", description: "The text to echo." },
			upper: { type: "boolean", description: "Whether to upper-case it." },
		},
		required: ["text"],
		additionalProperties: false,
	},
	annotations: { readOnlyHint: true, idempotentHint: true, openWorldHint: false },
	_meta: { "anthropic/alwaysLoad": true },
};

function call(id: number, name: string, args: object, meta?: object): object {
	return {
		jsonrpc: "2.0",
		id,
		method: "tools/call",
		params: { name, arguments: args, ...(meta ? { _meta: meta } : {}) },
	};
}

describe("serveMcp, 2025 era (initialize)", () => {
	test("initializes with the server's name, version and instructions", async () => {
		const answers = await exchange([INITIALIZE]);
		expect(answers.get(1)?.result).toEqual({
			protocolVersion: "2025-06-18",
			capabilities: { tools: { listChanged: true } },
			serverInfo: { name: "fixture", version: "1.2.3" },
			instructions: "Use echo, in the loud style.",
		});
	});

	test("lists each tool with its schemas as given, its hints and alwaysLoad", async () => {
		const answers = await exchange([INITIALIZE, INITIALIZED, { jsonrpc: "2.0", id: 2, method: "tools/list" }]);
		expect(answers.get(2)?.result).toEqual({
			tools: [
				ECHO_LISTED,
				{
					name: "refuse",
					description: "Refuse, always.",
					inputSchema: { type: "object", properties: {}, additionalProperties: false },
					annotations: { destructiveHint: true },
				},
				{
					name: "boom",
					description: "Throw.",
					inputSchema: { type: "object", properties: {}, additionalProperties: false },
					annotations: {},
				},
			],
		});
	});

	test("answers a call with the outcome's text only, which is what the model reads", async () => {
		const answers = await exchange([INITIALIZE, INITIALIZED, call(2, "echo", { text: "hello", upper: true })]);
		expect(answers.get(2)?.result).toEqual({ content: [{ type: "text", text: "HELLO" }] });
	});

	test("takes a field set to null as left out: the call passes the check and the handler never sees it", async () => {
		const answers = await exchange([INITIALIZE, INITIALIZED, call(2, "echo", { text: "hello", upper: null })]);
		expect(answers.get(2)?.result).toEqual({ content: [{ type: "text", text: "hello" }] });
	});

	test("answers a declared error as a tool error with its text", async () => {
		const answers = await exchange([INITIALIZE, INITIALIZED, call(2, "refuse", {})]);
		expect(answers.get(2)?.result).toEqual({
			content: [{ type: "text", text: "Refused: there is nothing to do." }],
			isError: true,
		});
	});

	test("answers a handler that throws as a tool error: the catalog's error-crashed with its message", async () => {
		const answers = await exchange([INITIALIZE, INITIALIZED, call(2, "boom", {})]);
		expect(answers.get(2)?.result).toEqual({
			content: [{ type: "text", text: "It broke: boom went the handler" }],
			isError: true,
		});
	});

	test("refuses arguments the input schema doesn't take, in the catalog's words, without calling the handler", async () => {
		const refused = [{ upper: true }, { text: 1 }, { text: "hi", extra: true }];
		const answers = await exchange([INITIALIZE, INITIALIZED, ...refused.map((args, i) => call(i + 2, "echo", args))]);
		for (const id of refused.map((_, i) => i + 2)) {
			const result = answers.get(id)?.result;
			expect(result).toMatchObject({ isError: true });
			// The handler would have thrown, its crash read as "It broke: ...".
			expect(JSON.stringify(result)).toContain("Those arguments don't fit: ");
		}
	});

	test("tells afterCall each outcome with the call's _meta, and answers the same when it fails", async () => {
		const calls: FinishedCall[] = [];
		const answers = await exchange(
			[INITIALIZE, INITIALIZED, call(2, "refuse", {}, { sessionId: "s-1" }), call(3, "echo", { text: "hi" })],
			{
				async afterCall(finished) {
					calls.push(finished);
					throw new Error("can't write the mark");
				},
			},
		);
		expect(calls.map(c => [c.operation, c.outcome.ok, c.meta])).toEqual([
			["refuse", false, { sessionId: "s-1" }],
			["echo", true, {}],
		]);
		expect(answers.get(2)?.result).toMatchObject({ isError: true });
		expect(answers.get(3)?.result).toEqual({ content: [{ type: "text", text: "hi" }] });
	});

	test("a call the client cancels aborts its handler's signal, and afterCall doesn't hear of it", async () => {
		const stdin = new PassThrough();
		const stdout = new PassThrough();
		const heard: FinishedCall[] = [];
		const started = Promise.withResolvers<void>();
		const stopped = Promise.withResolvers<void>();
		// A handler that waits until its call is cancelled.
		const waits = async (_input: unknown, signal?: CallSignal): Promise<Outcome> => {
			started.resolve();
			await new Promise<void>(resolve => {
				if (signal instanceof AbortSignal) signal.addEventListener("abort", () => resolve());
			});
			stopped.resolve();
			return { ok: false, error: "vault", text: catalog.text("refuse-refused") };
		};
		const afterCall = async (finished: FinishedCall) => void heard.push(finished);
		const handle = serveMcp(
			{ ...parts("loud"), handlers: { ...handlers, echo: waits }, afterCall },
			{ stdin, stdout },
		);
		for (const request of [INITIALIZE, INITIALIZED, call(2, "echo", { text: "hi" })])
			stdin.write(`${JSON.stringify(request)}\n`);
		await started.promise;
		const cancel = { jsonrpc: "2.0", method: "notifications/cancelled", params: { requestId: 2 } };
		stdin.write(`${JSON.stringify(cancel)}\n`);
		await stopped.promise;
		await handle.close();
		expect(heard).toEqual([]);
	});
});

describe("serveMcp, 2026-07-28 era (server/discover)", () => {
	test("discovers with the protocol-version claim, then lists and calls statelessly", async () => {
		const answers = await exchange([
			{ jsonrpc: "2.0", id: 1, method: "server/discover", params: { _meta: MODERN } },
			{ jsonrpc: "2.0", id: 2, method: "tools/list", params: { _meta: MODERN } },
			call(3, "echo", { text: "hi" }, MODERN),
		]);
		const serverInfo = { "io.modelcontextprotocol/serverInfo": { name: "fixture", version: "1.2.3" } };
		expect(answers.get(1)?.result).toEqual({
			supportedVersions: ["2026-07-28"],
			capabilities: { tools: { listChanged: true } },
			instructions: "Use echo, in the loud style.",
			resultType: "complete",
			ttlMs: 0,
			cacheScope: "private",
			_meta: serverInfo,
		});
		expect(answers.get(2)?.result).toMatchObject({ tools: [ECHO_LISTED, { name: "refuse" }, { name: "boom" }] });
		expect(answers.get(3)?.result).toEqual({
			content: [{ type: "text", text: "hi" }],
			resultType: "complete",
			_meta: serverInfo,
		});
	});

	test("a discover without the claim counts as 2025-era and isn't found", async () => {
		const answers = await exchange([{ jsonrpc: "2.0", id: 1, method: "server/discover", params: {} }]);
		expect(answers.get(1)?.error).toEqual({ code: -32601, message: "Method not found" });
	});
});

test("serveMcp refuses a tool without a handler before serving", () => {
	const { echo: _echo, ...rest } = handlers;
	expect(() =>
		serveMcp({ ...parts(), handlers: rest }, { stdin: new PassThrough(), stdout: new PassThrough() }),
	).toThrow("no handler for the operation echo");
});
