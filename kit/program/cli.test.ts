import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { mkdir, mkdtemp, realpath, rm } from "node:fs/promises";
import { homedir, tmpdir } from "node:os";
import { join } from "node:path";
import { writeMain } from "./fixture.test";

let dir: string;
let main: string;

beforeAll(async () => {
	dir = await realpath(await mkdtemp(join(tmpdir(), "kit-program-")));
	main = await writeMain(dir);
});
afterAll(() => rm(dir, { recursive: true, force: true }));

interface Ran {
	readonly exitCode: number;
	readonly stdout: string;
	readonly stderr: string;
}

/** Runs `command` in the temp folder with `stdin`. */
async function run(command: readonly string[], stdin = ""): Promise<Ran> {
	const proc = Bun.spawn([...command], {
		cwd: dir,
		stdin: new TextEncoder().encode(stdin),
		stdout: "pipe",
		stderr: "pipe",
	});
	const [stdout, stderr, exitCode] = await Promise.all([
		new Response(proc.stdout).text(),
		new Response(proc.stderr).text(),
		proc.exited,
	]);
	return { exitCode, stdout, stderr };
}

const fixture = (...args: string[]) => [process.execPath, "run", main, ...args];

/** Serves MCP from `command`, sends each request after the last one's answer, then closes stdin. */
async function serve(
	command: readonly string[],
	requests: readonly object[],
): Promise<{ answers: unknown[]; exitCode: number }> {
	const proc = Bun.spawn([...command], { cwd: dir, stdin: "pipe", stdout: "pipe", stderr: "inherit" });
	const lines = proc.stdout.pipeThrough(new TextDecoderStream()).getReader();
	const answers: unknown[] = [];
	let buffered = "";
	for (const request of requests) {
		await proc.stdin.write(`${JSON.stringify(request)}\n`);
		if (!("id" in request)) continue;
		while (!buffered.includes("\n")) {
			const { value, done } = await lines.read();
			if (done) throw new Error("the server closed stdout");
			buffered += value;
		}
		const end = buffered.indexOf("\n");
		answers.push(JSON.parse(buffered.slice(0, end)));
		buffered = buffered.slice(end + 1);
	}
	await proc.stdin.end();
	return { answers, exitCode: await proc.exited };
}

const INITIALIZE = {
	jsonrpc: "2.0",
	id: 1,
	method: "initialize",
	params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "codex", version: "0" } },
};
const INITIALIZED = { jsonrpc: "2.0", method: "notifications/initialized" };
const ECHO = { jsonrpc: "2.0", id: 2, method: "tools/call", params: { name: "echo", arguments: { text: "hi" } } };

const USAGE_START = "Usage: fixture <command>\n";

/** A hook event, about a call of `tool` when there is one. */
function event(name: string, tool?: string): string {
	const call = tool === undefined ? {} : { tool_name: tool, tool_input: {} };
	return JSON.stringify({ session_id: "s", cwd: dir, hook_event_name: name, ...call });
}

describe("runProgram", () => {
	test("--help prints the usage message", async () => {
		const ran = await run(fixture("--help"));
		expect(ran.exitCode).toBe(0);
		expect(ran.stdout.startsWith(USAGE_START)).toBe(true);
		expect(ran.stdout).toContain("call <operation>");
	});

	test("a command line it doesn't take exits 2 with the usage message", async () => {
		for (const args of [[], ["serve"], ["mcp", "extra"], ["call"], ["mcp", "-agent", "style=loud"]]) {
			const ran = await run(fixture(...args));
			expect({ args, exitCode: ran.exitCode, stdout: ran.stdout }).toEqual({ args, exitCode: 2, stdout: "" });
			expect(ran.stderr).toContain(USAGE_START);
		}
	});

	test("call prints the output or the declared error, and exits 0", async () => {
		expect(await run(fixture("call", "echo"), '{"text":"hi","upper":true}')).toEqual({
			exitCode: 0,
			stdout: '{"output":{"echoed":"HI"}}\n',
			stderr: "",
		});
		expect(await run(fixture("call", "refuse"), "{}")).toEqual({
			exitCode: 0,
			stdout: '{"error":{"id":"refused","text":"Refused: there is nothing to do."}}\n',
			stderr: "",
		});
	});

	test("call of an unknown operation exits 2 and names the operations", async () => {
		const ran = await run(fixture("call", "nope"), "{}");
		expect(ran.exitCode).toBe(2);
		expect(ran.stdout).toBe("");
		expect(ran.stderr).toStartWith(
			`fixture: no operation nope; the operations: boom, echo, place, refuse\n${USAGE_START}`,
		);
	});

	test("call exits 1 when the handler throws or the input isn't JSON", async () => {
		expect(await run(fixture("call", "boom"), "{}")).toEqual({
			exitCode: 1,
			stdout: "",
			stderr: "fixture: boom went the handler\n",
		});
		const ran = await run(fixture("call", "echo"), "not json");
		expect(ran.exitCode).toBe(1);
		expect(ran.stdout).toBe("");
	});

	test("call takes a field set to null as left out", async () => {
		expect(await run(fixture("call", "echo"), '{"text":"hi","upper":null}')).toEqual({
			exitCode: 0,
			stdout: '{"output":{"echoed":"hi"}}\n',
			stderr: "",
		});
	});

	test("call runs in the folder it was started in, the program's project", async () => {
		const ran = await run(fixture("call", "place"), "{}");
		expect(JSON.parse(ran.stdout)).toEqual({
			output: { home: homedir(), project: dir, plugin: join(import.meta.dir, "..", "..") },
		});
	});

	test("hook answers the event on stdin", async () => {
		expect(await run(fixture("hook"), event("PreToolUse", "webrun"))).toEqual({
			exitCode: 0,
			stdout:
				'{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"web.run doesn\'t search here; use echo."}}\n',
			stderr: "",
		});
		expect((await run(fixture("hook"), event("SessionStart"))).stdout).toBe(
			'{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"The echo tool is here."}}\n',
		);
		expect(await run(fixture("hook"), event("PreToolUse", "shell"))).toEqual({ exitCode: 0, stdout: "", stderr: "" });
		const broken = await run(fixture("hook"), "{}");
		expect({ exitCode: broken.exitCode, stdout: broken.stdout }).toEqual({ exitCode: 1, stdout: "" });
	});

	test("mcp serves until stdin closes", async () => {
		const { answers, exitCode } = await serve(fixture("mcp"), [INITIALIZE, INITIALIZED, ECHO]);
		expect(answers).toMatchObject([
			{
				id: 1,
				result: {
					serverInfo: { name: "fixture", version: "1.2.3" },
					instructions: "Use echo, in the plain style.",
				},
			},
			{ id: 2, result: { content: [{ type: "text", text: "hi" }] } },
		]);
		expect(exitCode).toBe(0);
	});
});

// Bun before 1.4.2 signs compiled programs so that macOS 27 kills them at launch (oven-sh/bun#32159).
test.skipIf(process.platform !== "darwin")(
	"the program compiles into a signed binary that serves and calls",
	async () => {
		const plugin = join(dir, "plugin");
		const platform = join(plugin, "native", `macos-${process.arch === "arm64" ? "arm64" : "x64"}`);
		await mkdir(platform, { recursive: true });
		const binary = join(platform, "fixture");
		const built = await run([process.execPath, "build", "--compile", main, "--outfile", binary]);
		expect(built.exitCode).toBe(0);
		expect(await run(["codesign", "--verify", "--strict", binary])).toEqual({ exitCode: 0, stdout: "", stderr: "" });

		const { answers, exitCode } = await serve([binary, "mcp"], [INITIALIZE, INITIALIZED, ECHO]);
		expect(answers).toMatchObject([
			{ id: 1, result: { instructions: "Use echo, in the plain style." } },
			{ id: 2, result: { content: [{ type: "text", text: "hi" }] } },
		]);
		expect(exitCode).toBe(0);
		const place = await run([binary, "call", "place"], "{}");
		expect(JSON.parse(place.stdout)).toEqual({ output: { home: homedir(), project: dir, plugin } });
	},
	60_000,
);
