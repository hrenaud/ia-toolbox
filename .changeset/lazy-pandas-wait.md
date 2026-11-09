---
"ia-toolbox": patch
---

fix(worker): stop the discarded dev mount from claiming the formats failed

Launching the app in development showed a red "restart the application" banner
on the conversion page, above the list of formats it had just loaded fine, and
it disappeared as soon as the workflow was switched.

StrictMode discards the first mount in development, and the shell's cleanup
stops the shared worker while that mount's `list_formats` request is still in
flight. The request rejected, and the page it no longer belonged to set its
error anyway. Both pages now drop a result that arrives after their mount was
discarded, the same way the drag-and-drop subscription next to them already
did.
