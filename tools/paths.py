# -*- coding: utf-8 -*-
"""Where to read bundled data from, and where to do work.

Running from source these are the same directory. Frozen into an .exe they are
not: read-only data ships inside the bundle and is unpacked to a temp dir, while
the dump/ and out/ trees have to live somewhere the user can actually see them.
"""
import os, sys

FROZEN = getattr(sys, 'frozen', False)

# Read-only data that ships with the tool (ctrl_args.json, the DS->Collection map).
DATA = (os.path.join(sys._MEIPASS, 'dump') if FROZEN
        else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'dump'))

# Writable root: next to the .exe when frozen, the repo root when running from source.
WORK = (os.path.dirname(os.path.abspath(sys.executable)) if FROZEN
        else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def data(*parts):
    """A file that ships with the tool."""
    return os.path.normpath(os.path.join(DATA, *parts))


def work(*parts):
    """A file the tool reads or writes at build time."""
    return os.path.normpath(os.path.join(WORK, *parts))
