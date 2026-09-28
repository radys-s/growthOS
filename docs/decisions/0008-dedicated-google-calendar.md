# ADR 0008: Dedicated calendar and three-way synchronization

Status: accepted, 2026-09-28.

V2 creates a secondary Google calendar for growthOS using only the
`https://www.googleapis.com/auth/calendar.app.created` scope. The integration stores its calendar
ID and event IDs. It never lists or modifies personal calendars. OAuth uses state and PKCE;
refresh and access tokens are protected by Windows DPAPI for the account running the backend.
They are absent from responses, Git and application logs. Calendar API calls use the official
Google endpoints. Live authorization requires the user's OAuth client and account.

Only explicitly scheduled work blocks synchronize. Projected or unpublished opportunity deadlines
do not become calendar events. Each event has a private growthOS plan marker, which is checked
before edits. On each run, the system compares local fields and Google fields with the last
acknowledged common value. Single-sided edits win; dual edits create a visible conflict. The user
chooses which value to keep, and stale choices are rejected. Google deletion clears the schedule
only. Completion status, decision history and evidence remain.

Event IDs are saved before network writes, so a lost response can be retried without duplicating
events. Calendar creation is marked pending before the request. If its response is lost, the user
can recover it by entering the ID from Google settings; the marker in its description must match.
An explicitly confirmed replacement is available for a deleted calendar. The local app runs with
one backend worker and a process-wide write lock. Multi-worker deployment would require a database
lock or versioned compare-and-swap before it can safely synchronize.
