"""ACG profile of the ERC-8409 delivery verdict (draft for Agent Commerce Gateway, eth-mag t/29858, 2026-10-12).

Builds the delivery records and receipt metadata for three cases -> acg_unsigned.json. The signed proofs in acg_vectors.json
come from POST /review sign=true over each distinct record's JCS bytes (artifact_hash = sha256(JCS(record))).

Binding, per what ACG has today:
  request   invokeBodySha256      sha256 of the original invoke body bytes, as ACG already digests them (exact construction: to confirm)
  response  backendBodySha256     sha256 of the backend's raw response bytes, captured before ACG parses the JSON   (new: nothing hashes it today)
            bodyJcsSha256         sha256(RFC 8785 JCS(parsed backend body)): survives ACG's parse + re-serialize
  quote     quoteDigest           the ERC-8409 digest once ACG issues quotes; null until then (the check reports the quote step as not established)
The verdict judges the BACKEND's bytes (what settlement pays for). The receipt also carries the DELIVERED body's digests (what the agent got), so
anyone holding the delivered bytes can check that ACG's re-serialization changed formatting only (equal JCS digests) or changed content.
"""
import hashlib, json
import rfc8785

h = lambda b: hashlib.sha256(b).hexdigest()
jcs = lambda o: rfc8785.dumps(o)

invoke_body = b'{"city":"Santiago","days":7}'
days = [{"date": f"2028-09-0{i+3}", "tmin_c": 6 + i, "tmax_c": 18 + i} for i in range(7)]
backend_obj = {"city": "Santiago", "days": 7, "forecast": days}
backend_raw = json.dumps(backend_obj, indent=2).encode()                       # what the backend sent: pretty-printed
delivered_ok = json.dumps(backend_obj, separators=(",", ":")).encode()         # ACG re-serialized: same content, different bytes
delivered_bad = json.dumps({**backend_obj, "forecast": days[:3]}, separators=(",", ":")).encode()   # content changed after the backend
QD = "0x48f1be2181771208981ebac78f2c01a5f224c7942e6149085c3e0f05dc81948f"     # the parent example's quote, for the quoted cases


def record(quote_digest):
    return {"scheme": "invinoveritas.delivery-record/2-acg-draft",
            "quote": {"quoteDigest": quote_digest},
            "request": {"invokeBodySha256": h(invoke_body)},
            "response": {"status": 200, "contentType": "application/json", "backendBody": backend_raw.decode(),
                         "backendBodySha256": h(backend_raw), "bodyJcsSha256": h(jcs(json.loads(backend_raw)))},
            "question": "Does this backend response deliver what the invoked request asked for?"}


def receipt_meta(rec, delivered):
    return {"deliveryVerdict": {"scheme": "invinoveritas.delivery-verdict/2-acg-draft",
                                "deliveryRecordSha256": h(jcs(rec)),
                                "deliveredBodySha256": h(delivered),
                                "deliveredBodyJcsSha256": h(jcs(json.loads(delivered)))}}


cases = {"delivered_reserialized": (record(QD), delivered_ok),
         "gateway_altered": (record(QD), delivered_bad),
         "no_quote_yet": (record(None), delivered_ok)}
out = {"invokeBody": invoke_body.decode(), "cases": {}}
for k, (rec, dlv) in cases.items():
    out["cases"][k] = {"deliveryRecord": rec, "deliveryRecordJcs": jcs(rec).decode(), "deliveredBody": dlv.decode(),
                       "receiptMetadata": receipt_meta(rec, dlv)}
json.dump(out, open("acg_unsigned.json", "w"), indent=1)
for k, v in out["cases"].items():
    print(k, v["receiptMetadata"]["deliveryVerdict"]["deliveryRecordSha256"][:16])
