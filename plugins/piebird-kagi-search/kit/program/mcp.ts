// The program's MCP server, for the agents that take a plugin's tools from a program: Codex and
// the desktop apps over the 2025 `initialize` handshake, Claude Code over the stateless 2026-07-28
// era. Each of the plugin's tools (core/operations.json) is listed with its input's JSON Schema as
// given and performed by core's handler. Arguments the schema doesn't take never reach the
// handler: the server checks them itself, so the model reads why in the plugin's words
// (error-arguments) rather than the SDK's. The model reads the outcome's text: no output schema,
// so no structured content, which Codex (0.162) shows the model instead of the text. The data
// stays for `call`. `serveStdio` picks the era from the first message, so a modern request must
// carry `_meta["io.modelcontextprotocol/protocolVersion"]`; a bare `server/discover` counts as
// 2025-era and is answered -32601.
import type { CallToolResult, ToolAnnotations } from "@modelcontextprotocol/server";
import type { StdioServerHandle } from "@modelcontextprotocol/server/stdio";
import type { Readable, Writable } from "node:stream";
import type { ModelText } from "../core/model";
import type { Handlers, JsonSchema, Operations, Outcome, ToolHints } from "../core/operations";
import { fromJsonSchema, McpServer } from "@modelcontextprotocol/server";
import { crashText, withoutNulls } from "../core/operations";
import { serveStdio, StdioServerTransport } from "@modelcontextprotocol/server/stdio";

/** One finished tool call (not one the client cancelled): the operation, its outcome, and the `_meta` the client sent with it. */
export interface FinishedCall {
	readonly operation: string;
	readonly outcome: Outcome;
	readonly meta: Readonly<Record<string, unknown>>;
}

export interface McpOptions {
	/** The server's name and version, as clients show them. */
	readonly name: string;
	readonly version: string;
	readonly operations: Operations;
	/** Core's handlers; every tool in `operations` needs one. */
	readonly handlers: Handlers;
	/** What the server tells the model about its tools, sent to every client. */
	readonly instructions?: ModelText;
	/** Told of each call that ends with an outcome, before the client gets it; its failure is ignored. */
	readonly afterCall?: (call: FinishedCall) => Promise<void>;
}

/** Other ends than the process's own stdin and stdout, for a test. */
export interface Stdio {
	readonly stdin: Readable;
	readonly stdout: Writable;
}

/** Claude Code keeps a tool with this `_meta` key in front of tool search. */
const ALWAYS_LOAD = "anthropic/alwaysLoad";

function annotations(hints: ToolHints): ToolAnnotations {
	const out: ToolAnnotations = {};
	if (hints.readOnly !== undefined) out.readOnlyHint = hints.readOnly;
	if (hints.destructive !== undefined) out.destructiveHint = hints.destructive;
	if (hints.idempotent !== undefined) out.idempotentHint = hints.idempotent;
	if (hints.openWorld !== undefined) out.openWorldHint = hints.openWorld;
	return out;
}

/** The tool result for an outcome: its text, as a tool error for a declared error. */
export function toolResult(outcome: Outcome): CallToolResult {
	const content = [{ type: "text" as const, text: outcome.text.text }];
	return outcome.ok ? { content } : { content, isError: true };
}

/** A call as the client sent it: its `_meta`, and the signal that aborts when the client cancels it. */
interface Request {
	readonly meta: unknown;
	readonly signal: AbortSignal;
}

async function perform(options: McpOptions, operation: string, input: unknown, req: Request): Promise<CallToolResult> {
	const handler = options.handlers[operation];
	if (handler === undefined) throw new Error(`no handler for the operation ${operation}`);
	let outcome: Outcome;
	try {
		outcome = await handler(input, req.signal);
	} catch (error) {
		return { content: [{ type: "text", text: crashText(options.operations, error).text }], isError: true };
	}
	// A cancelled call's outcome is how it was stopped, not what the operation found.
	if (!req.signal.aborted) {
		const fields = typeof req.meta === "object" && req.meta !== null ? { ...req.meta } : {};
		await options.afterCall?.({ operation, outcome, meta: fields }).catch(() => undefined);
	}
	return toolResult(outcome);
}

/** A tool's input schema as the SDK lists it: as given, the arguments passed on as sent. */
interface Listed {
	readonly "~standard": {
		readonly version: 1;
		readonly vendor: string;
		readonly jsonSchema: { readonly input: () => JsonSchema; readonly output: () => JsonSchema };
		readonly validate: (value: unknown) => { readonly value: unknown };
	};
}

function listedAsGiven(schema: JsonSchema): Listed {
	return {
		"~standard": {
			version: 1,
			vendor: "piebird",
			jsonSchema: { input: () => schema, output: () => schema },
			validate: (value: unknown) => ({ value }),
		},
	};
}

/** What in `input` the schema `schema` doesn't take, with the SDK's own validator; none when it fits. */
function argumentChecker(schema: JsonSchema): (input: unknown) => Promise<string | undefined> {
	const { validate } = fromJsonSchema(schema)["~standard"];
	return async input => {
		const result = await validate(input);
		return result.issues === undefined ? undefined : result.issues.map(i => i.message).join("; ");
	};
}

/** One server with every tool registered; `serveMcp`'s factory makes one per connection. */
export function mcpServer(options: McpOptions): McpServer {
	const { name, version, operations, handlers, instructions } = options;
	const server = new McpServer(
		{ name, version },
		instructions === undefined ? {} : { instructions: instructions.text },
	);
	for (const op of operations.tools) {
		if (handlers[op.id] === undefined) throw new Error(`no handler for the operation ${op.id}`);
		const { tool } = op;
		const problemWith = argumentChecker(tool.inputSchema);
		server.registerTool(
			tool.name,
			{
				description: tool.description.text,
				inputSchema: listedAsGiven(tool.inputSchema),
				annotations: annotations(tool.hints),
				...(tool.hints.alwaysLoad === true ? { _meta: { [ALWAYS_LOAD]: true } } : {}),
			},
			async (input, ctx): Promise<CallToolResult> => {
				const args = withoutNulls(input);
				const problem = await problemWith(args);
				if (problem !== undefined)
					return { content: [{ type: "text", text: operations.badArguments(problem).text }], isError: true };
				// oxlint-disable-next-line eslint/no-underscore-dangle -- MCP names a request's metadata _meta
				return perform(options, op.id, args, { meta: ctx.mcpReq._meta, signal: ctx.mcpReq.signal });
			},
		);
	}
	return server;
}

/**
 * Serves the tools over stdio until the client closes stdin. Throws at once when a tool has no
 * handler, rather than on the first client's connection.
 */
export function serveMcp(options: McpOptions, stdio?: Stdio): StdioServerHandle {
	mcpServer(options);
	const transport = stdio === undefined ? undefined : new StdioServerTransport(stdio.stdin, stdio.stdout);
	return serveStdio(() => mcpServer(options), transport === undefined ? {} : { transport });
}
