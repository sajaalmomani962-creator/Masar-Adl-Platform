---
name: Python storage SDK bucket selection
description: An observed difference between provisioning App Storage and Python SDK default-bucket discovery.
---

Select the intended bucket explicitly when using the official Python App
Storage SDK; do not assume successful provisioning makes its default discovery
resolve the same bucket.

**Why:** A newly provisioned private bucket was usable, but a default client
raised `DefaultBucketError`. The same development-only TEST write/read/delete
passed immediately with explicit bucket selection. This was configuration
selection, not a lack of storage support or a need to replace authentication
or the existing database.

**How to apply:** Retain an explicit server-side bucket selector, never expose
credentials, and verify changes with a newly created TEST object only. Do not
diagnose default discovery failure as a storage outage before testing explicit
selection. Do not change an existing selector without considering document
references already associated with that bucket.
