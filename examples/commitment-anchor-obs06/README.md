# commitment_anchor: draft OBS-06 text and conformance vectors

Proposed for [raknor-ai/agent-governance-standard#2](https://github.com/raknor-ai/agent-governance-standard/issues/2) (v1.1, Observability evidence field set). CC0-1.0.

## Problem

A timestamp written by the recording party is set by the party being assessed. A record written, or rewritten, after its outcome is known passes integrity checks and every other field in the set. An agent that logged its authorization after seeing the result looks the same as one that logged it before.

## Draft text (OBS-06, evidence field set)

**commitment_anchor** (RECOMMENDED; REQUIRED for any record that asserts it existed before its outcome).
A commitment of the record to a clock the recording party does not control. It contains:

- `mechanism`: the anchor type, for example `rfc3161`, `transparency-log` or `opentimestamps-bitcoin`.
- `digest` and `digest_rule`: the digest that was anchored, and how a verifier recomputes it from the record.
- `proof_ref`: where the proof can be retrieved. Verifying the proof MUST NOT require trusting the recording party.
- `anchor_time`: the time the proof attests, as the mechanism reports it.
- `anchor_time_tolerance_s`: the mechanism's timing uncertainty. For example, the TSA's stated accuracy for RFC 3161. For Bitcoin, a block's header time may be up to about two hours later than real time, so 7200.

**Rule.** A record MAY assert that it existed before its outcome only if `anchor_time + anchor_time_tolerance_s` is strictly earlier than the outcome time. Otherwise:

- the record MUST NOT assert precedence; and
- it MUST list `precedence_before_outcome` in `does_not_assert`, so the limitation is declared rather than silently absent (the same move `coverage_denominator` makes for completeness).

A record whose anchored digest does not recompute from the record has no anchor for this rule.

The field is mechanism-neutral. Any externally verifiable existence proof satisfies it, at different cost and trust points.

## Vectors

`vectors.json` has the requested pair and four negative controls. `check.py` is stdlib only:

```
python3 check.py            # 6/6 agree
ots verify -d a42205d7e39c684f0aa43f80fe7ea1aa8e180df93ff46e82b5bff95b70c663e9 38.ots
# Success! Bitcoin block 955810 attests existence as of 2026-06-28 UTC
```

| id | what it pins | expected |
|---|---|---|
| `anchor-before-outcome` | real anchor 2026-06-28 (block 955810), real outcome 2026-07-03 | CONFORMING, precedence established |
| `anchor-after-outcome-declared` | same anchor, outcome before it, limitation declared | CONFORMING, not established |
| `control-claims-precedence-after-outcome` | late anchor, but the record claims precedence | NONCONFORMING_UNSUPPORTED_PRECEDENCE_CLAIM |
| `control-late-anchor-silent` | late anchor, limitation not declared | NONCONFORMING_UNDECLARED_LIMITATION |
| `control-outcome-inside-tolerance` | outcome 1 h after the block time, inside the 2 h tolerance | NONCONFORMING_UNSUPPORTED_PRECEDENCE_CLAIM |
| `control-anchor-does-not-cover-record` | one word of the record changed after anchoring | ANCHOR_DOES_NOT_COVER_RECORD |

Each control is load-bearing. Removing any one of these from `check.py` makes at least one vector fail:

- the tolerance;
- the digest recompute;
- the undeclared-limitation check;
- the unsupported-claim check.

## Sources and limits

- The record is entry 38 of a public verdict ledger (a signed pre-action verdict; digest = its NIP-01 event id). Its OpenTimestamps proof is `38.ots`, also served at `https://api.babyblueviper.com/ledger/38/ots`.
- The second vector and the controls reuse that real anchor. Their outcome times are **synthetic**, chosen to land before or just after the anchor. The real "after" cases on that ledger are trading records, kept out of a standards corpus on purpose.
- `check.py` evaluates the rule. It does not verify the proof itself: run the mechanism's own verifier (`ots verify`, an RFC 3161 client, an inclusion-proof checker) and compare its attested time to `anchor_time`.
- Disclosure: we operate that ledger. The field and the rule do not depend on it.
