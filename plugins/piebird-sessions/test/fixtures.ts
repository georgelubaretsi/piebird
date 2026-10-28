// Made-up session journals in a throwaway sessions folder, read through readSession.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import type { ReadParams } from "../core/params";
import { readSession } from "../core/read";
import { bunIo } from "../kit/bun/io";

/** The message a read fails with; a read that succeeds fails the test. */
export async function failure(read: Promise<unknown>): Promise<string> {
	try {
		await read;
	} catch (error) {
		return error instanceof Error ? error.message : String(error);
	}
	throw new Error("expected the read to fail");
}

export const at = (second: number) => `2026-09-02T10:00:${String(second).padStart(2, "0")}.000Z`;

export const message = (second: number, role: string, content: unknown, extra: Record<string, unknown> = {}) => ({
	type: "message",
	timestamp: at(second),
	message: { role, content, ...extra },
});

export class Sessions {
	readonly root = fs.mkdtempSync(path.join(os.tmpdir(), "sessions-plugin-test-"));
	readonly folder = path.join(this.root, "-some-project");

	constructor() {
		fs.mkdirSync(this.folder);
	}

	/** Writes a journal for a session whose id starts with `prefix`; returns its lines. */
	write(prefix: string, entries: unknown[], stamp = "2026-09-02T10-00-00-000Z"): string[] {
		const lines = entries.map(entry => JSON.stringify(entry));
		fs.writeFileSync(
			path.join(this.folder, `${stamp}_${prefix}-bbbb-cccc-dddd-eeeeeeeeeeee.jsonl`),
			`${lines.join("\n")}\n`,
		);
		return lines;
	}

	/** The tool's text, split into lines: what it shows, then where to go next. `current` is this session's journal. */
	async read(params: ReadParams, current?: string): Promise<string[]> {
		const list = { kind: "folder" as const, folder: this.folder, ...(current === undefined ? {} : { current }) };
		// A home that holds none of the sessions: with the real one, a temp folder under it (CI's
		// runner) would show as ~/..., which the expected texts don't.
		const context = { roots: [this.root], list, home: path.join(this.root, "home") };
		return (await readSession(bunIo(), params, context)).text.split("\n");
	}

	cleanup(): void {
		fs.rmSync(this.root, { recursive: true, force: true });
	}
}

/** A reply, a three-step tool loop, another reply, a question, thinking alone, a last reply. */
export function writePages(sessions: Sessions): string[] {
	return sessions.write("01a0cccc", [
		{ type: "session", id: "01a0cccc-bbbb-cccc-dddd-eeeeeeeeeeee", timestamp: at(0) },
		message(1, "user", "first question"),
		message(2, "assistant", [
			{ type: "thinking", thinking: "pondering" },
			{ type: "text", text: "first reply" },
		]),
		...[0, 1, 2].flatMap(step => [
			message(3 + 2 * step, "assistant", [
				{ type: "toolCall", id: `call-${step}`, name: "bash", arguments: { command: `step ${step}` } },
			]),
			message(4 + 2 * step, "toolResult", [{ type: "text", text: `out ${step}` }], {
				toolCallId: `call-${step}`,
				toolName: "bash",
			}),
		]),
		message(9, "assistant", [{ type: "text", text: "second reply — ok" }]),
		message(10, "user", "second question"),
		message(11, "assistant", [{ type: "thinking", thinking: "deep thought" }]),
		message(12, "assistant", [{ type: "text", text: "third reply" }]),
	]);
}
