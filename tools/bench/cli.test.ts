import { describe, expect, test } from "bun:test";
import { parseOptions, suiteFolder } from "./cli";

describe("parseOptions", () => {
	test("reads every flag, after the suite or before it", () => {
		const argv = [
			"--variants",
			"a,b",
			"s",
			"--tasks=t",
			"--repeats",
			"2",
			"--concurrency",
			"4",
			"--out",
			"o",
			"--no-score",
		];
		expect(parseOptions(argv)).toEqual({
			suite: "s",
			variants: ["a", "b"],
			tasks: ["t"],
			repeats: 2,
			concurrency: 4,
			out: "o",
			score: false,
			help: false,
		});
	});

	test("leaves out what isn't given, and scores by default", () => {
		expect(parseOptions(["s"])).toEqual({ suite: "s", score: true, help: false });
	});

	test("takes a suite after --", () => {
		expect(parseOptions(["--", "--odd"]).suite).toBe("--odd");
	});

	test("help needs no suite", () => {
		expect(parseOptions(["-h"]).help).toBe(true);
	});

	const bad: { argv: string[]; problem: RegExp }[] = [
		{ argv: [], problem: /no suite given/ },
		{ argv: ["a", "b"], problem: /one suite at a time/ },
		{ argv: ["s", "--repeat", "2"], problem: /--repeat/ },
		{ argv: ["s", "--repeats"], problem: /--repeats/ },
		{ argv: ["s", "--repeats", "0"], problem: /^--repeats: expected a whole number/ },
		{ argv: ["s", "--repeats", "-1"], problem: /--repeats/ },
		{ argv: ["s", "--concurrency", "2.5"], problem: /^--concurrency: expected a whole number/ },
		{ argv: ["s", "--concurrency", "3x"], problem: /^--concurrency: expected a whole number/ },
		{ argv: ["s", "--variants", "a,,b"], problem: /^--variants: expected names/ },
		{ argv: ["s", "--tasks", ""], problem: /^--tasks: expected names/ },
		{ argv: ["s", "--out", ""], problem: /^--out/ },
		{ argv: ["s", "--no-score=yes"], problem: /no-score/ },
	];
	for (const { argv, problem } of bad) {
		test(`refuses ${JSON.stringify(argv)}`, () => {
			expect(() => parseOptions(argv)).toThrow(problem);
		});
	}
});

describe("suiteFolder", () => {
	const files = new Set([
		"/p/tools/bench/suites/interfaces/suite.json",
		"/w/mine/suite.json",
		"/w/Bad_Name/suite.json",
	]);
	const places = { suites: "/p/tools/bench/suites", cwd: "/w", isFile: (p: string) => files.has(p) };

	test("a name is a suite in tools/bench/suites/", () => {
		expect(suiteFolder("interfaces", places)).toEqual({
			root: "/p/tools/bench/suites/interfaces",
			name: "interfaces",
		});
	});

	test("anything else is a path from the working folder", () => {
		expect(suiteFolder("mine", places)).toEqual({ root: "/w/mine", name: "mine" });
		expect(suiteFolder("../w/mine/", places)).toEqual({ root: "/w/mine", name: "mine" });
	});

	test("refuses a folder without a suite.json", () => {
		expect(() => suiteFolder("nothing", places)).toThrow(/^no suite "nothing"/);
	});

	test("refuses a suite folder whose name is out of pattern", () => {
		expect(() => suiteFolder("Bad_Name", places)).toThrow(/a suite's name matches/);
	});
});
