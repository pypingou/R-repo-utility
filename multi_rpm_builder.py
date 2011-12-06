#!/usr/bin/python2
#-*- coding: utf-8 -*-

#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License along
#    with this program; if not, write to the Free Software Foundation, Inc.,
#    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# (C) 2011 - Pierre-Yves Chibon <pingou@pingoured.fr>

"""
Builds rpm based on the name present in the given files (one name per line)
and this in parallel.
"""

import argparse
import multiprocessing
import sys
from datetime import datetime
from multiprocessing import Pool
from r2spec.r2spec_obj import R2rpm, setup_parser as r2spec_parser

def setup_parser():
    """
    Set the command line arguments.
    """
    parser = argparse.ArgumentParser(version='0.1.0',
    usage='%(prog)s [options]', prog="Rrepo2rpm")
    # General connection options
    parser.add_argument('inputfile',
        help='Input file containing the rpm to build.')
    parser.add_argument('--mock-config', default='fedora-rawhide-i386',
        help='Mock configuration to use (defaults to fedora-rawhide-i386).')
    parser.add_argument('--ncores', type=int,
        help='Number of cores to use (all by default)')
    parser.add_argument('--verbose', action='store_true',
        help='Give more info about what is going on.')
    parser.add_argument('--debug', action='store_true',
        help='Output bunches of debugging info.')
    return parser


def build_rpm(packagename, mock_config):
    r2specparser = r2spec_parser('R2rpm')
    arg = r2specparser.parse_args('')
    arg.package = packagename
    arg.no_suggest = True
    #arg.force_spec = True
    arg.no_check = True
    #arg.mock_config = mock_config
    #arg.mock_config = 'epel-6-x86_64'
    arg.mock_config = 'epel-6-i386'
    arg.mock_resultdir = '/data/mock/results/'
    arg.keep_logs = True
    return R2rpm().main(arg)


class Builder(object):
    """ This is the class that does most of the work.
    """

    def __init__(self, ncores=None):
        """ Constructor.
        Instanciate the attributes (including the pool to which the 
        tasks are assigned).
        """
        self.ncores = multiprocessing.cpu_count()
        if ncores is None:
            self.pool = Pool(self.ncores)
        else:
            self.pool = Pool(ncores)

    def main(self, filename, mock_config):
        """ Reads the fill name, queue all the builds and run them.
        """

        stream = open(filename, 'r')
        pkg_names = stream.read().split('\n')
        stream.close()

        builds = []
        for pkg in pkg_names:
            if pkg:
                builds.append(self.pool.apply_async(build_rpm, (pkg, mock_config) ))
                #print build_rpm(pkg, mock_config)

        print '%s builds queued' % len(builds)

        cnt = 0
        failed = []
        succeed = []
        for build in builds:
            output = None
            try:
                output = build.get()
            except Exception, err:
                print "ERROR:", err
                print "On:", pkg_names[cnt]
            if output:
                failed.append(pkg_names[cnt])
            else:
                succeed.append(pkg_names[cnt])
            cnt = cnt + 1
        
        print '\n%s packages failed' % len(failed)
        print '%s packages succeed' % len(succeed)

        stream = open('failed', 'w')
        stream.write('\n'.join(failed))
        stream.close()
        stream = open('succeed', 'w')
        stream.write('\n'.join(succeed))
        stream.close()

if __name__ == "__main__":
    parser = setup_parser()
    args = parser.parse_args()
    start = datetime.now()
    print "Start at:" , start
    builder = Builder(args.ncores)
    builder.main(args.inputfile, args.mock_config)
    end = datetime.now()
    print "End at:", end
    print "Time elapsed: ", end - start
