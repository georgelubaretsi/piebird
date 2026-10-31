// The bench runner (plugins/docs/bench.md): `bun tools/bench/run.ts <suite> [flags]` from plugins/.
// Runs each chosen variant × task × repeat of a suite in its own sandbox, `concurrency` at a time,
// into a run folder, then scores it with tools/bench/score.py. Bad input stops it with exit 2
// before any sandbox starts.
import { statSync } from "node:fs";
import { copyFile, cp, mkdir, mkdtemp, readdir, readFile, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, relative, resolve } from "node:path";
import { isOutside } from "../build/paths";
import { parseOptions, suiteFolder, type SuiteFolder, USAGE } from "./cli";
import { type Bench, finishedLine, runJob } from "./job";
import {
	BenchError,
	type Job,
	type Override,
	overridesOf,
	parseSuite,
	planJobs,
	type Selection,
	select,
	type Suite,
} from "./suite";

/** plugins/. */
const ROOT = resolve(import.meta.dir, "..", "..");

const isFile = (path: string) => statSync(path, { throwIfNoEntry: false })?.isFile() ?? false;

/** A project's files: path → text. */
const isFiles = (value: unknown): value is Record<string, string> =>
	typeof value === "object" &&
	value !== null &&
	!Array.isArray(value) &&
	Object.values(value).every(text => typeof text === "string");

/** The project's files, the export the suite names; a BenchError when it isn't path → text. */
async function projectFiles(suite: Suite, file: string): Promise<Record<string, string>> {
	const { module, export: name } = suite.project;
	let loaded: unknown;
	try {
		// The suite names the module, so it is known only at run time.
		loaded = await import(join(ROOT, module));
	} catch (error) {
		throw new BenchError(
			`${file}: /project/module can't be loaded: ${error instanceof Error ? error.message : String(error)}`,
		);
	}
	// A module namespace has no prototype, so `instanceof Object` is false for it.
	const exports = typeof loaded === "object" && loaded !== null ? Object.entries(loaded) : [];
	const files: unknown = exports.find(([key]) => key === name)?.[1];
	if (!isFiles(files))
		throw new BenchError(`${file}: /project/export ${module} has no export ${name} mapping paths to texts`);
	return files;
}

/** The run folder: `--out` when given (new or empty), else a new temporary one. */
async function outFolder(out: string | undefined, suite: string): Promise<string> {
	if (out === undefined) return mkdtemp(join(tmpdir(), `bench-${suite}-`));
	const path = resolve(out);
	const entries = await readdir(path).catch(() => undefined);
	if (entries !== undefined && entries.length > 0) throw new BenchError(`--out: ${out} isn't empty`);
	await mkdir(path, { recursive: true });
	return path;
}

/** Everything checked before a sandbox starts. */
interface Prepared {
	folder: SuiteFolder;
	suite: Suite;
	selection: Selection;
	concurrency: number;
	overrides: Record<string, Override[]>;
	files: Record<string, string>;
	out: string;
	score: boolean;
}

async function prepare(argv: string[]): Promise<Prepared | undefined> {
	const options = parseOptions(argv);
	if (options.help) return undefined;
	const folder = suiteFolder(options.suite, {
		suites: join(ROOT, "tools", "bench", "suites"),
		cwd: process.cwd(),
		isFile,
	});
	const path = join(folder.root, "suite.json");
	const file = isOutside(relative(process.cwd(), path)) ? path : relative(process.cwd(), path);
	const suite = parseSuite(file, await readFile(path, "utf8"));
	const selection = select(suite, options);
	const pluginDir = join(ROOT, "plugins", suite.plugin);
	if (!statSync(pluginDir, { throwIfNoEntry: false })?.isDirectory())
		throw new BenchError(`${file}: /plugin there is no plugin ${suite.plugin} in plugins/`);
	const places = { file, suiteRoot: folder.root, pluginDir, isFile };
	const overrides = Object.fromEntries(selection.variants.map(v => [v, overridesOf(suite, v, places)]));
	const files = await projectFiles(suite, file);
	const out = await outFolder(options.out, folder.name);
	const concurrency = options.concurrency ?? suite.concurrency;
	return { folder, suite, selection, concurrency, overrides, files, out, score: options.score };
}

/**
 * The variant's market: a copy of the plugin with its files replaced, and plugins/node_modules
 * linked beside it, so the copy resolves its packages as the checkout's plugin does.
 */
async function writeMarket(p: Prepared, variant: string): Promise<string> {
	const market = join(p.out, "markets", variant);
	const plugin = join(market, "plugins", p.suite.plugin);
	await cp(join(ROOT, "plugins", p.suite.plugin), plugin, { recursive: true, verbatimSymlinks: true });
	for (const { target, source } of p.overrides[variant] ?? []) await copyFile(source, join(plugin, target));
	if (statSync(join(ROOT, "node_modules"), { throwIfNoEntry: false })?.isDirectory())
		await symlink(join(ROOT, "node_modules"), join(market, "node_modules"));
	return market;
}

/** Runs `jobs`, `concurrency` at a time, a line on stderr as each ends. */
async function runAll(bench: Bench, jobs: Job[], concurrency: number): Promise<void> {
	let next = 0;
	const worker = async () => {
		for (let job = jobs[next++]; job !== undefined; job = jobs[next++]) {
			process.stderr.write(`${finishedLine(await runJob(bench, job))}\n`);
		}
	};
	await Promise.all(Array.from({ length: Math.min(concurrency, jobs.length) }, worker));
}

async function main(argv: string[]): Promise<number> {
	const p = await prepare(argv);
	if (p === undefined) {
		console.log(USAGE);
		return 0;
	}
	const { selection, suite } = p;
	const { $schema: _schema, ...asRun } = suite as Suite & { $schema?: string };
	const ran = { variants: selection.variants, tasks: selection.tasks, repeats: selection.repeats };
	const record = { ...asRun, name: p.folder.name, root: p.folder.root, ran, startedAt: new Date().toISOString() };
	await writeFile(join(p.out, "suite.json"), `${JSON.stringify(record, null, 2)}\n`);
	const markets: Record<string, string> = {};
	for (const variant of selection.variants) markets[variant] = await writeMarket(p, variant);
	await runAll({ suite, files: p.files, markets, runs: join(p.out, "runs") }, planJobs(selection), p.concurrency);
	console.log(p.out);
	if (!p.score) return 0;
	const score = Bun.spawn(["uv", "run", "--locked", "python", "tools/bench/score.py", "--", p.out], {
		cwd: ROOT,
		stdio: ["inherit", "inherit", "inherit"],
	});
	return score.exited;
}

try {
	process.exitCode = await main(Bun.argv.slice(2));
} catch (error) {
	if (!(error instanceof BenchError)) throw error;
	process.stderr.write(`${error.message}\n${USAGE}\n`);
	process.exitCode = 2;
}
