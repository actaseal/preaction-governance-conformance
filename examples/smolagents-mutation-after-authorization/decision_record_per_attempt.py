#!/usr/bin/env python3
"""One decision record per tool-call attempt, allowed OR denied -- smolagents#2117
(the denial-side gap named in this thread on 2026-10-11, and Kaelenx's
2026-10-15 question: how to identify individual callable attempts when one
CodeAgent step makes several tool calls).

full_receipt_adversarial_matrix.py binds only AUTHORIZED calls. This file
emits the same preimage (tool, JCS args, agent_id, policy_version) for every
attempt, with allowed / reason / decider added, at decision time, before the
tool body runs. The guard sits at the callable boundary (see
callable_boundary_vs_dispatch_boundary.py), so both dispatch shapes produce
records.

Correlation. ToolCallingAgent gets a tool_call.id from the model; CodeAgent's
generated code calls tools as plain Python functions and nothing upstream
names each call. So the guard names it:

    attempt_id = sha256(JCS({run_id, step, call_index}))

call_index is a per-step counter incremented by the guard itself on every
entry to any guarded callable, before the decision. It counts attempts in
execution order, including denied ones and calls made inside loops, which a
static count of the generated code cannot do. Where the model supplied a
tool_call_id it is recorded alongside, not used instead.

Each record also carries prev = hash of the previous record in the run. A
verifier holding the chain can tell when a record was dropped or reordered,
which is what makes "before = N, after denied = N" countable from the log
alone: executions = records with allowed=true, attempts = chain length.

Zero dependencies, never imports smolagents. ASCII/int JCS only (same
disclosed limit as the sibling files).
"""
import hashlib
import json


def jcs(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def h(obj) -> str:
    return hashlib.sha256(jcs(obj)).hexdigest()


class Denied(Exception):
    def __init__(self, record):
        super().__init__(record["reason"])
        self.record = record


class AttemptGuard:
    def __init__(self, run_id, agent_id, policy_version, policy):
        self.run_id, self.agent_id, self.policy_version = run_id, agent_id, policy_version
        self.policy = policy  # (tool, args) -> (allowed, reason)
        self.step = 0
        self.call_index = 0
        self.records = []
        self.executions = 0

    def new_step(self):
        self.step += 1
        self.call_index = 0

    def _decide(self, tool, args, tool_call_id=None):
        attempt = {"run_id": self.run_id, "step": self.step, "call_index": self.call_index}
        self.call_index += 1
        allowed, reason = self.policy(tool, args)
        rec = {
            "attempt_id": h(attempt), **attempt,
            "tool_call_id": tool_call_id,
            "preimage_hash": h({"tool_hash": hashlib.sha256(tool.encode()).hexdigest(),
                                "args_hash": h(args), "agent_id": self.agent_id,
                                "policy_version": self.policy_version}),
            "tool": tool, "args": args, "agent_id": self.agent_id,
            "policy_version": self.policy_version,
            "allowed": allowed, "reason": reason, "decider": "AttemptGuard/v1",
            "prev": h(self.records[-1]) if self.records else None,
        }
        self.records.append(rec)  # written before the tool body can run
        return rec

    def wrap(self, name, fn):
        def guarded(*, _tool_call_id=None, **kwargs):
            rec = self._decide(name, kwargs, _tool_call_id)
            if not rec["allowed"]:
                raise Denied(rec)
            self.executions += 1
            return fn(**kwargs)
        return guarded


def observation(rec):
    """Structured denial observation returned to the agent; 1:1 with a record."""
    return {"denied": True, "attempt_id": rec["attempt_id"], "tool": rec["tool"],
            "reason": rec["reason"], "policy_version": rec["policy_version"]}


def verify_chain(records):
    prev = None
    for r in records:
        if r["prev"] != prev:
            return False
        prev = h(r)
    return True


def main():
    def policy(tool, args):  # read-only grant as a capability set
        return (tool in {"read_balance"}, "ok" if tool == "read_balance" else "capability: read-only")

    g = AttemptGuard("run-1", "support-agent-1", "v3", policy)
    tools = {"read_balance": g.wrap("read_balance", lambda customer: 42),
             "refund": g.wrap("refund", lambda customer, amount: f"refunded {amount}")}
    alias = tools["refund"]  # generated code may rebind a tool; same guarded callable

    # Step 1, CodeAgent-shaped: one code block, four calls incl. a loop and an alias.
    g.new_step()
    obs = []
    tools["read_balance"](customer="A")
    for amt in (100, 1000):
        try:
            tools["refund"](customer="A", amount=amt)
        except Denied as e:
            obs.append(observation(e.record))
    try:
        alias(customer="B", amount=5)
    except Denied as e:
        obs.append(observation(e.record))

    # Step 2, ToolCallingAgent-shaped: model-supplied ids recorded alongside.
    g.new_step()
    tools["read_balance"](customer="A", _tool_call_id="call_abc")
    try:
        tools["refund"](customer="A", amount=100, _tool_call_id="call_def")
    except Denied as e:
        obs.append(observation(e.record))

    recs = g.records
    checks = [
        ("6 attempts -> 6 records", len(recs) == 6),
        ("executions == allowed records == 2", g.executions == sum(r["allowed"] for r in recs) == 2),
        ("denied attempts == 4 == observations", len(obs) == 4 == sum(not r["allowed"] for r in recs)),
        ("step 1 call_index 0..3 in execution order", [r["call_index"] for r in recs[:4]] == [0, 1, 2, 3]),
        ("loop calls with same tool get distinct attempt_ids", recs[1]["attempt_id"] != recs[2]["attempt_id"]),
        ("all attempt_ids unique", len({r["attempt_id"] for r in recs}) == 6),
        ("call_index resets per step", recs[4]["step"] == 2 and recs[4]["call_index"] == 0),
        ("model tool_call_id recorded, not substituted", recs[5]["tool_call_id"] == "call_def"
            and recs[5]["attempt_id"] == h({"run_id": "run-1", "step": 2, "call_index": 1})),
        ("every observation maps to exactly one record",
            all(sum(r["attempt_id"] == o["attempt_id"] for r in recs) == 1 for o in obs)),
        ("chain verifies", verify_chain(recs)),
        ("dropping a denied record breaks the chain", not verify_chain(recs[:2] + recs[3:])),
        ("reordering breaks the chain", not verify_chain([recs[1], recs[0]] + recs[2:])),
    ]
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    assert all(ok for _, ok in checks)
    print("\nsample denial record:")
    print(json.dumps({k: recs[2][k] for k in ("attempt_id", "step", "call_index", "tool", "args",
                                                "allowed", "reason", "decider", "policy_version")}, indent=1))


if __name__ == "__main__":
    main()
