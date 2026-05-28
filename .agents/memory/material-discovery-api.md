---
name: MaterialDiscovery double-json bug
description: apiPost/apiGet in MaterialDiscoveryPanel called .json() twice — one call was already consuming the response body
---

`apiCall` already calls `response.json()` and returns the parsed object. The former `apiPost` and `apiGet` helper functions then called `.json()` again on that object (which is not a Response), silently returning `undefined`.

**Fix:** Remove the second `.json()` call — `apiPost` and `apiGet` should simply `return apiCall(...)`.

**Why it was subtle:** `object.json()` does not throw immediately in some JS engines if the object happens to have no such method — it may resolve to undefined, causing downstream `data.candidates` etc. to be undefined without a clear error.
