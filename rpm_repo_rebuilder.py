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
import logging
import multiprocessing
import sys
from datetime import datetime
from multiprocessing import Pool
from subprocess import Popen, PIPE
from r2spec.r2spec_obj import R2rpm, setup_parser as r2spec_parser

logging.basicConfig()
LOG = logging.getLogger()
if '--debug' in sys.argv:
    LOG.setLevel(logging.DEBUG)
elif '--verbose' in sys.argv:
    LOG.setLevel(logging.INFO)

def setup_parser():
    """
    Set the command line arguments.
    """
    parser = argparse.ArgumentParser()
    # General connection options
    parser.add_argument('inputfile',
        help='Input file containing the rpm to build.')
    parser.add_argument('--mock-config', default='fedora-rawhide',
        help='Mock configuration to use (defaults to fedora-rawhide). Do not specify the arch as this is a rebuild for both.')
    parser.add_argument('--ncores', type=int,
        help='Number of cores to use (all by default)')
    parser.add_argument('--verbose', action='store_true',
        help='Give more info about what is going on.')
    parser.add_argument('--debug', action='store_true',
        help='Output bunches of debugging info.')
    return parser


def build_rpm(packagename, mock_config):
    #LOG.debug ('  R2rpm %s -- %s' %(packagename, mock_config))
    print '  R2rpm %s -- %s' %(packagename, mock_config)
    r2specparser = r2spec_parser('R2rpm')
    arg = r2specparser.parse_args('')
    arg.package = packagename
    arg.no_suggest = True
    arg.force_spec = True
    #arg.force_dl = True
    arg.no_check = True
    arg.mock_config = mock_config
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
        self.log = LOG
        self.ncores = multiprocessing.cpu_count()
        if ncores is None:
            self.pool = Pool(self.ncores)
        else:
            self.pool = Pool(ncores)

    def is_built(self, pkgname, arch):
        """ For a given package, returns if the package is present in
        the repository, (True if it is, False otherwise).

        :arg pkgname, name of the package to search in the repositories.
        """
        arch_pkg = []
        built = False
        cmd = ['repoquery', '--envra', 'R-%s' % pkgname, '--archlist', arch ]
        self.log.debug(" ".join(cmd))
        #print cmd
        archname = Popen(cmd, stdout=PIPE).stdout.read()[:-1]
        if archname:
            built = True
        cmd = ['repoquery', '--envra', 'R-%s' % pkgname]
        self.log.debug(" ".join(cmd))
        noarch = Popen(cmd, stdout=PIPE).stdout.read()[:-1]
        if noarch:
            built = True
        return built

    def multiple_build(self, pkg_names, arch, mock_config):
        """ For a given list of package and one architecture, for each
        package, check if the package should be built for this arch,
        queue the build, run them and report.

        :arg pkg_names, a list of package name.
        :arg arch, the architecture to build against (i686/x86_64)
        """
        print arch
        builds = []
        for pkg in pkg_names:
            if pkg:
                self.log.debug(pkg)
                if not self.is_built(pkg, arch):
                    self.log.debug('  %s' % arch)
                    mock_arch = arch
                    if mock_arch == 'i686':
                        mock_arch = 'i386'
                    mock_cfg = '%s-%s' %(mock_config, mock_arch)
                    builds.append(self.pool.apply_async(build_rpm, (pkg, mock_cfg) ))
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

        stream = open('failed_%s' % arch, 'a')
        stream.write('\n'.join(failed))
        stream.close()
        stream = open('succeed_%s' % arch, 'a')
        stream.write('\n'.join(succeed))
        stream.close()

    def main(self, filename, mock_config):
        """ Reads the fill name, queue all the builds and run them.
        """

        stream = open(filename, 'r')
        pkg_names = stream.read().split('\n')
        stream.close()

        self.multiple_build(pkg_names, 'i686', mock_config)
        self.multiple_build(pkg_names, 'x86_64', mock_config)


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
