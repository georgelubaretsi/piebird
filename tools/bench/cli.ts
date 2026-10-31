// The runner's command line (plugins/docs/bench.md), the pure part: the options and which folder
// the suite argument names.
import { basename, join, resolve } from "node:path";
import { parseArgs } from "node:util";
import { BenchError, SUITE_NAME } from "./suite";

export const USAGE =
	"usage: bun tools/bench/run.ts <suite> [--variants a,b] [--tasks a,b] [--repeats n] [--concurrency n] [--out dir] [--no-score]";

export interface Options {
	/** A suite's folder name under tools/bench/suites/, or a path to a suite folder. */
	suite: string;
	variants?: string[];
	tasks?: string[];
	repeats?: number;
	concurrency?: number;
	/** The run folder; a new temporary one when absent. */
	out?: string;
	/** Whether score.py scores the runs at the end. */
	score: boolean;
	help: boolean;
}

function names(flag: string, value: string | undefined): string[] | undefined {
	if (value === undefined) return undefined;
	const list = value.split(",");
	if (list.some(name => name === ""))
		throw new BenchError(`${flag}: expected names separated by commas, got ${JSON.stringify(value)}`);
	return list;
}

function count(flag: string, value: string | undefined): number | undefined {
	if (value === undefined) return undefined;
	if (!/^[1-9][0-9]*$/.test(value))
		throw new BenchError(`${flag}: expected a whole number from 1, got ${JSON.stringify(value)}`);
	return Number(value);
}

/** The options in `argv` (after the script); a BenchError on anything it doesn't take. */
export function parseOptions(argv: string[]): Options {
	let parsed;
	try {
		parsed = parseArgs({
			args: argv,
			allowPositionals: true,
			strict: true,
			options: {
				variants: { type: "string" },
				tasks: { type: "string" },
				repeats: { type: "string" },
				concurrency: { type: "string" },
				out: { type: "string" },
				"no-score": { type: "boolean" },
				help: { type: "boolean", short: "h" },
			},
		});
	} catch (error) {
		throw new BenchError(error instanceof Error ? error.message : String(error));
	}
	const { values, positionals } = parsed;
	const help = values.help === true;
	const [suite, ...extra] = positionals;
	if (!help && suite === undefined) throw new BenchError("no suite given");
	if (extra.length > 0) throw new BenchError(`one suite at a time, got also ${extra.join(" ")}`);
	if (values.out === "") throw new BenchError("--out: expected a folder");
	return {
		suite: suite ?? "",
		variants: names("--variants", values.variants),
		tasks: names("--tasks", values.tasks),
		repeats: count("--repeats", values.repeats),
		concurrency: count("--concurrency", values.concurrency),
		out: values.out,
		score: values["no-score"] !== true,
		help,
	};
}

/** Where a suite argument is looked up. */
export interface SuitePlaces {
	/** tools/bench/suites/, absolute. */
	suites: string;
	cwd: string;
	isFile: (path: string) => boolean;
}

/** The folder holding the suite and the suite's name, the folder's. */
export interface SuiteFolder {
	root: string;
	name: string;
}

function named(root: string): SuiteFolder {
	const name = basename(root);
	if (!SUITE_NAME.test(name))
		throw new BenchError(`suite folder ${JSON.stringify(name)}: a suite's name matches ${SUITE_NAME.source}`);
	return { root, name };
}

/**
 * The suite folder `arg` names: tools/bench/suites/<arg> when that suite exists, else `arg` as a
 * path from `cwd` when it holds a suite.json; a BenchError otherwise.
 */
export function suiteFolder(arg: string, places: SuitePlaces): SuiteFolder {
	const inSuites = join(places.suites, arg);
	if (SUITE_NAME.test(arg) && places.isFile(join(inSuites, "suite.json"))) return named(inSuites);
	const path = resolve(places.cwd, arg);
	if (places.isFile(join(path, "suite.json"))) return named(path);
	throw new BenchError(
		`no suite ${JSON.stringify(arg)}: not a folder in tools/bench/suites/ nor a folder holding a suite.json`,
	);
}
