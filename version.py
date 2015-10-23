# -*- coding: utf-8 -*-

# Calculates the current version number.  If possible, this is the
# output of "git describe", modified to conform to the versioning
# scheme that setuptools uses.  If "git describe" returns an error
# (most likely because we're in an unpacked copy of a release tarball,
# rather than in a git working copy), then we fall back on reading the
# contents of the RELEASE-VERSION file.
#
# To use this script, simply import it your setup.py file, and use the
# results of get_git_version() as your package version:
#
# from version import *
#
# setup(
#     version=get_git_version(),
#     .
#     .
#     .
# )
#
# This will automatically update the RELEASE-VERSION file, if
# necessary.  Note that the RELEASE-VERSION file should *not* be
# checked into git; please add it to your top-level .gitignore file.
#
# You'll probably want to distribute the RELEASE-VERSION file in your
# sdist tarballs; to do this, just create a MANIFEST.in file that
# contains the following line:
#
#   include RELEASE-VERSION

# A note about python version numbers:
# http://www.python.org/dev/peps/pep-0386/#id18
# http://docs.python.org/distutils/apiref.html#module-distutils.version
#
# N.N[.N]+[{a|b|c|rc}N[.N]+][.postN][.devN]
#
# minimum 'N.N'
# any number of extra '.N' segments
# 'a' = alpha, 'b' = beta
# 'c' or 'rc' = release candidate

# first number: major business changes/milestones
# second number: database changes
# third number: code changes/patches

from subprocess import Popen, PIPE

__all__ = ("get_git_version")


def call_git_describe(abbrev=5):
    """
    The `git describe --long` command outputs in the format of:

        v1.0.4-14-g2414721

    Where the fields are:

        <tag>-<number of commits since tag>-<hash>

    """
    try:
        p = Popen(['git', 'describe', '--long', '--tags', '--always',
                   '--abbrev=%d' % abbrev], stdout=PIPE, stderr=PIPE)
        p.stderr.close()
        line = p.stdout.readlines()[0].strip()

        tag, count, sha = line.split('-')
        return tag, count, sha
    except ValueError:
        # This can happen if "No tags can describe" the SHA. We'll use 'line'
        # which should now be the sha due to the --always flag
        return None, '0', line
    except:
        # Unknown error. Not a git repo?
        return (None, None, None)


def read_release_version():
    try:
        f = open("RELEASE-VERSION", "r")

        try:
            version = f.readlines()[0]
            return version.strip()

        finally:
            f.close()

    except:
        return None


def write_release_version(version):
    f = open("RELEASE-VERSION", "w")
    f.write("%s\n" % version)
    f.close()


def get_git_version(abbrev=4):
    """
    Returns this project's version number based on the git repo's tags or from
    the RELEASE-VERSION file if this is a packaged release without a .git
    directory.

    Calling this will update the RELEASE-VERSION file if the calculated version
    number differs

    Calculated dev version numbers (non-tagged commits) are PEP-426, PEP-440,
    and pip compliant as long as the latest git tag is

    https://www.python.org/dev/peps/pep-0440/

    """
    # Read in the version that's currently in RELEASE-VERSION.
    release_version = read_release_version()

    # First try to get the current version using "git describe".
    tag, count, _ = call_git_describe(abbrev)

    if count == '0':
        if tag:
            # Normal tagged release
            version = tag
        else:
            # This is an odd case where the git repo/branch can't find a tag
            version = "0.dev0"
    elif count:
        # Non-zero count means a development release after the last tag
        version = "{}.dev{}".format(tag, count)
    else:
        # Build count wasn't returned at all. Fall back on the value that's in
        # the packaged RELEASE-VERSION file
        version = release_version

    # If the current version is different from what's in the
    # RELEASE-VERSION file, update the file to be current.
    if version != release_version:
        write_release_version(version)

    # Finally, return the current version.
    return version


def get_git_hash():
    _, _, sha = call_git_describe()
    return sha

if __name__ == "__main__":
    print get_git_version()
