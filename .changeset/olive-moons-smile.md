---
"ia-toolbox": patch
---

The Windows installer is built again. Its build step had been silently doing
nothing: the script that packages the Python worker decided whether it was being
run or merely imported by comparing paths in a way that is only ever true on
macOS and Linux, so on Windows it exited immediately and reported success. The
bundle then failed on a worker that was never produced, and no Windows installer
was attached to the release.
