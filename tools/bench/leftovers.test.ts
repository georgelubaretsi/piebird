import { afterEach, describe, expect, test } from "bun:test";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { leftoverPids, signal, stopLeftovers } from "./leftovers";

const owner = { pgid: 500, home: "/tmp/omp-demo-a/home", self: 400 };

describe("leftoverPids", () => {
	test("takes omp's group and processes started with the sandbox's HOME, nothing else", () => {
		const ps = [
			"  500   500 Ss   omp -p -- fix it HOME=/tmp/omp-demo-a/home PATH=/bin",
			"  501   500 S    sleep 300 PATH=/bin",
			"  600   600 Ss   bun broker.ts A=1 HOME=/tmp/omp-demo-a/home",
			"  601   601 Ss   bun server.ts HOME=/tmp/omp-demo-a/home",
			"  700   700 Ss   omp -p -- other HOME=/tmp/omp-demo-b/home",
			"  701   701 S    sleep 9 HOME=/tmp/omp-demo-a/home2",
			"  702   702 S    sleep 9 HOME=/tmp/omp-demo-a",
			"  400   500 S    bun run.ts HOME=/tmp/omp-demo-a/home",
			"  502   500 Z    (sleep)",
			"",
		].join("\n");
		expect(leftoverPids(ps, owner)).toEqual([500, 501, 600, 601]);
	});
});

const alive = (pid: number) => {
	try {
		process.kill(pid, 0);
		return true;
	} catch {
		return false;
	}
};
/** Whether `pid`, not this process's child, is gone within a second (launchd reaps it). */
async function gone(pid: number): Promise<boolean> {
	for (let i = 0; i < 20 && alive(pid); i++) await Bun.sleep(50);
	return !alive(pid);
}

// The real thing on this Mac: /bin/ps -E is macOS's.
describe.skipIf(process.platform !== "darwin")("stopLeftovers", () => {
	const homes: string[] = [];
	afterEach(async () => {
		await Promise.all(homes.splice(0).map(home => rm(home, { recursive: true, force: true })));
	});

	test("stops what the leader left in its group and what runs with the sandbox's HOME, not another run's", async () => {
		const home = await mkdtemp(join(tmpdir(), "bench-leftovers-"));
		homes.push(home);
		const env = { ...process.env, HOME: home };
		// The leader (omp) starts a grandchild in its group and exits; the grandchild leaves its stdout.
		const leader = Bun.spawn(["sh", "-c", "sleep 300 >/dev/null & echo $!"], { env, detached: true, stdout: "pipe" });
		const grandchild = Number((await new Response(leader.stdout).text()).trim());
		await leader.exited;
		// A daemon in a session of its own, as omp's service broker is.
		const daemon = Bun.spawn(["sleep", "301"], { env, detached: true });
		const otherRun = Bun.spawn(["sleep", "302"], { env: { ...process.env, HOME: `${home}-other` }, detached: true });
		try {
			const found = await stopLeftovers({ pgid: leader.pid, home, self: process.pid }, 2000);
			expect(found).toBe(2);
			expect(await gone(grandchild)).toBe(true);
			expect(await daemon.exited).toBe(143);
			expect(alive(otherRun.pid)).toBe(true);
		} finally {
			signal(grandchild, "SIGKILL");
			daemon.kill("SIGKILL");
			otherRun.kill("SIGKILL");
		}
	});

	test("kills one that ignores SIGTERM after the grace time", async () => {
		const home = await mkdtemp(join(tmpdir(), "bench-leftovers-"));
		homes.push(home);
		const stubborn = Bun.spawn(["sh", "-c", "trap '' TERM; echo ready; while :; do sleep 0.05; done"], {
			env: { ...process.env, HOME: home },
			detached: true,
			stdout: "pipe",
		});
		try {
			// Signalled only once the trap is set.
			await stubborn.stdout.getReader().read();
			const started = Date.now();
			await stopLeftovers({ pgid: stubborn.pid, home, self: process.pid }, 500);
			expect(await stubborn.exited).toBe(137);
			expect(Date.now() - started).toBeGreaterThanOrEqual(500);
		} finally {
			stubborn.kill("SIGKILL");
		}
	});
});
