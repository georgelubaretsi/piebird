// A plugin's operations that the model gets as tools, registered with omp, each performed by core's
// handler for it. The build copies kit/ into each plugin that needs it (plugins/<name>/kit/); edit
// it in kit/.
import type { Handlers, Operations, Outcome, Tool } from "../core/operations";
import { crashText, withoutNulls } from "../core/operations";

export interface ToolResult {
	content: { type: "text"; text: string }[];
	details?: unknown;
	isError?: boolean;
}

/** The fields of omp's ToolDefinition the kit sets; parameters are plain JSON Schema. */
export interface OmpTool<C> {
	name: string;
	label: string;
	description: string;
	parameters: Readonly<Record<string, unknown>>;
	/** "discoverable" tools are found through tool search; "essential" ones stay in front of the model. */
	loadMode: "essential" | "discoverable";
	/** omp's approval tier: a read-only tool reads, one that runs the model's code executes, any other changes something. */
	approval: "read" | "write" | "exec";
	/**
	 * Always false: without it, omp sends OpenAI the tool with no strict flag and the optional
	 * fields not nullable, and GPT models fill every field with a made-up value (time and dates,
	 * find and before), which the operations refuse. With false they send only what they use.
	 */
	strict: false;
	/** `ctx` is omp's ExtensionContext of the session that calls the tool. */
	execute(
		toolCallId: string,
		params: unknown,
		signal: AbortSignal | undefined,
		onUpdate: unknown,
		ctx: C,
	): Promise<ToolResult>;
}

/**
 * What registerOperations uses of omp's extension API (`ExtensionAPI` in `@oh-my-pi/pi-coding-agent`).
 * Declared here so kit/ needs no omp package to typecheck; each plugin passes its own `pi`, so the
 * plugin's typecheck checks omp's real type against this one.
 */
export interface ToolHost<C> {
	registerTool(tool: OmpTool<C>): void;
}

/** Core's handlers for one call, made from the calling session's context (its folder, project, ...). */
export type HandlersFor<C> = (ctx: C) => Handlers;

/** The tool result for an outcome: a declared error is a tool error that keeps its id in details. */
function resultOf(outcome: Outcome): ToolResult {
	const content = [{ type: "text" as const, text: outcome.text.text }];
	return outcome.ok
		? { content, details: outcome.data }
		: { content, details: { error: outcome.error }, isError: true };
}

/** omp's approval tier for a tool with `hints`. */
function approvalOf(hints: Tool["hints"]): OmpTool<unknown>["approval"] {
	if (hints.runsCode === true) return "exec";
	return hints.readOnly === true ? "read" : "write";
}

function definition<C>(
	operations: Operations,
	op: Operations["tools"][number],
	handlersFor: HandlersFor<C>,
): OmpTool<C> {
	const { id, tool } = op;
	return {
		name: tool.name,
		label: tool.name,
		description: tool.description.text,
		parameters: tool.inputSchema,
		loadMode: tool.hints.alwaysLoad === true ? "essential" : "discoverable",
		approval: approvalOf(tool.hints),
		strict: false,
		// oxlint-disable-next-line eslint/max-params -- omp's execute signature: the context comes fifth
		async execute(_toolCallId, params, signal, _onUpdate, ctx) {
			try {
				const handlers = handlersFor(ctx);
				if (!Object.hasOwn(handlers, id)) throw new Error(`no handler for operation ${id} (tool ${tool.name})`);
				// The call's signal aborts when the person cancels it.
				return resultOf(await handlers[id](withoutNulls(params), signal));
			} catch (error) {
				return { content: [{ type: "text", text: crashText(operations, error).text }], isError: true };
			}
		},
	};
}

/**
 * Registers one omp tool per operation in `operations.tools`. Each call is performed by the
 * handler for its operation (keyed by operation id) among `handlersFor(ctx)`; a handler that
 * throws, or an operation without one, answers with the catalog's error-crashed.
 */
export function registerOperations<C>(pi: ToolHost<C>, operations: Operations, handlersFor: HandlersFor<C>): void {
	for (const op of operations.tools) pi.registerTool(definition(operations, op, handlersFor));
}
