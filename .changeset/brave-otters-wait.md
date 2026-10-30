---
"ia-toolbox": patch
---

A file dropped onto the conversion page is added to the list once, not twice.
The page subscribed to native drag and drop inside the effect that loads the
format catalog, and read the unsubscribe function synchronously in the cleanup
even though subscribing is asynchronous — so a cleanup that ran before the
subscription settled left a second handler attached, and every drop was
counted by both.
