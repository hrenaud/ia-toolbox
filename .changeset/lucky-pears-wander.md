---
"ia-toolbox": patch
---

The macOS app can load its list of supported formats again, and convert files.
The signed bundle was refusing to start its document worker: notarization
requires the hardened runtime, under which macOS declined to load the Python
libraries the worker unpacks at startup because they do not carry this team's
signature. The worker died silently and every conversion was unavailable. The
bundle now ships the entitlement that exempts those libraries.
