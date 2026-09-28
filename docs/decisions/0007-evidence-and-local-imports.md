# ADR 0007: Confirmed evidence and local imports

Status: accepted, 2026-09-28.

V2 imports text PDF, DOCX, pasted CV text and selected public GitHub repositories. Parsing is
local and rule-based. No imported text or repository content goes to OmniRoute. PDFs without an
extractable text layer require pasted text. The GitHub adapter reads public metadata, README and
selected dependency manifests through the official API; it never executes project code.

An import creates a proposal with its source reference and a preserved excerpt. Proposals are
editable in the UI. The user must confirm the final profile item. A dependency or README mention
is a claim, not proof of mastery, deployment or research success. Only confirmed items marked
`demonstrated` contribute to the signal coverage. Manual items remain confirmed, preserving the
existing M1/V1 profile. Repeated confirmation uses an import fingerprint; completion uses a target
key. The schema adds columns and tables without replacing existing profile data.

Personal CV excerpts remain in the local database, including unconfirmed proposals; the user
should protect and back up that database. The 5 MB file cap, 100 line proposal cap and 100 kB
text cap limit resources. Scanned PDF OCR and private GitHub access are outside V2.

Decision history is append-only. Undo appends a reversal; completed evidence survives a reversal.
Progress snapshots record the signal coverage before and after confirmed profile changes. Newly
discovered recommendations and explicitly useful feedback are separate measurements.
