#!/usr/bin/env python3
"""
    Static Router for MCENoC network

    Generates headers for a set of static routes of 2-party calls
    in a UoB MCENoC network of switches. Provided no two sources
    require the same destination, a valid non-blocking route is guaranteed.

    Copyright (c) 2017 Steve Kerrison, University of Bristol

    Released under the MIT License, see LICENSE file, which must be packaged
    together with this program wherever it is distributed.

Usage:
    mcenoc-sroute.py -h
    mcenoc-sroute.py [options] <network.tikz> [<src--dst>...]

Options:
    -h, --help                      Print this help message.
    -a <file.tikz> --annotate=<file.tikz>   Output coloured routes.
    -p, --print                     Print routing bits for each port.

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
import numpy as np
import time
import sys


class BSPMat():

    def __init__(self, srcdst=None):
        if srcdst:
            self.s = {a: {'src': a, 'dst': b, 'os': None, 'od': None} for a, b
                      in srcdst}
            self.d = {b['dst']: b for a, b in self.s.items()}
            self.size = len(self.s)
        else:
            self.s = {}
            self.d = {}
            self.size = None

    def __len__(self):
        return self.size

    def insert(self, x):
        newsrc = int(x['src']/2)
        newdst = int(x['dst']/2)
        v = {'src': newsrc, 'dst': newdst, 'os': x['src'], 'od': x['dst']}
        self.s[newsrc] = v
        self.d[newdst] = v

    def delete(self, x):
        newsrc = int(x['src']/2)
        newdst = int(x['dst']/2)
        del self.ps[newsrc][x['src']]
        if len(self.ps[newsrc]) == 0:
            del self.ps[newsrc]
        del self.pd[newdst][x['dst']]
        if len(self.pd[newdst]) == 0:
            del self.pd[newdst]
        return

    def partition(self):
        newsize = int(self.size/2)
        self.ps = {x: {} for x in range(newsize)}
        self.pd = {x: {} for x in range(newsize)}
        self.dbl = {}
        seen = {}
        for x in self.d.values():
            ns = int(x['src']/2)
            nd = int(x['dst']/2)
            self.ps[ns][x['src']] = x
            self.pd[nd][x['dst']] = x
            if (ns, nd) in seen:
                self.dbl[ns, nd] = True
            else:
                seen[ns, nd] = True
        return self

    def permutedbl(self, Pa, Pb):
        """
            Do the permutation splitting for cells that have two entries
        """
        start = 0
        others = self.size - 1
        if len(self.dbl):
            for x in self.dbl:
                v = next(iter(self.pd[x[1]].values()))
                Pa.insert(v)
                self.delete(v)
                v = next(iter(self.pd[x[1]].values()))
                Pb.insert(v)
                self.delete(v)
                others -= 2
            if len(self.pd):
                start = next(iter(self.pd))
            else:
                start = None
        return start, others

    def newpermute(self, r):
        """
            We hit the end of a cycle without completing the permutation.
            Find a new starting point
        """
        return next(iter(r))

    def permutation(self, stage, offset=0):
        self.partition()
        Pa, Pb = BSPMat(), BSPMat()
        startcol, othercols = self.permutedbl(Pa, Pb)
        if startcol is not None:
            v = next(iter(self.pd[startcol].values()))
            Pa.insert(v)
            pos = int(v['dst']/2)
            self.delete(v)
            reflu = [self.pd, self.ps]
            refin = [Pb, Pa]
            refdim = ['dst', 'src']
            refidx = 0
            for i in range(othercols):
                refl = reflu[refidx]
                refi = refin[refidx]
                if pos not in refl:
                    pos = self.newpermute(refl)
                refidx = (refidx + 1) % 2
                v = next(iter(refl[pos].values()))
                refi.insert(v)
                pos = int(v[refdim[refidx]]/2)
                self.delete(v)
        Pa.size = len(Pa.d)
        Pb.size = len(Pb.d)
        isw = [int(x['os']/2) for x in Pa.d.values() if x['os'] & 1]
        osw = [int(x['od']/2) for x in Pa.d.values() if x['od'] & 1]
        swconfig = {(stage, offset): {'in': set(isw), 'out': set(osw)}}
        stage -= 1
        offset *= 2
        if stage >= 0:
            swconfig.update(Pa.permutation(stage, offset))
            swconfig.update(Pb.permutation(stage, offset+1))
        return swconfig

    def route(self):
        return [(x, y['dst']) for x, y in self.s.items()]


class BSRoute():
    """
        Static route generator for MCENoC networks.
    """

    def __init__(self, net, route):
        super(BSRoute, self).__init__()
        self.netfile = open(net, 'r')
        pr = parse.parse(r"\node[BP={:d}, BN={:d}, BM={:d}, BL={:d}{}",
                         self.netfile.readline().strip())
        self.nports = pr[0]
        self.nbits = int(math.log(pr[1], 2))
        self.mbits = int(math.log(pr[2], 2))
        self.stages = pr[3]
        self.rbits = self.stages*self.nbits*2 + self.mbits
        self.netfile.seek(0, 0)
        self.src = []
        self.dst = []
        if len(route) > 0:
            src, dst = [list(l) for l in zip(*[x.split('--') for x in route])]
            self.src = list(map(lambda i: int(i, 0), src))
            self.dst = list(map(lambda i: int(i, 0), dst))
        else:
            print ("No route given. Generating random route", file=sys.stderr)
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

    def connection(self, stage, switch, port, side, step, group):
        mod = 2**stage
        relsw = switch % mod
        group = max(int(self.nports/2) - step, 1)
        context = (stage, int(switch/group))
        cfg = self.swconfig[context]
        cross = relsw in cfg[side]
        pstep = 2**(st+2)
        if pstep > self.nports:
            step = self.nports
        else:
            step = pstep
        pmap = int((port % step) * 2)
        wrapcount = int(pmap / step)
        pmod = int((pmap % step) + wrapcount)
        blockoff = int(math.floor(port / step) * step)
        fport = pmod + blockoff

    def routebits(self, annotate):
        if annotate:
            f = open(annotate, 'w')
            f.write(r"""\documentclass[tikz]{standalone}
\usepackage{xcolor}

\newcommand{\randomcolor}{%
  \definecolor{randomcolor}{RGB}
   {
    \pdfuniformdeviate 256,
    \pdfuniformdeviate 256,
    \pdfuniformdeviate 256
   }%
  \color{randomcolor}%
}
\usetikzlibrary{switching-architectures}
\pagestyle{empty}

\begin{document}

\begin{tikzpicture}
""")
            f.write(self.netfile.read())
        rbits = {x: [] for x in range(self.nports)}
        nstages = int(math.log(self.nports, 2) - 1)
        stages = list(range(nstages, 0, -1)) + list(range(nstages+1))
        linkstages = stages[1:nstages+1]
        linkstages += reversed(linkstages)
        steps = [2*(stages[0] - n) for n in stages]
        side = ['in' for x in range(nstages+1)] + ['out' for x in
                                                   range(nstages)]
        self.inputs = {x: x for x in range(self.nports)}
        newinputs = {x: False for x in range(self.nports)}
        for i, st in enumerate(stages):
            newinputs = {x: False for x in range(self.nports)}
            for sw in range(int(self.nports/2)):
                mod = 2**st
                relsw = sw % mod
                group = int(sw/mod)
                context = (st, group)
                cfg = self.swconfig[context]
                cross = relsw in cfg[side[i]]
                p0 = 2*sw
                p1 = 2*sw+1
                if cross:
                    rbits[self.inputs[p0]].append(1)
                    newinputs[p0+1] = self.inputs[p0]
                    rbits[self.inputs[p1]].append(0)
                    newinputs[p1-1] = self.inputs[p1]
                    if annotate:
                        f.write("""
\draw[color=blue,densely dotted,thick](r{}-{}-input-{})--(r{}-{}-output-{});""".format(
                            i+1, sw+1, 1, i+1, sw+1, 2))
                        f.write("""
\draw[color=blue,densely dotted,thick](r{}-{}-input-{})--(r{}-{}-output-{});""".format(
                            i+1, sw+1, 2, i+1, sw+1, 1))
                else:
                    rbits[self.inputs[p0]].append(0)
                    newinputs[p0] = self.inputs[p0]
                    rbits[self.inputs[p1]].append(1)
                    newinputs[p1] = self.inputs[p1]
                    if annotate:
                        f.write("""
\draw[color=blue,densely dotted,thick](r{}-{}-input-{})--(r{}-{}-output-{});""".format(
                            i+1, sw+1, 1, i+1, sw+1, 1))
                        f.write("""
\draw[color=blue,densely dotted,thick](r{}-{}-input-{})--(r{}-{}-output-{});""".format(
                        i+1, sw+1, 2, i+1, sw+1, 2))
            self.inputs = dict(newinputs)
            newinputs = {x: False for x in range(self.nports)}
            if i+1 < len(stages):
                pstep = 2**(linkstages[i]+2)
                if pstep > self.nports:
                    step = self.nports
                else:
                    step = pstep
                for p in range(self.nports):
                    # Only go as far as penultimate stage
                    pmap = int((p % step) * 2)
                    wrapcount = int(pmap / step)
                    pmod = int((pmap % step) + wrapcount)
                    blockoff = int(math.floor(p / step) * step)
                    fport = pmod + blockoff
                    if side[i] == 'in':
                        p, fport = fport, p
                    newinputs[fport] = self.inputs[p]
                self.inputs = dict(newinputs)
        if annotate:
            f.write(r"""
\end{tikzpicture}

\end{document}""")
            f.close()
        return rbits

    def gen(self, annotate, printroute):
        # self.src = [2, 4, 7, 5, 1, 3, 6, 0]
        # self.src = [7, 3, 5, 1, 6, 2, 0, 4]
        # self.src = [7, 0, 4, 5, 1, 2, 6, 3]
        # self.src = [7, 6, 4, 5, 1, 2, 0, 3]
        # self.dst = [0, 1, 2, 3, 4, 5, 6, 7]
        # self.src = [0, 1, 2, 3, 4, 5, 6, 7]
        # self.dst = [7, 3, 6, 0, 5, 2, 1, 4]
        # self.src = list(range(16))
        # self.dst = [0, 11, 2, 7, 14, 8, 5, 6, 3, 10, 13, 4, 12, 1, 9, 15]
        Pa = BSPMat(zip(self.src, self.dst))
        Pb = None
        # print ("Route:")
        # print (Pa.route())
        stage = int(math.log(self.nports, 2))-1
        self.swconfig = Pa.permutation(stage)
        confkey = sorted(self.swconfig, reverse=True)
        # print ([(k, self.swconfig[k]) for k in confkey])
        if printroute:
            print ("Route bits per port:")
            print (self.routebits(annotate))


if __name__ == "__main__":
    ARGS = docopt(__doc__, version="MCENoC Static Router v0.1")
    BSR = BSRoute(ARGS['<network.tikz>'], ARGS['<src--dst>'])
    start = time.clock()
    BSR.gen(ARGS['--annotate'], ARGS['--print'])
    end = time.clock()
    print ("Routed permutation in {:.4f} seconds".format(end - start),
           file=sys.stderr)