// A bench suite (suite.schema.json, plugins/docs/bench.md), the pure part: parsing and checking
// it, choosing what to run, the runs it makes, and the files each variant replaces.
import Ajv2020 from "ajv/dist/2020";
import { join, relative, resolve } from "node:path";
import { located, pointerToken } from "../build/json";
import { isOutside } from "../build/paths";
import { schemaProblems } from "../build/schemas";
import suiteSchema from "./suite.schema.json" with { type: "json" };

/** Bad input: the command line, the suite or its files. The runner exits 2 on it. */
export class BenchError extends Error {}

/** Suites', variants', tasks' and checks' names. */
export const SUITE_NAME = new RegExp(suiteSchema.$defs.name.pattern);

export interface Task {
	prompt: string;
	checks: string[];
}

/** A suite.json, as suite.schema.json shapes it. */
export interface Suite {
	description: string;
	plugin: string;
	project: { module: string; export: string; name: string; commit: string };
	agent: "omp";
	model: string;
	thinking: string;
	repeats: number;
	concurrency: number;
	timeoutMinutes: number;
	guide: string;
	variants: Record<string, Record<string, string>>;
	tasks: Record<string, Task>;
}

const validateSuite = new Ajv2020({ allErrors: true, verbose: true }).compile<Suite>(suiteSchema);

/** The suite in `text`, read from `file`; a BenchError naming each field that is wrong. */
export function parseSuite(file: string, text: string): Suite {
	let value: unknown;
	try {
		value = JSON.parse(text);
	} catch (error) {
		throw new BenchError(`${file}: not JSON: ${error instanceof Error ? error.message : String(error)}`);
	}
	if (!validateSuite(value)) throw new BenchError(schemaProblems(file, validateSuite.errors).join("\n"));
	return value;
}

/** What one bench run covers. */
export interface Selection {
	variants: string[];
	tasks: string[];
	repeats: number;
}

/** The names asked for, each one the suite has, in the order given; all of them when none are. */
function chosen(flag: string, asked: string[] | undefined, known: string[]): string[] {
	if (asked === undefined) return known;
	const seen = new Set<string>();
	for (const name of asked) {
		if (!known.includes(name))
			throw new BenchError(`${flag}: the suite has no ${JSON.stringify(name)} (it has ${known.join(", ")})`);
		if (seen.has(name)) throw new BenchError(`${flag}: ${JSON.stringify(name)} is listed twice`);
		seen.add(name);
	}
	return asked;
}

/** The variants, tasks and repeats to run: the flags' where given, else the suite's. */
export function select(suite: Suite, asked: Partial<Selection>): Selection {
	return {
		variants: chosen("--variants", asked.variants, Object.keys(suite.variants)),
		tasks: chosen("--tasks", asked.tasks, Object.keys(suite.tasks)),
		repeats: asked.repeats ?? suite.repeats,
	};
}

/** One run of a task on a variant. */
export interface Job {
	/** `<variant>.<task>.<repeat>`: the run's folder under runs/. */
	id: string;
	variant: string;
	task: string;
	/** From 1. */
	repeat: number;
}

/**
 * Every run the selection makes, each repeat of the whole grid before the next, variants side by
 * side within it: stopped early, the runs done still compare the variants.
 */
export function planJobs(selection: Selection): Job[] {
	const jobs: Job[] = [];
	for (let repeat = 1; repeat <= selection.repeats; repeat++) {
		for (const task of selection.tasks) {
			for (const variant of selection.variants)
				jobs.push({ id: `${variant}.${task}.${repeat}`, variant, task, repeat });
		}
	}
	return jobs;
}

/** A file a variant replaces: where in the plugin, and the suite's file that replaces it. */
export interface Override {
	/** Relative to the plugin folder, normalized. */
	target: string;
	/** Absolute. */
	source: string;
}

/** Where a variant's files are read and checked. */
export interface Places {
	/** The suite file, for messages. */
	file: string;
	/** The suite's folder, which the variant's sources are relative to. */
	suiteRoot: string;
	/** The plugin under test, as checked out. */
	pluginDir: string;
	/** Whether a regular file exists at an absolute path. */
	isFile: (path: string) => boolean;
}

/**
 * The files `variant` replaces. Each target must be a file the plugin has (a variant replaces
 * files, so a misspelled target can't quietly add one) and each source must exist.
 */
export function overridesOf(suite: Suite, variant: string, places: Places): Override[] {
	const entries = Object.entries(suite.variants[variant] ?? {});
	return entries.map(([target, source]) => {
		const where = located(places.file, `/variants/${pointerToken(variant)}/${pointerToken(target)}`);
		const rel = relative(places.pluginDir, resolve(places.pluginDir, target));
		if (rel === "" || isOutside(rel)) throw new BenchError(`${where} the target must be a file inside the plugin`);
		if (!places.isFile(join(places.pluginDir, rel)))
			throw new BenchError(`${where} the plugin has no file ${JSON.stringify(rel)} to replace`);
		const from = resolve(places.suiteRoot, source);
		if (!places.isFile(from)) throw new BenchError(`${where} the source ${JSON.stringify(source)} isn't a file`);
		return { target: rel, source: from };
	});
}
