#!/usr/bin/python

import os
import sys
import math
import argparse
import traceback
from collections import defaultdict
from input_handling import findNumber
from group import Group,UnsortedInputGrouper
from multiprocessing import Pool

def metric_hamming(s1, s2, state=None):
    #Return the Hamming distance between equal-length sequences
    if len(s1) != len(s2):
        raise ValueError("Undefined for sequences of unequal length")
    return sum(ch1 != ch2 for ch1, ch2 in zip(s1, s2)), state

def metric_hamming_m(args):
    return metric_hamming(*args)

def metric_levenshtein(a,b,state=None):
    #Calculates the Levenshtein distance between a and b.
    n, m = len(a), len(b)
    if n > m:
        # Make sure n <= m, to use O(min(n,m)) space
        a,b = b,a
        n,m = m,n
        
    current = range(n+1)
    for i in range(1,m+1):
        previous, current = current, [i]+[0]*n
        for j in range(1,n+1):
            add, delete = previous[j]+1, current[j-1]+1
            change = previous[j-1]
            if a[j-1] != b[i-1]:
                change = change + 1
            current[j] = min(add, delete, change)
            
    return current[n],state

def metric_levenshtein_m(args):
    return metric_levenshtein(*args)

def metric_cosine(vec1, vec2, state=None):
    # vec1 and vec2 are arrays of 2-tuples where vec[i][0] is a unique key and vec[i][1] is a frequency
    numerator = 0
    d = defaultdict(int)
    for p1 in vec1:
        d[p1[0]] = p1[1]
    for p2 in vec2:
        numerator += d[p2[0]]*p2[1]

    sum1 = sum([vec1[x][1]**2 for x in range(len(vec1))])
    sum2 = sum([vec2[x][1]**2 for x in range(len(vec2))])
    denominator = math.sqrt(sum1) * math.sqrt(sum2)

    if not denominator:
        return 0.0, state
    else:
        return float(numerator) / denominator, state

def metric_cosine_m(args):
    return metric_cosine(*args)

def metric_jaccard(vec1, vec2, state=None):
     s1 = set([vec1[x][0] for x in range(len(vec1))])
     s2 = set([vec2[x][0] for x in range(len(vec2))])
     return float(len(s1 & s2)) / float(len(s1 | s2)), state

def metric_jaccard_m(args):
    return metric_jaccard(*args)
     
class DistanceGroup(Group):
    def __init__(self, tup):
        super(DistanceGroup, self).__init__(tup)
        self.values = []
        args.groups.append(self)

    def add(self, chunks):
        self.values.append( (chunks[args.key], float(chunks[args.value])) )

    def done(self):
        pass

def generatePairs():
    for g1 in args.groups:
        for g2 in args.groups:
            if g1 == g2:
                break
            yield (g1.values, g2.values, (g1.tup, g2.tup))
            
def multithreaded():
    pool = Pool(args.threads)
    try:
        results = pool.imap_unordered(args.metricf, generatePairs(), args.chunk)
        for d,state in results:
            args.outfile.write(args.jdelim.join(state[0]+state[1]) + args.jdelim + str(d) + '\n')
    except KeyboardInterrupt:
        pool.terminate()
        sys.exit()

if __name__ == "__main__":
    # set up command line args
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                                     description='Compute distance between list')
    parser.add_argument('infiles', nargs='*', type=argparse.FileType('r'), default=[sys.stdin])
    parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
    parser.add_argument('-m', '--metric', default='cosine', choices=['cosine', 'jaccard', 'hamming', 'levenshtein'])
    parser.add_argument('-k', '--key', type=int, default=0)
    parser.add_argument('-v', '--value', type=int, default=1)
    parser.add_argument('-g', '--group', nargs='+', type=int, default=[])
    parser.add_argument('-d', '--delimiter', default=None)
    parser.add_argument('-u', '--multithreaded', action='store_true', default=False)
    parser.add_argument('-t', '--threads', default=None, type=int, help='number of threads to user')
    parser.add_argument('-c', '--chunk', default=20, help='chunk size to assign to each thread')
    args = parser.parse_args()

    args.groups = []
    args.jdelim = args.delimiter if args.delimiter != None else ' '

    for infile in args.infiles:
        grouper = UnsortedInputGrouper(infile, DistanceGroup, args.group, args.delimiter)
        grouper.group()

    if args.multithreaded:
        args.metricf = getattr(sys.modules[__name__], 'metric_'+args.metric+'_m')
        multithreaded()
    else:
        args.metricf = getattr(sys.modules[__name__], 'metric_'+args.metric)
        for v1,v2,state in generatePairs():
            args.outfile.write(args.jdelim.join(state[0]+state[1]) + args.jdelim + str(args.metricf(v1, v2)[0]) + '\n')

