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
This script reads the git repository, get the version for each spec in
there and compare it to the version present in the upstream repository.
If the upstream version is higher than the local version, print the name
of the package to the screen.
"""


import ConfigParser
import os
import sys
import urllib2

from subprocess import Popen, PIPE


def get_spec_version(specfile):
    ''' Return the version of a package by greping its spec file.
    :arg specfile, full path to the specfile to grep.
    '''
    version = Popen(["grep", "Version:", specfile], stdout=PIPE).stdout.read()[:-1]
    return version.strip().split(' ')[-1:][0]


def load_upstream_repo(config_file):
    ''' Load all the R package information from upstream repository into
    a large dictionnary.
    :arg config_file, path to the repos.cfg containing information about
    the different upstream repository.
    '''
    parser = ConfigParser.ConfigParser()
    parser.read(config_file)
    packages = {}
    for section in parser.sections():
        if section.startswith('repo:'):
            url = parser.get(section, 'package')
            stream = urllib2.urlopen(url)
            content = stream.read()
            stream.close()
            upstream_packages = content.split('\n\n')
            for upstream_package in upstream_packages:
                if not upstream_package:
                    continue
                upstream_package = parseConfig(
                    upstream_package.split('\n'))
                #print upstream_package
                upstream_package['version'] = upstream_package['version'
                    ].replace('-', '.')
                try:
                    pack = packages[upstream_package['package']]
                    if pack['version'].split('.') < upstream_package[
                        'version'].split('.'):
                        packages[upstream_package['package']
                            ] = upstream_package
                except KeyError:
                    packages[upstream_package['package']
                        ] = upstream_package
    print '%s packages loaded' % len(packages.keys())
    return packages


def main():
    ''' Main function.
    Retrieve all the information from upstream.
    Reads all the spec file from the given directory and output the name
    of the packages to udpate.
    '''
    if len(sys.argv) == 1:
        print 'Not enough arguments specified. Usage: python ' \
            'check_spec_to_update.py path/to/r-repo-spec_folder'
        return 1
    if len(sys.argv) > 2:
        print 'Too many arguments specified. Usage: python ' \
            'update_rpms.py path/to/r-repo-spec_folder'
        return 2

    folder = os.path.expanduser(sys.argv[1])
    if not os.path.exists(folder):
        print 'The file "%s" could not be found' % folder
        return 3
    if not os.path.isdir(folder):
        print 'The folder "%s" has not been identified as being a folder' % folder
        return 4

    packages = load_upstream_repo('depgenerator/repos.cfg')

    filelist = os.listdir(folder)
    spec_files = []
    for filename in filelist:
        if filename.endswith('.spec') and filename.startswith('R-'):
            spec_files.append('%s/%s' % (folder, filename))

    cnt = 0
    notfound = []
    for spec in spec_files:
        name = spec.rsplit('R-', 1)[1].rsplit('.spec',1)[0]
        version = get_spec_version(spec)
        try:
            upstream_version = packages[name]['version']
        except KeyError:
            notfound.append(name)
            continue
        version = version.split('.')
        upstream_version = upstream_version.split('.')
        if upstream_version > version:
            cnt = cnt +1
            print name
    print '%s packages to update among %s packages' % (cnt,
        len(spec_files))
    print '%s packages not found upstream' % len(notfound)

    stream = open('notfound.txt', 'w')
    for pkg in notfound:
        stream.write(pkg + '\n')
    stream.close()


def parseConfig(package):
    ''' Returns a dictionnary of all the options available '''
    COMMENT_CHAR = '#' # char for comments
    OPTION_CHAR =  ':' # char used to separate option from value
    
    options = {}
    for line in package:
        # First, remove comments:
        if COMMENT_CHAR in line:
            # split on comment char, keep only the part before
            line, comment = line.split(COMMENT_CHAR, 1)
        # Second, find lines with an option=value:
        if OPTION_CHAR in line:
            # split on option char:
            option, value = line.split(OPTION_CHAR, 1)
            # strip spaces:
            option = option.strip().lower()
            value = value.strip()
            # store in dictionary:
            options[option] = value
        else:
            values = line.split(' ')
            for value in values:
                if value.strip() != '':
                    options[option] += ' ' +value.strip()

    return options


if __name__ == '__main__':
    main()
