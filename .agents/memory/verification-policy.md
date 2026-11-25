---
name: Continue demo verification without live credentials
description: Owner-approved boundary between demo development and deferred live SQL verification.
---

Unavailable real SQL Server connection details must not block development and
testing in the existing demo environment. Use the existing mock repository
where appropriate, and explicitly distinguish demo-verified behavior from checks
that require the real database. Never invent or assume credentials.

**Why:** The owner explicitly authorized continuing all role-based and UI testing
without the unavailable live database, instead of blocking the project on access.

**How to apply:** Continue demo work independently; report live SQL verification
as deferred until approved secure access exists, never as proven by mock tests.
