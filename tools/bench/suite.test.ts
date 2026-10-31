import { describe, expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { BenchError, overridesOf, parseSuite, planJobs, select, type Suite } from "./suite";

const FILE = "suites/x/suite.json";

const suite = (over: Partial<Suite> = {}): Suite => ({
	description: "d",
	plugin: "demo",
	project: { module: "demos/shop-api.ts", export: "shopApi", name: "shop-api", commit: "c" },
	agent: "omp",
	model: "m",
	thinking: "medium",
	repeats: 3,
	concurrency: 2,
	timeoutMinutes: 1,
	guide: "rules/x.md",
	variants: { shipped: {}, short: { "rules/x.md": "short.md" } },
	tasks: { one: { prompt: "p", checks: ["a"] }, two: { prompt: "q", checks: ["b"] } },
	...over,
});

const problemsOf = (value: unknown): string => {
	try {
		parseSuite(FILE, JSON.stringify(value));
	} catch (error) {
		if (error instanceof BenchError) return error.message;
		throw error;
	}
	return "";
};

describe("parseSuite", () => {
	test("accepts the interfaces suite", async () => {
		const file = join(import.meta.dir, "suites", "interfaces", "suite.json");
		expect(parseSuite(file, await readFile(file, "utf8")).agent).toBe("omp");
	});

	test("refuses text that isn't JSON, naming the file", () => {
		expect(() => parseSuite(FILE, "{")).toThrow(/^suites\/x\/suite\.json: not JSON/);
	});

	const cases: { name: string; value: unknown; problem: string }[] = [
		{
			name: "a missing field",
			value: (({ guide: _, ...rest }) => rest)(suite()),
			problem: "must have required property 'guide'",
		},
		{
			name: "an agent other than omp",
			value: { ...suite(), agent: "codex" },
			problem: "/agent must be equal to one of",
		},
		{
			name: "a variant name out of pattern",
			value: suite({ variants: { Shipped: {} } }),
			problem: "/variants/Shipped",
		},
		{
			name: "a task name with a dot",
			value: suite({ tasks: { "a.b": { prompt: "p", checks: ["c"] } } }),
			problem: "/tasks/a.b",
		},
		{
			name: "a task without checks",
			value: suite({ tasks: { one: { prompt: "p", checks: [] } } }),
			problem: "/tasks/one/checks",
		},
		{
			name: "a check name out of pattern",
			value: suite({ tasks: { one: { prompt: "p", checks: ["a_b"] } } }),
			problem: "/tasks/one/checks/0",
		},
		{
			name: "no variants",
			value: suite({ variants: {} }),
			problem: "/variants must NOT have fewer than 1 properties",
		},
		{ name: "zero repeats", value: suite({ repeats: 0 }), problem: "/repeats must be >= 1" },
		{
			name: "a field the schema lacks",
			value: { ...suite(), extra: 1 },
			problem: 'must NOT have additional properties: "extra"',
		},
	];
	for (const c of cases) {
		test(`refuses ${c.name}, naming the field`, () => {
			expect(problemsOf(c.value)).toContain(c.problem);
		});
	}
});

describe("select", () => {
	test("takes everything in the suite when nothing is asked", () => {
		expect(select(suite(), {})).toEqual({ variants: ["shipped", "short"], tasks: ["one", "two"], repeats: 3 });
	});

	test("takes the names and repeats asked for, in the order given", () => {
		expect(select(suite(), { variants: ["short", "shipped"], tasks: ["two"], repeats: 1 })).toEqual({
			variants: ["short", "shipped"],
			tasks: ["two"],
			repeats: 1,
		});
	});

	test("refuses a name the suite lacks, naming the flag", () => {
		expect(() => select(suite(), { variants: ["long"] })).toThrow(/^--variants: the suite has no "long"/);
		expect(() => select(suite(), { tasks: ["three"] })).toThrow(/^--tasks: the suite has no "three"/);
	});

	test("refuses a name listed twice", () => {
		expect(() => select(suite(), { tasks: ["one", "one"] })).toThrow(/^--tasks: "one" is listed twice/);
	});
});

describe("planJobs", () => {
	test("one job per variant, task and repeat, repeats from 1, each round whole before the next", () => {
		const jobs = planJobs({ variants: ["a", "b"], tasks: ["t"], repeats: 2 });
		expect(jobs.map(j => j.id)).toEqual(["a.t.1", "b.t.1", "a.t.2", "b.t.2"]);
		expect(jobs[3]).toEqual({ id: "b.t.2", variant: "b", task: "t", repeat: 2 });
	});
});

describe("overridesOf", () => {
	const pluginDir = "/m/plugins/demo";
	const files = new Set(["/m/plugins/demo/rules/x.md", "/s/short.md", "/s/other.md"]);
	const places = { file: FILE, suiteRoot: "/s", pluginDir, isFile: (p: string) => files.has(p) };
	const of = (entries: Record<string, string>) => overridesOf(suite({ variants: { v: entries } }), "v", places);

	test("maps each entry to the plugin-relative target and the absolute source", () => {
		expect(of({ "./rules/../rules/x.md": "short.md" })).toEqual([{ target: "rules/x.md", source: "/s/short.md" }]);
	});

	test("an empty variant replaces nothing", () => {
		expect(of({})).toEqual([]);
	});

	for (const target of ["../other/x.md", "rules/../../other/x.md", "/etc/passwd", ".", ""]) {
		test(`refuses the target ${JSON.stringify(target)} outside the plugin, naming the entry`, () => {
			expect(() => of({ [target]: "short.md" })).toThrow(
				/^suites\/x\/suite\.json: \/variants\/v\/.* the target must be a file inside the plugin/,
			);
		});
	}

	test("refuses a target the plugin doesn't have", () => {
		expect(() => of({ "rules/y.md": "short.md" })).toThrow(
			'/variants/v/rules~1y.md the plugin has no file "rules/y.md"',
		);
	});

	test("refuses a source that isn't there", () => {
		expect(() => of({ "rules/x.md": "missing.md" })).toThrow(
			'/variants/v/rules~1x.md the source "missing.md" isn\'t a file',
		);
	});
});
