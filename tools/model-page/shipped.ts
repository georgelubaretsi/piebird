// The skills and rules a plugin ships as files, for its "what the model sees" page. Every harness
// reads a plugin's skills itself: each lists a skill's name and description, and the agent reads
// the whole SKILL.md (and the files it points to) when the description fits the task. Rules are
// omp's: an always-applied rule's body is in the system prompt of the agents it is for (every agent
// without `agents`); a rule with a `condition` (TTSR) is in no prompt, and omp gives its body when
// a call it watches matches; any other rule is a line in those agents' rules list whose body
// rule:// reads. Where a plugin gives Claude Code or Codex its rules, its shell does, and the
// scripted session shows it.
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, sep } from "node:path";
import { isObject } from "../build/json";
import { readFrontmatter } from "../build/parse";
import { fenced } from "./render";

function frontAndBody(file: string): { front: Readonly<Record<string, unknown>>; body: string } {
	const problems: string[] = [];
	const parsed = readFrontmatter(file, readFileSync(file, "utf8"), problems);
	if (parsed === undefined || !isObject(parsed.value) || problems.length > 0)
		throw new Error(problems.join("; ") || `${file}: front matter is not a map`);
	return { front: parsed.value, body: parsed.body.trim() };
}

const text = (value: unknown): string => (typeof value === "string" ? value : "");

function skills(plugin: string): string[] {
	const dir = join(plugin, "skills");
	if (!existsSync(dir)) return [];
	const names = readdirSync(dir, { withFileTypes: true }).filter(entry => entry.isDirectory());
	return names
		.map(entry => entry.name)
		.toSorted()
		.flatMap(name => {
			const folder = join(dir, name);
			const skill = join(folder, "SKILL.md");
			const others = readdirSync(folder, { recursive: true, encoding: "utf8" })
				.filter(file => file.endsWith(".md") && file !== "SKILL.md")
				.toSorted()
				.flatMap(file => [
					`**\`${file.split(sep).join("/")}\`**, where the skill points to it:`,
					"",
					fenced(readFileSync(join(folder, file), "utf8").trimEnd()),
				]);
			return [
				`### Skill \`${name}\``,
				"",
				`In the skills list: \`${name}\`: ${text(frontAndBody(skill).front.description)}`,
				"",
				"The whole `SKILL.md`, which the agent reads when the description fits its task:",
				"",
				fenced(readFileSync(skill, "utf8").trimEnd()),
				...others,
			];
		});
}

/** Whose prompt or calls a rule reaches, from its `agents` (absent: every agent's). */
function audience(agents: unknown): string {
	const named = list(agents);
	return named.length === 0 ? "every omp agent" : `omp's ${named.join(" and ")} agent`;
}

/** A front matter value that YAML gives as a string or a list of them. */
function list(value: unknown): string[] {
	return typeof value === "string" ? [value] : Array.isArray(value) ? value.map(text) : [];
}

/** Where omp puts the rule `name`, from its front matter. */
function placement(name: string, front: Readonly<Record<string, unknown>>): string {
	if (front.alwaysApply === true)
		return `In the system prompt of ${audience(front.agents)}, without its front matter:`;
	if (front.condition !== undefined) {
		const watched = list(front.scope).join(", ") || "text and tool calls";
		const conditions = list(front.condition)
			.map(condition => `\`${condition}\``)
			.join(", ");
		return `In no prompt: omp watches ${watched} of ${audience(front.agents)} for ${conditions}, stops a matching call before it runs and gives the agent its body:`;
	}
	return `In the rules list of ${audience(front.agents)} (\`${name}\`: ${text(front.description)}); \`rule://${name}\` reads its body:`;
}

function rules(plugin: string): string[] {
	const dir = join(plugin, "rules");
	if (!existsSync(dir)) return [];
	return readdirSync(dir)
		.filter(file => file.endsWith(".md"))
		.toSorted()
		.flatMap(file => {
			const { front, body } = frontAndBody(join(dir, file));
			const name = file.slice(0, -3);
			return [`### Rule \`${name}\``, "", placement(name, front), "", fenced(body)];
		});
}

/** The page's section on the plugin at `plugin` (its folder): its skills and rules, or "" without any. */
export function shippedSection(plugin: string): string {
	const lines = [...skills(plugin), ...rules(plugin)];
	if (lines.length === 0) return "";
	const intro = [
		"## Skills and rules",
		"",
		"Files the plugin ships, which the harnesses read themselves. Each harness the plugin runs in lists",
		"each skill by its name and description, and the agent reads the whole file when the description",
		"fits its task. Rules are omp's; where Claude Code or Codex gets a rule, the plugin's shell gives",
		"it, as the steps above show.",
		"",
	];
	return [...intro, ...lines].join("\n");
}
