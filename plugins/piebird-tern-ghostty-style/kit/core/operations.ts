// A plugin's operations (core/operations.json) joined with their text from core/model.ftl, as its
// generated core/operations.gen.ts carries them, and the contract between the shells and the code
// that performs an operation. The build has checked the file and the text (tools/build/operations.ts);
// this reads them into types and refuses what the code can't use.
import type { ModelText } from "./model";

export type JsonSchema = Readonly<Record<string, unknown>>;

/** MCP's tool annotations, and whether the tool stays in front of tool search. */
export interface ToolHints {
	readonly readOnly?: boolean;
	readonly destructive?: boolean;
	readonly idempotent?: boolean;
	readonly openWorld?: boolean;
	readonly alwaysLoad?: boolean;
	/** It runs code the model wrote. */
	readonly runsCode?: boolean;
}

export interface Tool {
	readonly name: string;
	readonly description: ModelText;
	/** The operation's input with each argument's description, from model.ftl, filled in. */
	readonly inputSchema: JsonSchema;
	readonly outputSchema: JsonSchema;
	readonly hints: ToolHints;
}

export interface Operation {
	readonly id: string;
	readonly input: JsonSchema;
	readonly output: JsonSchema;
	readonly errors: readonly string[];
	/** The plugin's vault performs it: it needs a secret. */
	readonly vault: boolean;
	readonly tool?: Tool;
}

/** What an operation ends with: its answer, as the model reads it and as data, or a declared error. */
export type Outcome =
	| { readonly ok: true; readonly text: ModelText; readonly data: unknown }
	| { readonly ok: false; readonly error: string; readonly text: ModelText };

/**
 * A call's cancellation as core sees it: the platform's AbortSignal, which aborts when the caller
 * cancels the call. Core names only what it reads, so it typechecks where there's no AbortSignal
 * type (a Claude Code mod); a shell that hands it to its platform checks it is one.
 */
export interface CallSignal {
	readonly aborted: boolean;
}

/**
 * Performs one operation; the input is as the caller sent it, for the handler to check. `signal`
 * aborts when the caller cancels the call: whatever the handler started (a program, a wait) stops.
 */
export type Handler = (input: unknown, signal?: CallSignal) => Promise<Outcome>;

export type Handlers = Readonly<Record<string, Handler>>;

/**
 * The arguments of a call with each field set to null left out: a caller that sends every field
 * (OpenAI's strict mode) sets the ones it doesn't use to null, and an operation takes a field
 * that is there as given. Every shell passes a call's arguments through this before checking
 * them or calling the handler, so an operation can't take null as a value.
 */
export function withoutNulls(input: unknown): unknown {
	if (!isFields(input)) return input;
	return Object.fromEntries(Object.entries(input).filter(([, value]) => value !== null));
}

/**
 * What the model reads when a tool can't answer as its operation says, from the plugin's catalog:
 * `crashed`, error-crashed, when its code fails instead (a bug, an unexpected error), with the
 * failure's own message; `badArguments`, error-arguments, when the arguments don't fit the tool's
 * input schema, with what doesn't. A plugin with tools has both (tools/build/operations.ts).
 */
export interface ToolWords {
	readonly crashed: (cause: string) => ModelText;
	readonly badArguments: (problem: string) => ModelText;
}

export interface Operations extends ToolWords {
	readonly byId: ReadonlyMap<string, Operation>;
	/** The operations the model gets as tools, in declaration order. */
	readonly tools: readonly (Operation & { readonly tool: Tool })[];
}

/** The failure `error` as the model reads it: the catalog's error-crashed with its message. */
export function crashText(operations: Operations, error: unknown): ModelText {
	return operations.crashed(error instanceof Error ? error.message : String(error));
}

/** For a plugin without tools: it never needs these words. */
const NO_TOOLS: ToolWords = {
	crashed: () => {
		throw new Error("this plugin has no tools");
	},
	badArguments: () => {
		throw new Error("this plugin has no tools");
	},
};

type Fields = Readonly<Record<string, unknown>>;

function isFields(value: unknown): value is Fields {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

function fields(value: unknown, at: string): Fields {
	if (isFields(value)) return value;
	throw new Error(`operations.json: ${at} isn't an object`);
}

function textFor(text: ReadonlyMap<string, ModelText>, id: string): ModelText {
	const found = text.get(id);
	if (found === undefined) throw new Error(`model.ftl: no ${id}`);
	return found;
}

function hints(tool: Fields): ToolHints {
	const flag = (k: string) => (typeof tool[k] === "boolean" ? { [k]: tool[k] } : {});
	return {
		...flag("readOnly"),
		...flag("destructive"),
		...flag("idempotent"),
		...flag("openWorld"),
		...flag("alwaysLoad"),
		...flag("runsCode"),
	};
}

function toolFor(id: string, op: Fields, text: ReadonlyMap<string, ModelText>): Tool | undefined {
	if (op.tool === undefined) return undefined;
	const tool = fields(op.tool, `/operations/${id}/tool`);
	if (typeof tool.name !== "string") throw new Error(`operations.json: /operations/${id}/tool/name isn't text`);
	const input = fields(op.input, `/operations/${id}/input`);
	const props = fields(input.properties ?? {}, `/operations/${id}/input/properties`);
	const described = Object.fromEntries(
		Object.entries(props).map(([arg, schema]) => [
			arg,
			{
				...fields(schema, `/operations/${id}/input/properties/${arg}`),
				description: textFor(text, `${id}.${arg}`).text,
			},
		]),
	);
	return {
		name: tool.name,
		description: textFor(text, id),
		inputSchema: { ...input, properties: described },
		outputSchema: fields(op.output, `/operations/${id}/output`),
		hints: hints(tool),
	};
}

/**
 * The operations in `source` (operations.json without `$schema`), each tool given its text, with
 * `words` for a tool that can't answer; a plugin without tools needs none.
 */
export function parseOperations(
	source: string,
	text: ReadonlyMap<string, ModelText>,
	words: ToolWords = NO_TOOLS,
): Operations {
	const parsed: unknown = JSON.parse(source);
	const byId = new Map<string, Operation>();
	for (const [id, value] of Object.entries(fields(fields(parsed, "").operations, "/operations"))) {
		const op = fields(value, `/operations/${id}`);
		const errors = Array.isArray(op.errors) ? op.errors.filter((e): e is string => typeof e === "string") : [];
		const tool = toolFor(id, op, text);
		const base = {
			id,
			input: fields(op.input, `/operations/${id}/input`),
			output: fields(op.output, `/operations/${id}/output`),
			errors,
			vault: op.vault === true,
		};
		byId.set(id, tool === undefined ? base : { ...base, tool });
	}
	const tools = [...byId.values()].flatMap(op => (op.tool === undefined ? [] : [{ ...op, tool: op.tool }]));
	return { byId, tools, ...words };
}
