# -*- coding: utf-8 -*-
"""
Make debian packages. Constructs source packages with  debbuild and binary
packages with pbuilder.

To prep your system, install the following packages through apt:

* debhelper
* devscripts
* gnupg2
* pbuilder
* rsync

And the following python packages through pip

* requests

TODO(josh): capture dependencies and do everything in a series of overlays,
only if needed. Current checks are kind of weak.
"""

from __future__ import print_function
from __future__ import unicode_literals

import argparse
import io
import logging
import math
import os
import re
import subprocess
import sys
import time

import requests

REPOSITORY_URL = "https://github.com/cheshirekow/i3"
UPSTREAM_VERSION = "4.17.1"

logger = logging.getLogger(__name__)


def parse_changelog(logpath):
  """
  Parse the changelog to get package name and version number
  """
  with io.open(logpath, "r", encoding="utf-8") as infile:
    lineiter = iter(infile)
    firstline = next(lineiter)

  pattern = r"(\S+) \(([\d\.]+)-(\S+)\) (\S+); urgency=\S+"
  match = re.match(pattern, firstline)
  assert match, "Failed to match firstline pattern:\n {}".format(firstline)
  package_name = match.group(1)
  upstream_version = match.group(2)
  local_version = match.group(3)
  distribution = match.group(4)

  return package_name, upstream_version, local_version, distribution


def get_progress_bar(fraction, numchars=30):
  """
  Return a high resolution unicode progress bar
  """
  blocks = ["", "▏", "▎", "▍", "▌", "▋", "▊", "▉", "█"]
  length_in_chars = fraction * numchars
  if length_in_chars > numchars:
    length_in_chars = numchars
  n_full = int(length_in_chars)

  i_partial = int(len(blocks) * (length_in_chars - n_full))
  partial = blocks[i_partial]
  n_empty = max(numchars - n_full - len(partial), 0)
  return ("█" * n_full) + partial + (" " * n_empty)


def get_human_readable_size(size_in_bytes):
  """
  Convert a number of bytes into a human readable string.
  """
  if size_in_bytes == 0:
    return '{:6.2f}{}'.format(0, " B")

  exponent = int(math.log(size_in_bytes, 1024))
  unit = [' B', 'KB', 'MB', 'GB', 'PB', 'EB'][exponent]
  size_in_units = float(size_in_bytes) / (1024 ** exponent)
  return '{:6.2f}{}'.format(size_in_units, unit)


def download_file(srcurl, outpath):
  """
  Download i3-<version>.tar.gz if it doesn't already exist
  """
  tmppath = outpath + ".tmp"
  if os.path.exists(tmppath):
    os.remove(tmppath)

  response = requests.head(srcurl)
  totalsize = int(response.headers.get("content-length", 2320000))
  recvsize = 0

  request = requests.get(srcurl, stream=True)
  last_print = 0

  outname = os.path.basename(outpath)
  with open(tmppath, "wb") as outfile:
    for chunk in request.iter_content(chunk_size=4096):
      outfile.write(chunk)
      recvsize += len(chunk)

      if time.time() - last_print > 0.1:
        last_print = time.time()
        percent = 100.0 * recvsize / totalsize
        message = ("Downloading {}: {}/{} [{}] {:6.2f}%"
                   .format(outname,
                           get_human_readable_size(recvsize),
                           get_human_readable_size(totalsize),
                           get_progress_bar(percent / 100.0), percent))
        sys.stdout.write(message)
        sys.stdout.flush()
        sys.stdout.write("\r")
  message = ("Downloading {}: {}/{} [{}] {:6.2f}%"
             .format(outname,
                     get_human_readable_size(totalsize),
                     get_human_readable_size(totalsize),
                     get_progress_bar(1.0), 100.0))
  sys.stdout.write(message)
  sys.stdout.write("\n")
  sys.stdout.flush()
  os.rename(tmppath, outpath)
  return outpath


def get_base_tgz(distro, arch):
  return "/var/cache/pbuilder/{}-{}-base.tgz".format(distro, arch)


def prep_pbuilder(distro, arch, basetgz):
  """
  Create base rootfs tarfiles for the specified distro/arch.
  """
  subprocess.check_call(
      ["sudo", "pbuilder", "--create", "--distribution", distro,
       "--architecture", arch, "--basetgz", basetgz])


def exec_pbuilder(dscpath, distro, arch, basetgz, outdir):
  """
  Execute pbuilder to get the binary archives
  """
  subprocess.check_call(
      ["sudo", "env", 'DEB_BUILD_OPTIONS="parallel=8"',
       "pbuilder", "--build", "--distribution", distro,
       "--architecture", arch, "--basetgz", basetgz,
       "--buildresult", outdir, dscpath])


def translate_changelog(src, dst, distro):
  parent = os.path.dirname(dst)
  if not os.path.exists(parent):
    os.makedirs(parent)

  pattern = r"(\S+ \([\d\.]+-\S+\) )ubuntu(; urgency=\S+)"
  replacement = r"\1{}\2".format(distro)
  entry_regex = re.compile(pattern)
  with open(src, "r") as infile:
    with open(dst, "w") as outfile:
      for line in infile:
        outfile.write(entry_regex.sub(replacement, line))


def build_arch(distro, arch, args, dscpath, package_name, upstream_version,
               local_version):
  workdir = os.path.join(args.out, distro)

  # Create the base tarball if needed
  basetgz = get_base_tgz(distro, arch)
  outname = os.path.basename(basetgz)
  if os.path.exists(basetgz):
    logger.info("%s up to date", outname)
  else:
    logger.info("Making %s", outname)
    prep_pbuilder(distro, arch, basetgz)

  outname = ("{}_{}-{}_{}.deb"
             .format(package_name, upstream_version, local_version, arch))

  binout = os.path.join(workdir, 'binary')
  if not os.path.exists(binout):
    os.makedirs(binout)

  outpath = os.path.join(binout, outname)
  needs_build = False
  if os.path.exists(outpath):
    if os.stat(outpath).st_mtime < os.stat(dscpath).st_mtime:
      needs_build = True
      logger.info("%s is out of date", outname)
    else:
      logger.info("%s is up to date", outname)
  else:
    needs_build = True
    logger.info("Need to create %s", outname)

  if needs_build:
    exec_pbuilder(dscpath, distro, arch, basetgz, binout)

  logger.info("Writing out repository index")
  with open(os.path.join(binout, "Packages.gz"), "wb") as outfile:
    scanpkg = subprocess.Popen(
        ["dpkg-scanpackages", "."], cwd=binout, stdout=subprocess.PIPE)
    gzip = subprocess.Popen(
        ["gzip", "-9c"], cwd=binout, stdout=outfile, stdin=scanpkg.stdout)
    scanpkg.stdout.close()
  scanpkg.wait()
  gzip.wait()


def build_for(distro, args, tarball):
  logger.info("Building for %s", distro)
  workdir = os.path.join(args.out, distro)
  if not os.path.exists(workdir):
    os.makedirs(workdir)

  # Extract the tarball
  srcdir = os.path.join(workdir, "i3-{}".format(UPSTREAM_VERSION))
  if os.path.exists(srcdir):
    logger.info("Already extracted tarball")
  else:
    logger.info("Extracting tarball")
    subprocess.check_call(["tar", "xf", tarball], cwd=workdir)

  # Create symlink to source
  tarname = os.path.basename(tarball)
  tarlink = os.path.join(workdir, tarname)
  if not os.path.lexists(tarlink):
    os.symlink(tarball, tarlink)

  # Synchronize patches
  logger.info("Syncing debian patches")
  subprocess.check_call([
      'rsync', "-a",
      os.path.join(args.src, "debian/"),
      os.path.join(srcdir, "debian/")
  ])

  # Translate the changelog into ubuntu suite names
  src_changelog = os.path.join(args.src, "debian/changelog")
  srcdir = os.path.join(workdir, "i3-{}".format(UPSTREAM_VERSION))
  dst_changelog = os.path.join(srcdir, "debian/changelog")
  translate_changelog(src_changelog, dst_changelog, distro)

  # Create the .dsc file
  (package_name, upstream_version, local_version,
      distribution) = parse_changelog(dst_changelog)
  if distro != distribution:
    raise RuntimeError("{} != {}".format(distro, distribution))

  outname = ("{}_{}-{}.dsc"
             .format(package_name, upstream_version, local_version))
  dscpath = os.path.join(workdir, outname)
  if os.path.exists(dscpath):
    logger.info("%s already built", outname)
  else:
    logger.info("Creating %s", outname)
    subprocess.check_call(['debuild', "-S", "-sa", "-pgpg2", "-k6A8A4FAF"],
                          cwd=srcdir)

  if args.skip_build:
    return
  for arch in args.arch:
    build_arch(distro, arch, args, dscpath, package_name, upstream_version,
               local_version)


def setup_argparse(parser):
  """
  Setup argument parser
  """
  arches = ["i386", "amd64", "armhf", "arm64"]
  distros = ["bionic"]  # , "eoan"]

  parser.add_argument("--distro", choices=distros, nargs="*",
                      help="which distros to build",
                      default=list(distros))
  parser.add_argument("--arch", choices=arches, nargs="*",
                      help="which architectures to build",
                      default=["amd64"])

  srcdir = os.path.dirname(os.path.realpath(__file__))
  parser.add_argument("--src", help="source directory", default=srcdir)
  parser.add_argument("--out", help="output directory",
                      default=os.path.join(srcdir, "work"))
  parser.add_argument("--skip-build", action="store_true")


def main():
  logging.basicConfig(level=logging.INFO)

  parser = argparse.ArgumentParser(description=__doc__)
  setup_argparse(parser)
  args = parser.parse_args()

  # Download the tarball if needed
  src_url = ("https://github.com/i3/i3/archive/{}.tar.gz"
             .format(UPSTREAM_VERSION))
  tarball = os.path.join(
      args.out, "i3-wm_{}.orig.tar.gz".format(UPSTREAM_VERSION))
  if not os.path.exists(args.out):
    os.makedirs(args.out)

  if os.path.exists(tarball):
    logger.info("Already downloaded tarball")
  else:
    download_file(src_url, tarball)

  # TODO(josh): install requirements... or, better yet, use container.
  # sudo apt install $(tr '\n' ' ' < apt-depends.txt)
  for distro in args.distro:
    build_for(distro, args, tarball)


if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
  main()
