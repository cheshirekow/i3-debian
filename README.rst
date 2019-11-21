=====================
Debian package for i3
=====================

This repository contains a maintainer script and some debian packaging files
for patched i3. The patched i3 pak

* Upstream repository is here__
* Patch/dev repository is here__

.. __: https://github.com/i3/i3
.. __: https://github.com/cheshirekow/i3

----------------------------
Summary of packaging changes
----------------------------

1. add `quilt` to the build dependencies in the control file
2. add `source/format` to avoid lintian warnings
3. add patches
4. add my entries to the changelog

------------------
Summary of patches
------------------

1. support keyboard focus with multiple xscreens
