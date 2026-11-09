// The watched rules' conditions as omp compiles them (`new RegExp`, no flags) and checks them: on a
// bash call's arguments as JSON, and on every prefix of them while the model writes. A command that
// breaks a rule matches once it is complete; one that follows the rule matches at no point.
import { expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { isObject } from "../../../tools/build/json";
import { readFrontmatter } from "../../../tools/build/parse";

function conditions(rule: string): RegExp[] {
	const file = join(import.meta.dir, "..", "rules", `${rule}.md`);
	const problems: string[] = [];
	const front = readFrontmatter(file, readFileSync(file, "utf8"), problems)?.value;
	expect(problems).toEqual([]);
	const condition = isObject(front) ? front.condition : undefined;
	const patterns = [condition].flat().filter((pattern): pattern is string => typeof pattern === "string");
	expect(patterns.length).toBeGreaterThan(0);
	return patterns.map(pattern => new RegExp(pattern));
}

/** Whether omp's buffer `text` matches the rule, and whether any shorter prefix of it does. */
function matches(patterns: readonly RegExp[], text: string): { whole: boolean; prefix: boolean } {
	const hit = (part: string) => patterns.some(pattern => pattern.test(part));
	const prefixes = Array.from({ length: text.length }, (_, end) => text.slice(0, end));
	return { whole: hit(text), prefix: prefixes.some(hit) };
}

function check(rule: string, breaks: readonly string[], follows: readonly string[]): void {
	const patterns = conditions(rule);
	for (const command of breaks) {
		const json = JSON.stringify({ command });
		expect({ command, fires: matches(patterns, json).whole }).toEqual({ command, fires: true });
	}
	for (const command of follows) {
		const seen = matches(patterns, JSON.stringify({ command }));
		expect({ command, ...seen }).toEqual({ command, whole: false, prefix: false });
	}
}

test("worktree-beside-repo stops a worktree inside a checkout, however spelled, and only that", () => {
	check(
		"worktree-beside-repo",
		[
			"git worktree add --no-track -b feat/fix .worktrees/fix origin/main",
			"git worktree add .claude/worktrees/fix",
			'git worktree add -b feat/fix ".worktrees/fix" origin/main',
			"git worktree add -b feat/fix '.worktrees/fix' origin/main",
			'git worktree add ".claude/worktrees/my fix"',
			'git worktree add -b "feat/fix" ".worktrees/fix"',
			"git worktree add -- .worktrees/fix",
			"git worktree add \\\n  -b feat/fix .worktrees/fix origin/main",
			"git worktree add -b feat/fix .worktrees/fix\\\n  origin/main",
		],
		[
			"git -C shop-api worktree add -b feat/fix ../shop-api-fix origin/main",
			"git worktree add -q -b chore/fix ../shop-api-fix HEAD",
			"git worktree add --no-checkout ../shop-api-fix HEAD",
			"git worktree add -b feat/fix ../shop-api-fix",
			'git -C shop-api worktree add -b feat/fix "../shop-api-fix" origin/main',
			"git worktree add -b feat/fix '../shop-api-fix' HEAD",
			'git worktree add -b "feat/fix" "../shop api fix"',
			"git worktree add \\\n  -b feat/fix ../shop-api-fix \\\n  origin/main",
			"git worktree add -- ../shop-api-fix",
		],
	);
});

test("nix-copies-folder stops Nix being handed a folder, not a git reference", () => {
	check(
		"nix-copies-folder",
		[
			"nix build path:$PWD#app",
			"nix flake lock --override-input data path:../data",
			"nix eval --impure --expr '(builtins.getFlake (toString ./.)).outputs'",
			`nix eval --expr '(builtins.getFlake "/home/user/repo")'`,
			"nix eval --expr '(builtins.getFlake\n  (toString ./.))'",
		],
		[
			"nix build .#tools -o result",
			"nix build 'git+file:///home/user/repo?rev=abc'#app",
			`nix eval --expr '(builtins.getFlake "git+file:///home/user/repo?rev=abc")'`,
			"rg 'path:' docs/",
		],
	);
	// A .nix edit is checked on the source it writes, not on JSON.
	const patterns = conditions("nix-copies-folder");
	expect(matches(patterns, 'inputs.data.url = "path:../data";').whole).toBe(true);
	expect(matches(patterns, 'inputs.data.url = "github:owner/data";').whole).toBe(false);
});
