---
name: Browser PDF verification limits
description: Distinguish headless viewer and MIME limitations from document-service failures and actual printing.
---

Do not describe an authorized PDF response or a visible iframe as proof that the
PDF rendered or printed successfully. Do not relax PDF MIME checks,
authorization, or the content-security policy merely to make a browser-test
harness display or upload a PDF.

**Why:** The independent authenticated browser run completed the release/print
journey, but its headless viewer showed a blocked placeholder despite the raw
PDF returning successfully. Responsive mobile Chromium also showed an empty
viewer. The browser's PDF viewer, not only application authorization, determines
whether embedded printing is usable. The harness's path-based upload also
initially supplied a generic binary MIME type; the same TEST file succeeded
through the actual form when correctly labeled as a PDF.

**How to apply:** Check authorization, status, content type, file signature,
PDF bytes and the print page separately from native viewer rendering. Use the
protected standalone print link when embedding is unavailable, while stating the
visual/physical-print limitation. Use a separate real-device or supported-browser
verification before claiming printing support. Test malformed uploads without
weakening validation, document permissions, or the content-security policy.
