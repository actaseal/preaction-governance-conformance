#!/usr/bin/env python3
"""Offline check of the ACG profile vectors (acg_vectors.json). Trusts neither the presenter nor our API.

Per case:
  1. quote     quoteDigest present -> NAMED (verify the 8409 envelope itself with ../check.py); null -> NOT_ESTABLISHED, never a pass
  2. request   sha256(invoke body bytes you hold) == request.invokeBodySha256
  3. backend   sha256(backendBody) == backendBodySha256 and sha256(JCS(parsed backendBody)) == bodyJcsSha256
  4. binding   sha256(JCS(deliveryRecord)) == the proof's signed artifact_hash == receipt deliveryRecordSha256
  5. proof     NIP-01 id recomputes, BIP-340 signature verifies, pubkey == the published verifier key
  6. verdict   receipt verdict == the signed verdict
  7. delivered sha256(delivered bytes you hold) == deliveredBodySha256; then deliveredBodyJcsSha256 == bodyJcsSha256 means ACG changed formatting
               only (COVERED: the verdict on the backend bytes covers what the agent got); unequal means content changed after the backend
               (NOT_COVERED: the verdict says nothing about what the agent received)
Expected: delivered_reserialized and no_quote_yet COVERED (no_quote_yet with the quote step NOT_ESTABLISHED), gateway_altered NOT_COVERED,
and the mutation self-tests each fail exactly the step they target.
"""
import copy, hashlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..")); sys.path.insert(0, os.path.join(HERE, "..", "..", ".."))
from _bip340_nostr import schnorr_verify, nostr_event_id   # noqa: E402
import rfc8785                                             # noqa: E402

PUB = json.load(open(os.path.join(HERE, "..", "vectors.json")))["verifier_pubkey"]
h = lambda b: hashlib.sha256(b).hexdigest()


def check(c, invoke_body, delivered=None):
    rec, m = c["deliveryRecord"], c["receiptMetadata"]["deliveryVerdict"]
    quote = "NAMED" if rec["quote"].get("quoteDigest") else "NOT_ESTABLISHED"
    if h(invoke_body) != rec["request"]["invokeBodySha256"]:
        return "FAIL 2 request", quote
    raw = rec["response"]["backendBody"].encode()
    if h(raw) != rec["response"]["backendBodySha256"] or h(rfc8785.dumps(json.loads(raw))) != rec["response"]["bodyJcsSha256"]:
        return "FAIL 3 backend", quote
    ev = m["proof"]; payload = json.loads(ev["content"]); rh = h(rfc8785.dumps(rec))
    if rh != payload.get("artifact_hash") or rh != m["deliveryRecordSha256"]:
        return "FAIL 4 binding", quote
    if nostr_event_id(ev) != ev["id"] or ev["id"] != m["proofEventId"] or ev["pubkey"] != PUB or \
            not schnorr_verify(bytes.fromhex(ev["id"]), bytes.fromhex(ev["pubkey"]), bytes.fromhex(ev["sig"])):
        return "FAIL 5 proof", quote
    if payload.get("verdict") != m["verdict"]:
        return "FAIL 6 verdict", quote
    dl = (delivered if delivered is not None else c["deliveredBody"]).encode()
    if h(dl) != m["deliveredBodySha256"]:
        return "FAIL 7 delivered bytes", quote
    covered = h(rfc8785.dumps(json.loads(dl))) == m["deliveredBodyJcsSha256"] == rec["response"]["bodyJcsSha256"]
    return ("COVERED" if covered else "NOT_COVERED") + f" ({m['verdict']})", quote


def main():
    V = json.load(open(os.path.join(HERE, "acg_vectors.json")))
    inv = V["invokeBody"].encode()
    want = {"delivered_reserialized": ("COVERED", "NAMED"), "gateway_altered": ("NOT_COVERED", "NAMED"),
            "no_quote_yet": ("COVERED", "NOT_ESTABLISHED")}
    ok = True
    for k, c in V["cases"].items():
        res, q = check(c, inv)
        good = res.startswith(want[k][0] + " ") and q == want[k][1]
        ok &= good
        print(f"{'ok  ' if good else 'FAIL'} {k:24s} {res:42s} quote={q}")
    base = V["cases"]["delivered_reserialized"]
    muts = [("2 request", lambda c: (c, b'{"city":"Lima","days":7}', None)),
            ("3 backend", lambda c: (dict(c, deliveryRecord={**c["deliveryRecord"], "response": {**c["deliveryRecord"]["response"], "backendBody": c["deliveryRecord"]["response"]["backendBody"].replace("Santiago", "Lima")}}), inv, None)),
            ("4 binding", lambda c: (dict(c, deliveryRecord={**c["deliveryRecord"], "question": c["deliveryRecord"]["question"] + " "}), inv, None)),
            ("5 proof", lambda c: (dict(c, receiptMetadata={"deliveryVerdict": {**c["receiptMetadata"]["deliveryVerdict"], "proof": {**c["receiptMetadata"]["deliveryVerdict"]["proof"], "sig": "00" * 64}}}), inv, None)),
            ("6 verdict", lambda c: (dict(c, receiptMetadata={"deliveryVerdict": {**c["receiptMetadata"]["deliveryVerdict"], "verdict": "reject"}}), inv, None)),
            ("7 delivered bytes", lambda c: (c, inv, c["deliveredBody"] + " "))]
    for step, f in muts:
        c2, i2, d2 = f(copy.deepcopy(base))
        res, _ = check(c2, i2, d2)
        good = res == f"FAIL {step}"
        ok &= good
        print(f"{'ok  ' if good else 'FAIL'} mutation {step:18s} -> {res}")
    print("ALL PASS" if ok else "FAILURES")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
