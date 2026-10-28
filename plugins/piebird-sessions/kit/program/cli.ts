// The program's commands: `mcp` serves the plugin's tools, `hook` answers a Codex hook, `call`
// performs one operation for a person or a script, `settings` opens the person's settings page.
// The program's main.ts says what they work with; this only reads the command line and wires
// stdin and stdout.
import type { Declared } from "../core/declared";
import type { HookAnswer, HookInput } from "./hook";
import type { McpOptions } from "./mcp";
import { readHookInput } from "./hook";
import { serveMcp } from "./mcp";
import { withoutNulls } from "../core/operations";
import { runSettingsPage } from "./settings";

export interface Parts extends McpOptions {
	/** Answers a Codex hook event; a program without hooks has none. */
	readonly hook?: (input: HookInput) => Promise<HookAnswer>;
}

export interface Program {
	/** The program's command name, for its usage message. */
	readonly name: string;
	/**
	 * What the commands work with, made once the command line is read. The person's settings come
	 * from their settings files: no host passes the program settings of its own.
	 */
	readonly parts: () => Promise<Parts>;
	/** The plugin's declared settings, for the settings page; none when it has none. */
	readonly settings?: Declared;
}

interface Command {
	readonly name: string;
	readonly args: readonly string[];
}

/** A command line the program doesn't take: exit 2 with the usage message. */
class UsageError extends Error {}

function usage(name: string): string {
	return [
		`Usage: ${name} <command>`,
		"",
		"Commands:",
		"  mcp               serve the plugin's tools over MCP on stdin and stdout",
		"  hook              answer the Codex hook event on stdin",
		"  call <operation>  perform an operation, its input as JSON on stdin; prints",
		'                    {"output": ...} or {"error": {"id": ..., "text": ...}}',
		"  settings          open your settings for this plugin in the browser",
		"",
	].join("\n");
}

function parse(argv: readonly string[]): Command {
	const [name = "", ...args] = argv;
	return { name, args };
}

function expectArgs(command: Command, count: number): void {
	if (command.args.length !== count)
		throw new UsageError(`${command.name} takes ${count === 0 ? "no" : count} argument${count === 1 ? "" : "s"}`);
}

async function call(parts: Parts, operation: string): Promise<void> {
	const handler = parts.handlers[operation];
	if (handler === undefined) {
		const known = Object.keys(parts.handlers).toSorted().join(", ");
		throw new UsageError(`no operation ${operation}; the operations: ${known}`);
	}
	const input: unknown = JSON.parse(await Bun.stdin.text());
	const outcome = await handler(withoutNulls(input));
	const reply = outcome.ok ? { output: outcome.data } : { error: { id: outcome.error, text: outcome.text.text } };
	process.stdout.write(`${JSON.stringify(reply)}\n`);
}

async function hook(parts: Parts): Promise<void> {
	if (parts.hook === undefined) throw new UsageError("this program answers no hooks");
	const answer = await parts.hook(readHookInput(await Bun.stdin.text()));
	process.stdout.write(answer.stdout);
	process.exitCode = answer.exitCode;
}

async function dispatch(program: Program, command: Command): Promise<void> {
	switch (command.name) {
		case "mcp":
			expectArgs(command, 0);
			// Serves until the client closes stdin; then nothing keeps the process alive.
			serveMcp(await program.parts());
			return;
		case "hook":
			expectArgs(command, 0);
			return hook(await program.parts());
		case "call":
			expectArgs(command, 1);
			return call(await program.parts(), command.args[0] ?? "");
		case "settings":
			expectArgs(command, 0);
			if (!program.settings) throw new UsageError("this plugin has no settings");
			return runSettingsPage([{ name: program.name, declared: program.settings }]);
		default:
			throw new UsageError(command.name === "" ? "no command" : `no command ${command.name}`);
	}
}

/**
 * Runs the command in `argv` (the arguments after the program's own path) and sets the exit
 * status: 0 when it ran, 2 for a command line it doesn't take, 1 when it failed. `--help` prints
 * the usage message.
 */
export async function runProgram(argv: readonly string[], program: Program): Promise<void> {
	const [first] = argv;
	if (first === "--help" || first === "-h" || first === "help") {
		process.stdout.write(usage(program.name));
		return;
	}
	try {
		await dispatch(program, parse(argv));
	} catch (error) {
		const message = error instanceof Error ? error.message : String(error);
		process.stderr.write(`${program.name}: ${message}\n`);
		if (error instanceof UsageError) process.stderr.write(usage(program.name));
		process.exitCode = error instanceof UsageError ? 2 : 1;
	}
}
