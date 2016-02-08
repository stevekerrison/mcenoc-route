#!/usr/bin/env python3
"""
    Banyan Static Router

    Generates headers for a set of static routes of 2-party calls
    in a UoB Banyan-style network of switches. Provided no two sources
    require the same destination, a valid non-blocking route is guaranteed.

Usage:
    banyan-sroute.py -h
    banyan-sroute.py <network.tikz> [<src--dst>...]

Options:
    -h, --help                      Print this help message.

Arguments:
    <network.tikz>                  The network description in Sa-Tikz
                                    butterfly format.
    <src--dst>                      Source and node IDs (up to numports
                                    instances). No repeated srcid or dstid
                                    allowed. Randomly generated by default.

"""

from docopt import docopt
import random
import parse
import math
import pyeda.util as eda


class BSRoute:
    """
        Static route generator for Banyan-style networks.
    """

    def __init__(self, net, route):
        netfile = open(net, 'r')
        pr = parse.parse(r"\node[BP={:d}, BN={:d}, BM={:d}, BL={:d}{}",
                         netfile.readline().strip())
        netfile.close()
        self.nports = pr[0]
        self.nbits = int(math.log2(pr[1]))
        self.mbits = int(math.log2(pr[2]))
        self.stages = pr[3]
        self.rbits = self.stages*self.nbits*2 + self.mbits
        print (self.nports, self.nbits, self.mbits)
        self.src = []
        self.dst = []
        if len(route) > 0:
            src, dst = [list(l) for l in zip(*[x.split('--') for x in route])]
            self.src = list(map(lambda i: int(i, 0), src))
            self.dst = list(map(lambda i: int(i, 0), dst))
        else:
            self.randroute()
        self.dupecheck(self.src)
        self.dupecheck(self.dst)
        self.rangecheck(self.src)
        self.rangecheck(self.dst)
        return

    def rangeraise(self, v):
        raise ValueError("Value {} outside node range".format(v))

    def rangecheck(self, l):
        if max(l) >= self.nports:
            self.rangeraise(max(l))
        if min(l) < 0:
            self.rangeraise(min(l))

    def dupecheck(self, l):
        seen = set()
        dupes = set(x for x in l if x in seen or seen.add(x))
        if len(dupes) > 0:
            raise ValueError('Duplicate value(s): {}'.format(list(dupes)))
        return

    def randroute(self):
        self.src = random.sample(range(self.nports), self.nports)
        self.dst = random.sample(range(self.nports), self.nports)

    def gen(self):
        self.routes = zip(self.src, self.dst)
        self.routesort = map(lambda x: x[0],
                             sorted(self.routes, key=lambda x: x[1]))
        self.routeout = []
        sw = 0
        hbits = int((self.rbits-1)/2)
        nsw = int(self.nports / 2**self.mbits)
        swskip = int(nsw / (2**self.mbits))
        fmt = "{{:0{:d}b}}".format(self.rbits)
        print (hbits, nsw, fmt)
        print ("Routes:")
        for i,r in enumerate(self.routesort):
            if i % nsw == 0:
                sw = 0
            print (i, r, fmt.format((sw << (hbits + 1)) | i))
            # sw = sw + swskip
            # if sw > nsw:
            #     sw = int((sw + 1) % nsw)
            sw += swskip
            if sw >= nsw:
                sw = ((sw + 1) % nsw)


if __name__ == "__main__":
    ARGS = docopt(__doc__, version="Banyan Static Router v0.0")
    BSR = BSRoute(ARGS['<network.tikz>'], ARGS['<src--dst>'])
    BSR.gen()
