// A plugin's operations that the model gets as tools, in a Claude Code mod: the specs its hooks
// module registers with `$.tool.register` at session.start, and the answer its `tool.call` hook
// gives, from core's handler. No `$` here: Claude Code refuses a module that passes `$` to another
// file, so the hooks module makes every call and hands values in and out (kit/claude/io-of.md).
// The build copies kit/ into each plugin that needs it (plugins/<name>/kit/); edit it in kit/.
import type { Handlers, Operations, Outcome } from "../core/operations";
import { crashText, withoutNulls } from "../core/operations";

/** What `$.tool.register` takes (Claude Code's `ToolSpec`). */
export interface ToolSpec {
	/** The short name; the model calls it as `mcp__<plugin>__<name>`. */
	readonly name: string;
	readonly description: string;
	readonly inputSchema: Readonly<Record<string, unknown>>;
	/** True: the tool waits behind tool search; false: its schema is in every prompt. */
	readonly isDeferred: boolean;
}

/**
 * A `tool.call` hook's answer. Claude Code 2.1.296 gives the model `result` (a string) as the
 * tool's result and `deny` as an error result (`is_error`); it ignores `text` and `isError` on a
 * hook's own answer and refuses a `result` that is neither a string nor content blocks.
 */
export type CallResult = { readonly result: string } | { readonly deny: string };

/** The fields of a `tool.call` event that are Claude Code's, not the tool's arguments. */
const RESERVED: Readonly<Record<string, true>> = {
	tool: true,
	tool_use_id: true,
	agentId: true,
	requestMeta: true,
	consent: true,
};

/** One spec per operation the model gets as a tool, in declaration order. */
export function toolSpecs(operations: Operations): ToolSpec[] {
	return operations.tools.map(({ tool }) => ({
		name: tool.name,
		description: tool.description.text,
		inputSchema: tool.inputSchema,
		isDeferred: tool.hints.alwaysLoad !== true,
	}));
}

/** The name the model and `tool.call` hooks see for the plugin's tool `name`. */
export function toolName(plugin: string, name: string): string {
	return `mcp__${plugin}__${name}`;
}

/** Every tool's full name, for the `tool.call` hook's matcher. */
export function toolNames(plugin: string, operations: Operations): string[] {
	return operations.tools.map(({ tool }) => toolName(plugin, tool.name));
}

/** The tool's arguments in a `tool.call` event, which carries them beside its own fields. */
export function toolArguments(event: Readonly<Record<string, unknown>>): Record<string, unknown> {
	return Object.fromEntries(Object.entries(event).filter(([key]) => !Object.hasOwn(RESERVED, key)));
}

/** The hook's answer for an outcome: its text, as a result or, for a declared error, a refusal. */
export function callResult(outcome: Outcome): CallResult {
	return outcome.ok ? { result: outcome.text.text } : { deny: outcome.text.text };
}

/**
 * Performs the call to the tool `tool` (its full name) with its arguments `input`: core's handler
 * for the operation answers, and a handler that throws answers with the catalog's error-crashed.
 * Undefined when no operation is that tool, for the hook to pass the call on.
 */
export async function dispatch(
	operations: Operations,
	handlers: Handlers,
	tool: string,
	input: unknown,
): Promise<CallResult | undefined> {
	// Tool names never hold `__` (tools/operations.schema.json), so the last one ends the plugin's.
	const at = tool.lastIndexOf("__");
	const name = tool.startsWith("mcp__") && at > "mcp_".length ? tool.slice(at + 2) : undefined;
	const op = operations.tools.find(o => o.tool.name === name);
	if (op === undefined) return undefined;
	try {
		if (!Object.hasOwn(handlers, op.id)) throw new Error(`no handler for operation ${op.id}`);
		return callResult(await handlers[op.id](withoutNulls(input)));
	} catch (error) {
		return { deny: crashText(operations, error).text };
	}
}
