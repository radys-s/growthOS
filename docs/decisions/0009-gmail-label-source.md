# ADR 0009: Gmail as a label-scoped, verified source

Status: accepted, 2026-09-30. Amends ADR 0007 (imports stay local) for labelled mail only.

V3 reads Gmail through a **separate** OAuth grant with the minimal
`https://www.googleapis.com/auth/gmail.readonly` scope. It shares the PKCE/DPAPI code with the
calendar (`app/google/oauth.py`, ADR 0008) but has its own connection row, redirect URI and
revocation, so either integration can be disconnected alone. growthOS never sends, modifies,
labels or deletes mail.

**The label is the consent.** Only messages that carry the user's label (`GMAIL_LABEL`, default
`growthOS`, typically applied by a Gmail filter) and are newer than 365 days are listed; Gmail
applies the filter server-side, so unlabelled mail is never fetched. Attachments are never
downloaded. The body (plain text preferred, otherwise HTML text plus link targets) is capped to
12k characters and sent to the configured OpenAI-compatible LLM (OmniRoute, ADR 0006). This is
the one place where personal text leaves the machine; ADR 0007's "no LLM for imports" still holds
for CV and GitHub imports. Without an LLM, the Gmail step reads nothing.

The LLM only proposes. Code verifies deterministically:

- every claim needs a quote (≤400 chars) that appears verbatim in the message, else it is dropped;
- a deadline is kept only when the date is written in the quote, is in the future and at most
  550 days away; a quoted deadline that already passed drops the opportunity;
- `kind` must be a known opportunity kind; organizer, URL and achievement result are kept only
  when they appear in the message (otherwise "Neuvedeno (Gmail)", the Gmail permalink, null);
- an achievement date is kept only when it is in the quote and not in the future.

Opportunities are stored with source `gmail`, unverified eligibility and the permalink as
evidence; they are not closed by later runs. When the URL matches an open opportunity (any$
source, including an earlier mail) without a deadline, the verified deadline and quote are added
there instead of a
duplicate. Achievements become import proposals: they change nothing until the user confirms
them, and demonstrated evidence still needs an explicit result (ADR 0007).

Retention: bodies are not stored. The database keeps message ids (so each message goes to the
LLM once), verified quotes and derived items. A provider or network failure leaves the message
unmarked, so it is retried on the next run.
