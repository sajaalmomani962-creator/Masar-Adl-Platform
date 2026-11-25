---
name: Browser PDF verification
description: Distinguish headless viewer and MIME limitations from document-service failures during demo testing.
---

Do not relax PDF MIME checks, authorization, or the content-security policy merely
to make a browser-test harness display or upload a PDF.

**Why:** An authenticated demo journey showed that the headless browser blocked
its embedded PDF viewer despite receiving valid authorized PDF bytes. Its
path-based upload also initially supplied a generic binary MIME type; the same
file succeeded through the actual form when correctly labeled as a PDF.

**How to apply:** Check the authorized PDF response, file signature and status
separately from native viewer rendering. Use the protected standalone print link
when embedding is unavailable, and report physical printing as unverified unless
it was actually exercised. Test malformed uploads without weakening validation.
