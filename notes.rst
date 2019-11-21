=====
Notes
=====

---------------
Release process
---------------

Update changelog
================

Create a new changelog entry with:

~~~
debchange -l~ppa "Change message"
~~~

Don't forget to change the "channel" from "UNRELEASED" to `ubuntu`. The
`makedeb.py` script will replace `ubuntu` with the actual distribution name.

Build and test
==============

We'll run the script to create both the source packages for launchpad and
the binary packages that we'll use for testing.

1. Run the script `python makedeb.py`
2. Add `/etc/apt/sources.list.d/i3-local.list` with the following:
   ~~~
   deb [trusted=yes] file:/path/to/i3-debian/work/bionic/binary ./
   ~~~
   for example:
   ~~~
   deb [trusted=yes] file:/data/code/i3-debian/work/bionic/binary ./
   ~~~
3. Update and install
   ~~~
   # apt update
   # apt install i3
   ~~~

Upload to launchpad
===================

~~~
$ cd work/bionic
$ dput ppa:josh-bialkowski/i3-fixes i3-wm_4.17.1-1~ppa1_source.changes
~~~

-----------
Build Steps
-----------

Taken from `.travis.yml` in the source repo:

.. code::

    autoreconf -fi
    mkdir -p build
    cd build
    ../configure
    make -j

See also `debian-build.sh`, called with `DEST=deb/ubuntu-amd64/DIST`

.. code::

    mkdir -p build
    cd build
    ../configure
    make echo-version > ../I3_VERSION
    make dist-bzip2
    # unpack dist tarball
    mkdir -p "${DEST}"
    tar xf *.tar.bz2 -C "${DEST}" --strip-components=1
    cp -r ../debian "${DEST}"
    sed -i '/^\s*libxcb-xrm-dev/d' deb/ubuntu-*/DIST/debian/control || true
    cd "${DEST}"
    debchange -m -l+g$(git describe --tags) 'Automatically built'
    dpkg-buildpackage -b
