"""commitment_anchor checker for the OBS-06 draft (stdlib only).

For each vector: (1) recompute the record's digest under the declared digest_rule and require it to equal
commitment_anchor.digest; (2) decide whether precedence is established: anchor_time + anchor_time_tolerance_s
strictly before outcome_time; (3) check the record's own claim: it may assert precedence only if established,
and if not established it must list "precedence_before_outcome" in does_not_assert.

What this does NOT check: that the proof really commits the digest at anchor_time. Run the mechanism's own
verifier for that (for the OpenTimestamps vectors: `ots verify -d <digest> 38.ots`, then compare the block time).
Usage: python3 check.py [vectors.json]
"""
import hashlib, json, sys

def digest_of(record):
    rule = record["commitment_anchor"]["digest_rule"]
    if rule == "nip01-event-id":
        e = record["subject"]
        ser = json.dumps([0, e["pubkey"], e["created_at"], e["kind"], e["tags"], e["content"]],
                         separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(ser.encode("utf-8")).hexdigest()
    raise ValueError(f"unsupported digest_rule {rule}")

def evaluate(record):
    a = record["commitment_anchor"]
    if digest_of(record) != a["digest"]:
        return {"result": "ANCHOR_DOES_NOT_COVER_RECORD", "precedence_established": False}
    established = a["anchor_time"] + a["anchor_time_tolerance_s"] < record["outcome_time"]
    asserts = record.get("asserts_precedence", False)
    declared = "precedence_before_outcome" in record.get("does_not_assert", [])
    if asserts and not established:
        res = "NONCONFORMING_UNSUPPORTED_PRECEDENCE_CLAIM"
    elif not established and not declared:
        res = "NONCONFORMING_UNDECLARED_LIMITATION"
    else:
        res = "CONFORMING"
    return {"result": res, "precedence_established": established}

def main(path):
    vectors = json.load(open(path))["vectors"]
    ok = 0
    for v in vectors:
        got = evaluate(v["record"])
        good = got == v["expect"]
        ok += good
        print(f"{'ok  ' if good else 'FAIL'} {v['id']:<40} {got['result']:<44} established={got['precedence_established']}")
    print(f"{ok}/{len(vectors)} agree")
    return 0 if ok == len(vectors) else 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "vectors.json"))
