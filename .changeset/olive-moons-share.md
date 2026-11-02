---
"ia-toolbox": patch
---

fix(worker): keep the one worker alive when switching between workflows

Switching from conversion to anonymization opened the page on "could not load
the formats that can be anonymized". Each page stopped the worker when it was
left, but the two workflows talk to the **same** process, so leaving one killed
the process the other was about to use. The app now owns the worker's lifetime
and no page stops it.

Two related races are closed on the way: asking for the worker twice before the
first one has finished starting started two processes, and asking for it while
it was being stopped handed back a worker already told to fail.
