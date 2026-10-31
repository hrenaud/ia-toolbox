---
"ia-toolbox": patch
---

Dropping files onto the drop zone of the Markdown conversion page works again.
The window's capability granted no core permissions, so the page's request to
listen for native drag and drop events was rejected at the IPC boundary. The
rejection went to the console and the zone stayed inert, while the file picker
beside it kept working.
