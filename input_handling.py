#!/usr/bin/python

import os
import re
import sys
import glob
import string
import socket
import struct
import logging
import datetime
import argparse
import traceback
from copy import copy
from decimal import Decimal,InvalidOperation

number_pattern = re.compile("(-?\d+\.?\d*(e[\+|\-]?\d+)?)", re.IGNORECASE)
ip_pattern = re.compile("(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")

def findIdentity(value):
    return value

def findFloat(value):
    return float(value)

def findInt(value):
    return int(value)

# Search an input value for a number
def findNumber(value):
    try:
        return Decimal(value)
    except InvalidOperation:
        return Decimal(number_pattern.search(value).group())

# Search an input value for a number
def findSignificantNumber(value, digits):
    try:
        return Decimal(value)
    except InvalidOperation:
        return Decimal(number_pattern.search(value).group())

def findIPAddress(value):
    try:
        # Might be a simple integer
        return int(value)
    except ValueError:
        m = ip_pattern.search(value)
        if m: # IP address in octet notation
	        return IPfromString(m.group())
        else: # Potentially a hostname
            return socket.gethostbyname(value)

def IPfromString(ip):
    return struct.unpack("!I", socket.inet_aton(ip))[0]

def IPtoString(ip):
    return socket.inet_ntoa(struct.pack("!I", int(ip)))

def MACfromString(mac):
    return int(mac.replace(':', ''), 16)

def MACtoString(mac):
    mac = hex(int(mac)).lstrip('0x')
    mac = '0'*(12-len(mac))+mac
    return ':'.join([mac[i:i+2] for i in xrange(0, len(mac), 2)])

def ToUnixTime(dt):
    epoch = datetime.datetime.utcfromtimestamp(0)
    delta = dt - epoch
    return delta.days*86400 + delta.seconds

def ToDateTime(dt):
    return datetime.datetime.utcfromtimestamp(dt)

def parseLines(infile, delimiter=None, columns=[0], function=findIdentity):
    for line in infile:
        try:
            chunks = line.rstrip().split(delimiter)
            yield [function(chunks[i]) for i in columns]
        except IndexError as e:
            logging.error('Error on input: %s%s\n%s', line, e, traceback.format_exc())

def concatFiles(files, opts='r'):
    for f in files:
        for line in openFile(f, opts):
            yield line

def fileRange(startFile, endFile):
    startDir, startFile = os.path.split(startFile)
    _, endFile = os.path.split(endFile)
    if startDir == '':
        files = glob.iglob('*');
    else:
        files = glob.iglob(os.path.expanduser(startDir) + '/*');
    ret = []
    for fn in files:
        if startFile <= os.path.basename(fn) <= endFile:
            ret.append(fn)
    return sorted(ret)

def openFile(filename, opts):
    if type(filename) is str:
        return gzip.open(os.path.expanduser(filename), opts+'b') if filename.endswith('.gz') else open(os.path.expanduser(filename), opts)
    elif type(filename) is file:
        return filename
    else:
        raise IOError('Unknown input type: %s' % type(filename))

class Header:
    def __init__(self, columns = []):
        self.columns = columns
        
    def __len__(self):
        return len(self.columns)

    def __iter__(self):
        return self.columns.__iter__()
        
    def setCol(self, colName, index):
        while len(self.columns) <= index:
            self.columns.append(str(len(self.columns)))
        self.columns[index] = colName
        
    def addCol(self, colName):
        col = colName
        i = 1
        while col in self.columns:
            col = colName+str(i)
            i += 1
        self.columns.append(col)
        return len(self.columns) - 1

    def addCols(self, colNames):
        return [self.addCol(colName) for colName in colNames]
        
    def extend(self, header):
        self.addCols(header.columns)

    def index(self, colName):
        if colName is None:
            return colName
        elif colName in self.columns:
            return self.columns.index(colName)
        else:
            try:
                return int(colName)
            except ValueError as e:
                raise ValueError('Invalid column %s specified' % colName, e)

    def indexes(self, colNames):
        return [self.index(colName) for colName in colNames]

    def name(self, index):
        try:
            return self.columns[int(index)]
        except ValueError:
            return str(index)
        except IndexError:
            return 'col_'+str(index)

    def names(self, indexes):
        return [self.name(index) for index in indexes]

    def copy(self):
        return Header(copy(self.columns))

class FileWriter:
    def __init__(self, outputStream, reader, args):
        self._outputStream = openFile(outputStream, 'w')
        self._delimiter = reader._delimiter if reader._delimiter else ' '
        if reader.hasHeader:
            self.write = self._firstwrite
            if hasattr(args, 'append') and args.append:
                self._header = reader.header.copy()
            else:
                self._header = Header()
                if hasattr(args, 'group'):
                    self._header.addCols(reader.header.names(args.group))
            if hasattr(args, 'labels'):
                self._header.addCols(args.labels)
        else:
            self.write = self._write
            self._header = Header()
            
    @property
    def header(self):
        return self._header

    @property
    def hasHeader(self):
        return len(self._header.columns) > 0

    def _firstwrite(self, chunks):
        self.write = self._write
        self.write(self._header.columns)
        if len(self._header) != len(chunks):
            sys.stderr.write('Warning: number of rows in output does not match number of rows in header\n')
        self.write(chunks)

    def _write(self, chunks):
        self._outputStream.write(self._delimiter.join(chunks)+'\n')

class FileReader:
    def __init__(self, inputStream, header = False, delimiter = None):
        self._inputStream = openFile(inputStream, 'r')
        self._delimiter = delimiter if delimiter else os.environ.get('TOOLBOX_DELIMITER', None)
        header = header or os.environ.get('TOOLBOX_HEADER', '').lower() == 'true'
        if header:
            self._header = self._readHeader()
            self.next = self._firstnext
        else:
            self._header = Header()
            self.next = self._next

    @property
    def header(self):
        return self._header

    @property
    def hasHeader(self):
        return len(self._header.columns) > 0

    def _readHeader(self):
        preamble = self._inputStream.next()
        return Header(preamble.strip().split(self._delimiter))
        
    def __iter__(self):
        return self

    def _firstnext(self):
        self.next = self._next
        row = self.next()
        if len(row) != len(self._header):
            sys.stderr.write('Warning: number of rows in input does not match number of rows in header\n')
        return row
        
    def _next(self):
        return self._inputStream.next().strip().split(self._delimiter)

    def readline(self):
        try:
            return self.next()
        except StopIteration:
            return ''

    def close(self):
        self._inputStream.close()

    def __enter__(self):
        return self
        
    def __exit__(self, type, value, traceback):
        self.close()

class ParameterParser:
    def __init__(self, descrip, group = True, columns = True, append = True, labels = None):
        self.parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter, description=descrip)
        self.parser.add_argument('infile', nargs='?', default=sys.stdin)
        self.parser.add_argument('outfile', nargs='?', default=sys.stdout)
        if group:
            self.parser.add_argument('-g', '--group', nargs='+', default=[], help='column(s) to group input by')
        if columns:
            self.parser.add_argument('-c', '--columns', nargs='+', default=[0], help='column(s) to manipulate')
        if labels:
            self.parser.add_argument('-l', '--labels', nargs='+', default=labels, help='labels for the column(s)')
        if append:
            self.parser.add_argument('--append', action='store_true', default=False, help='keep original columns in output')
        self.parser.add_argument('--delimiter', default=None)
        self.parser.add_argument('--header', action='store_true', default=False)

    def parseArgs(self):
        return self.parser.parse_args()
        
    def getArgs(self, args):
        args.infile = FileReader(args.infile, args.header, args.delimiter)
        args.outfile = FileWriter(args.outfile, args.infile, args)
        if hasattr(args, 'group'):
            args.group_names = args.infile.header.names(args.group)
            args.group = args.infile.header.indexes(args.group)
        if hasattr(args, 'columns'):
            args.columns_names = args.infile.header.names(args.columns)
            args.columns = args.infile.header.indexes(args.columns)
        return args

if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                                     description='Parse input base upon available functions')
    parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
    parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
    parser.add_argument('-c', '--columns', nargs='+', type=int, default=[0])
    parser.add_argument('-a', '--append', action='store_true', default=False, help='append result to columns')
    parser.add_argument('-f', '--function', choices=['IPtoString', 'IPfromString', 'MACtoString', 'MACfromString', 'findNumber', 'findIPAddress'], default='findNumber')
    parser.add_argument('-d', '--delimiter', default=None)
    args = parser.parse_args()
    args.function = getattr(sys.modules[__name__], args.function)

    jdelim = args.delimiter if args.delimiter != None else ' '
    for line in args.infile:
        chunks = line.rstrip().split(args.delimiter)
        vals = [args.function(chunks[i]) for i in args.columns]
        if args.append:
            args.outfile.write('%s%s' % (line.rstrip(), jdelim))
        args.outfile.write(jdelim.join(map(str,vals))+'\n')
    
