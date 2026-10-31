import { afterEach, expect, test } from "bun:test";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { concatJournals } from "./job";

const roots: string[] = [];
afterEach(async () => {
	await Promise.all(roots.splice(0).map(root => rm(root, { recursive: true, force: true })));
});

async function tree(files: Record<string, string>): Promise<string> {
	const root = await mkdtemp(join(tmpdir(), "bench-journal-"));
	roots.push(root);
	for (const [path, text] of Object.entries(files)) {
		await mkdir(dirname(join(root, path)), { recursive: true });
		await writeFile(join(root, path), text);
	}
	return root;
}

test("joins every journal under the folder, subagents' included, in path order", async () => {
	const root = await tree({
		"b-project/2.jsonl": "b2\n",
		"a-project/1.jsonl": "a1\n",
		"a-project/1/sub/agent.jsonl": "sub\n",
		"a-project/notes.txt": "not a journal\n",
		"A-upper/0.jsonl": "upper\n",
	});
	expect(await concatJournals(root)).toBe("upper\na1\nsub\nb2\n");
});

test("ends a journal's last line so the next journal's first line stays apart", async () => {
	const root = await tree({ "p/1.jsonl": '{"a":1}', "p/2.jsonl": '{"b":2}\n', "p/3.jsonl": "" });
	expect(await concatJournals(root)).toBe('{"a":1}\n{"b":2}\n');
});

test("no sessions folder, no journal", async () => {
	expect(await concatJournals(join(tmpdir(), "bench-journal-missing", "sessions"))).toBe("");
});
