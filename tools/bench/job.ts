// One bench run (plugins/docs/bench.md): a throwaway sandbox on this Mac with the variant's plugin
// linked into omp, the suite's project in it, `omp -p` on the task's prompt, then everything the
// analysis reads copied into the run's folder. The sandbox goes, whatever happened.
import { cp, mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { hostSandbox } from "../demo/place-host";
import { writeProject } from "../demo/project";
import { signal, stopLeftovers } from "./leftovers";
import type { Job, Suite } from "./suite";

/** What every run of a bench shares. */
export interface Bench {
	suite: Suite;
	/** The project's files: path → text. */
	files: Record<string, string>;
	/** Variant → the market (a folder with plugins/<plugin>) holding its copy of the plugin. */
	markets: Record<string, string>;
	/** <out>/runs. */
	runs: string;
}

/** meta.json: how the run went. */
export interface Meta {
	id: string;
	variant: string;
	task: string;
	repeat: number;
	agent: string;
	model: string;
	thinking: string;
	exitCode: number | null;
	timedOut: boolean;
	seconds: number;
	startedAt: string;
	error?: string;
}

/** After a stop (at the timeout, or of leftovers), how long processes have to exit before they are killed. */
const GRACE_MS = 10_000;

type Env = Record<string, string | undefined>;

/** A command's output; throws with what it said when it fails. */
async function output(argv: string[], env: Env, cwd: string): Promise<string> {
	const proc = Bun.spawn(argv, { env, cwd, stdin: "ignore", stdout: "pipe", stderr: "pipe" });
	const [out, err, code] = await Promise.all([
		new Response(proc.stdout).text(),
		new Response(proc.stderr).text(),
		proc.exited,
	]);
	if (code !== 0) throw new Error(`${argv.join(" ")} exited ${code}: ${err.trim()}`);
	return out;
}

/** Every *.jsonl under `root`, in path order, concatenated; each ends its last line. Nothing when `root` is missing. */
export async function concatJournals(root: string): Promise<string> {
	const entries = await readdir(root, { recursive: true }).catch((error: unknown) => {
		if (error instanceof Error && "code" in error && error.code === "ENOENT") return [];
		throw error;
	});
	// Path order, by code unit: the same on every machine, whatever its locale.
	const files = entries.filter(path => path.endsWith(".jsonl")).toSorted((a, b) => (a < b ? -1 : a > b ? 1 : 0));
	let all = "";
	for (const path of files) {
		const text = await readFile(join(root, path), "utf8");
		all += text === "" || text.endsWith("\n") ? text : `${text}\n`;
	}
	return all;
}

interface Outcome {
	exitCode: number | null;
	timedOut: boolean;
	/** omp's time, to a tenth. */
	seconds: number;
}

/**
 * Runs omp on `prompt` in `cwd`, its output straight into final.txt and stderr.txt (not pipes: a
 * program the agent left running keeps a pipe open, and the run would wait for it); its process
 * group stopped at the timeout, killed if it doesn't exit soon after. Whatever it leaves running
 * is stopped before this returns.
 */
async function runAgent(
	suite: Suite,
	prompt: string,
	env: Env,
	places: { cwd: string; dir: string; home: string },
): Promise<Outcome> {
	const argv = ["omp", "-p", "--model", suite.model, "--thinking", suite.thinking, "--", prompt];
	const started = Date.now();
	// detached: omp leads a process group of its own (setsid), which the timeout and the cleanup signal.
	const proc = Bun.spawn(argv, {
		env,
		cwd: places.cwd,
		detached: true,
		stdin: "ignore",
		stdout: Bun.file(join(places.dir, "final.txt")),
		stderr: Bun.file(join(places.dir, "stderr.txt")),
	});
	let timedOut = false;
	let kill: Timer | undefined;
	const stop = setTimeout(() => {
		timedOut = true;
		signal(-proc.pid, "SIGTERM");
		kill = setTimeout(() => signal(-proc.pid, "SIGKILL"), GRACE_MS);
	}, suite.timeoutMinutes * 60_000);
	try {
		await proc.exited;
	} finally {
		clearTimeout(stop);
		clearTimeout(kill);
	}
	const seconds = Math.round((Date.now() - started) / 100) / 10;
	await stopLeftovers({ pgid: proc.pid, home: places.home, self: process.pid }, GRACE_MS);
	return { exitCode: proc.exitCode, timedOut, seconds };
}

/** The journals, the project afterwards, and git's view of what changed since `base`. */
async function collect(dir: string, s: { home: string; project: string; env: Env }, base: string): Promise<void> {
	await writeFile(join(dir, "journal.jsonl"), await concatJournals(join(s.home, ".omp", "agent", "sessions")));
	await cp(s.project, join(dir, "project"), { recursive: true, verbatimSymlinks: true });
	await output(["git", "add", "--all"], s.env, s.project);
	const diff = await output(["git", "diff", "--cached", "--binary", "--end-of-options", base, "--"], s.env, s.project);
	await writeFile(join(dir, "diff.patch"), diff);
	await writeFile(join(dir, "git-log.txt"), await output(["git", "log", "--oneline", "--all"], s.env, s.project));
}

/** Runs `job` into <runs>/<id>/; its meta.json says how it went, an `error` when it failed. */
export async function runJob(bench: Bench, job: Job): Promise<Meta> {
	const { suite } = bench;
	const dir = join(bench.runs, job.id);
	const prompt = suite.tasks[job.task]?.prompt ?? "";
	const meta: Meta = {
		...job,
		agent: suite.agent,
		model: suite.model,
		thinking: suite.thinking,
		exitCode: null,
		timedOut: false,
		seconds: 0,
		startedAt: new Date().toISOString(),
	};
	await mkdir(dir, { recursive: true });
	await writeFile(join(dir, "prompt.txt"), prompt);
	const market = bench.markets[job.variant] ?? "";
	try {
		const s = await hostSandbox({ plugins: [suite.plugin], market, projectName: suite.project.name });
		try {
			await writeProject(s.project, bench.files, suite.project.commit);
			const base = (
				await output(["git", "rev-parse", "--verify", "--end-of-options", "HEAD"], s.env, s.project)
			).trim();
			Object.assign(meta, await runAgent(suite, prompt, s.env, { cwd: s.project, dir, home: s.home }));
			await collect(dir, s, base);
		} finally {
			await s.close(false);
		}
	} catch (error) {
		meta.error = error instanceof Error ? error.message : String(error);
	}
	await writeFile(join(dir, "meta.json"), `${JSON.stringify(meta, null, 2)}\n`);
	return meta;
}

/** The line the runner prints when `meta`'s run ends. */
export function finishedLine(meta: Meta): string {
	if (meta.error !== undefined) return `${meta.id}: error: ${meta.error}`;
	if (meta.timedOut) return `${meta.id}: timed out, ${meta.seconds}s`;
	return `${meta.id}: exit ${meta.exitCode ?? "none"}, ${meta.seconds}s`;
}
