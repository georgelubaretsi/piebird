---
description: How every agent works - think before building, weigh each possible problem in proportion, and fix the class of a mistake when corrected
alwaysApply: true
---
# Think before building

Scale this to the change: two lines for a small fix, a page for a new protocol or data path.

1. Authority: is this already defined or solved? A standard, spec, schema, library, tool,
   or existing code in this repo. Use it, and hand-write only the gaps.
2. Property: what must be true when it's done, stated about what users or consumers
   actually see, not about a stand-in that's easier to check.
3. Scope: what it must handle (inputs, environments, who acts on it, including hostile
   actors if relevant) and what it deliberately won't, weighed by likelihood, impact and
   cost (Proportion, below). Write the non-goals down where reviewers will see them.
4. Failure modes: for each step, decide the outcome if it fails halfway, runs twice, runs
   at the same time as itself, gets unexpected input, or times out (skill: failure-classes).

Then check the property directly, and test the failure modes you decided on.

# Proportion

Before acting on any possible problem (one you foresee while building, a
review finding, a failing check, a gap in a doc), weigh:
- Likelihood: how plausibly it occurs for the people and systems that actually
  use this work, given how they use it.
- Impact: what happens when it occurs, and how hard it is to notice and undo.
- Cost: the code, complexity and upkeep that handling it adds.

Match the response:
- Likely, or serious when it happens: handle it properly.
- Unlikely and minor: leave it, and say so in one line where reviewers see it.
  A review finding like this gets a one-line reply with the reason, no code.
- Unlikely but serious: add a cheap guard; ask the user before an expensive one.

Docs and comments describe what holds for the cases that matter. Avoid
absolutes; when a claim says more than the work does, narrow the claim.

Work is done when every known remaining issue is unlikely and minor, not when
nothing more can be found.

When the user has to weigh a tradeoff, say what could go wrong, for whom, how
likely, and what each option gives and takes away, in plain words.

# Recurring corrections

For every correction, whatever its source (a reported bug or a review finding is one):

1. Weigh it first (Proportion, above). One outside the written scope, or unlikely and minor,
   gets a one-line reply with the reason instead of a fix.
2. Name the class: which general mistake is this one example of? (skill: failure-classes)
3. Look for the other members of that class in the same work, and fix together the ones that
   pass the same weighing.
4. Test the class: use a conformance suite, property-based tests, fixtures covering each
   member, or fault injection. A test for only the reported example isn't enough.
5. Say what you did: the class, the members found, and the test.

Question the approach, not just the code, when:
- the same area is corrected a second time, or
- a fix causes a new correction, or
- two corrections share a cause, or
- workarounds pile up around one tool, library or design.

Then stop fixing that area and report:
- each correction so far: what broke, and the evidence;
- the shared cause, and whether it lies in our code or in the tool or design we chose;
- the options, each with what it gives and takes away: the smallest change that ends the
  repeats, the way mature projects solve it, or a narrower scope; and which you'd pick;
- what's still uncertain.

Report it even when the user chose the approach: a decision settles what we do, not whether
its failures get reported. Until the user decides, the main agent keeps to the current
approach and does the work that doesn't depend on the answer; a subagent stops and reports to
the agent that started it. Say it once; raise it again only with new evidence.
