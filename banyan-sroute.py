#!/usr/bin/env python
"""
    Banyan Static Router

    Generates headers for a set of static routes of 2-party calls
    in a UoB Banyan-style network of switches. Provided no two sources
    require the same destination, a valid non-blocking route is guaranteed.

Usage:
    banyan-sroute.py (-h | --help)
    banyan-sroute.py [-n=<n>] [-s=<s>] [<src--dst>...]

Options:
    -n=<n>, --numports=<n>      The number of ports in the system [default: 8]
    -s=<s>, --midswitches=<s>   The number of middle-stage switches [default: 4]

Arguments:
    <src--dst>  Source and node IDs (up to numports instances). No repeated
                srcid or dstid allowed. Randomly generated by default.

"""

from docopt import docopt

if __name__ == "__main__":
    ARGS = docopt(__doc__, version="Banyan Static Router v0.0")
    print ARGS
