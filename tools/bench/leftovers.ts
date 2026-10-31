// What a run leaves running after omp exits: servers and workers the agent started, and omp's own
// daemons (its service broker and kernels start in sessions of their own). They are stopped before
// the run's files are copied, so nothing changes the project while it is, and none outlive the
// sandbox. A leftover is in omp's process group (omp is started as its leader) or was started
// with the sandbox's HOME, which every process the agent starts inherits; another run's sandbox
// has another HOME and group. Lists processes with macOS's /bin/ps (the sandboxes are this Mac's).

/** Whose leftovers: omp's process group, the sandbox's HOME, and the runner, which is never one. */
export interface Owner {
	pgid: number;
	home: string;
	self: number;
}

/**
 * The live processes in `ps`, the output of `ps -A -E -ww -o pid=,pgid=,state=,command=` (the
 * command followed by the environment), that are `owner`'s leftovers. Zombies are already dead.
 */
export function leftoverPids(ps: string, owner: Owner): number[] {
	const pids: number[] = [];
	for (const line of ps.split("\n")) {
		const match = /^\s*(\d+)\s+(\d+)\s+(\S+)\s(.*)$/.exec(line);
		if (!match || match[3]?.startsWith("Z")) continue;
		const pid = Number(match[1]);
		const inSandbox = ` ${match[4]} `.includes(` HOME=${owner.home} `);
		if (pid !== owner.self && (Number(match[2]) === owner.pgid || inSandbox)) pids.push(pid);
	}
	return pids;
}

async function list(owner: Owner): Promise<number[]> {
	const argv = ["/bin/ps", "-A", "-E", "-ww", "-o", "pid=,pgid=,state=,command="];
	const proc = Bun.spawn(argv, { stdin: "ignore", stdout: "pipe", stderr: "pipe" });
	const [out, err, code] = await Promise.all([
		new Response(proc.stdout).text(),
		new Response(proc.stderr).text(),
		proc.exited,
	]);
	if (code !== 0) throw new Error(`${argv.join(" ")} exited ${code}: ${err.trim()}`);
	return leftoverPids(out, owner);
}

/** Sends `signal` to `target` (a pid, or a negated process group); one already gone is fine. */
export function signal(target: number, sig: NodeJS.Signals): void {
	try {
		process.kill(target, sig);
	} catch (error) {
		if (!(error instanceof Error && "code" in error && error.code === "ESRCH")) throw error;
	}
}

/** Stops `owner`'s leftovers: SIGTERM, then SIGKILL to those still running after `graceMs`. How many there were. */
export async function stopLeftovers(owner: Owner, graceMs: number): Promise<number> {
	const found = await list(owner);
	for (const pid of found) signal(pid, "SIGTERM");
	const deadline = Date.now() + graceMs;
	let left = found.length > 0 ? await list(owner) : [];
	while (left.length > 0 && Date.now() < deadline) {
		await Bun.sleep(100);
		left = await list(owner);
	}
	for (const pid of left) signal(pid, "SIGKILL");
	return found.length;
}
