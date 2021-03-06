#!/usr/bin/env python

import os
import sys
import argparse
from toollib.files import ParameterParser,findNumber
from toollib.group import Group,run_grouping
from decimal import Decimal
from heapq import heappush, heappop

class MaxGroup(Group):
    def __init__(self, tup):
        super(MaxGroup, self).__init__(tup)
        self.maxes = [Decimal('-Inf')]*len(args.columns)
        self.rows = [None]*len(args.columns)

    def add(self, chunks):
        for i,c in enumerate(args.columns):
            val = findNumber(chunks[c])
            if val > self.maxes[i]:
                self.maxes[i] = val
                self.rows[i] = chunks

    def done(self):
        if args.append:
            for r in self.rows:
                args.outfile.write(r)
        else:
            args.outfile.write(self.tup + self.maxes)

class KMaxGroup(Group):
    def __init__(self, tup):
        super(KMaxGroup, self).__init__(tup)
        self.maxes = [[] for c in args.columns]

    def add(self, chunks):
        for i,c in enumerate(args.columns):
            heappush(self.maxes[i], findNumber(chunks[c]))
            if len(self.maxes[i]) > args.k:
                heappop(self.maxes[i])

    def done(self):
        for i,m in enumerate(self.maxes):
            self.maxes[i] = reversed(sorted(m))
        for k in range(args.k):
            args.outfile.write(self.tup + [m[k] for m in self.maxes] + [ k+1 ])

if __name__ == "__main__":
    pp = ParameterParser('Compute maximum of columns', columns = '*', labels = [None])
    pp.parser.add_argument('-k', '--k', type = int, default = 1, help = 'find the k maximum values')
    args = pp.parseArgs()
    if not any(args.labels):
        args.labels = [cn + '_max' for cn in args.columns_names]
    if args.append:
        args.labels = []
    if args.k > 1:
        args.labels.append('k')
    args = pp.getArgs(args)

    if args.k > 1:
        run_grouping(args.infile, KMaxGroup, args.group, args.ordered)
    else:
        run_grouping(args.infile, MaxGroup, args.group, args.ordered)
