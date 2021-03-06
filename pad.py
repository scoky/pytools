#!/usr/bin/env python

import os
import sys
import argparse
from toollib.files import FileReader,ParameterParser
from toollib.group import Group,run_grouping

class PadGroup(Group):
    def __init__(self, tup):
        super(PadGroup, self).__init__(tup)
        self.present = set()

    def add(self, chunks):
        self.present.add(tuple(chunks[i] for i in args.columns))
        args.outfile.write(chunks)

    def done(self):
        for element in args.elements:
            if element not in self.present:
                args.outfile.write(self.tup + list(element) + args.pad)

if __name__ == "__main__":
    pp = ParameterParser('Generate additional rows to pad input', columns = '*', append = False, labels = False, ordered = False)
    pp.parser.add_argument('-e', '--elements', help='File containing list elements, one per line.')
    pp.parser.add_argument('-p', '--pad', nargs='+', default=['0'])
    args = pp.parseArgs()
    args.append = True
    args = pp.getArgs(args)

    elements = set()
    with FileReader(args.elements, args) as f:
        for chunks in f:
            elements.add(tuple(chunks))
    args.elements = elements

    run_grouping(args.infile, PadGroup, args.group, ordered = False)
