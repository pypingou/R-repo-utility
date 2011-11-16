#!/usr/bin/python
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
Main functions for Rrepo2rpm
"""

import argparse
import ConfigParser
import logging
import re
import sys
import urllib2
from subprocess import Popen, PIPE
from distutils.version import LooseVersion as V


def format_dependencies(dependencies):
    """ Format the dependencies cleanning them as much as possible for rpm.
    """
    ignorelist = ['R']
    # Regular expression used to determine whether the string is a
    # version number
    versionmotif = re.compile('\d\.\d\.?\d?')
    char = {
            '\r': '',
            '(': ' ',
            ')': ' ',
            ',': ' ',
            '  ': ' ',
            }

    for key in char.keys():
        dependencies = dependencies.replace(key, char[key])
    dep_list = []

    for dep in dependencies.split(' '):
        if dep.strip():
            if  not ">" in dep \
            and not "<" in dep \
            and not "=" in dep \
            and len(versionmotif.findall(dep)) == 0 \
            and dep.strip() not in ignorelist:
                dep = dep.strip()
                dep_list.append(dep)

    return dep_list


def get_logger():
    """ Return a logger object."""
    logging.basicConfig()
    log = logging.getLogger('Rrepo2rpm')
    return log


def setup_parser():
    """
    Set the command line arguments.
    """
    parser = argparse.ArgumentParser(version='0.1.0',
    usage='%(prog)s [options]', prog="Rrepo2rpm")
    # General connection options
    parser.add_argument('--all-dep', action='store_true',
        help='Whether you want to use all the dependencies (Depends, Suggests and Imports) or just the Depends (default)')
    parser.add_argument('--config', default='repos.cfg',
        help='A repo configuration files, it will use repos.cfg by default in the current working directory.')
    parser.add_argument('--verbose', action='store_true',
        help='Give more info about what is going on.')
    parser.add_argument('--debug', action='store_true',
        help='Output bunches of debugging info.')
    return parser


def write_package_list(filename, pkg_list):
    """ Write the name of the packages in the given list of packages in
    the file with the given filename.
    """
    log = get_logger()
    try:
        stream = open(filename, 'w')
        for pkg in pkg_list:
            stream.write(pkg.get('Package') + '\n')
        stream.close()
        log.info('%s written' % filename)
    except IOError, err:
        log.info('An error occured while writing the file %s' % filename)
        log.debug('ERROR: %s' % err)
        print er


# Initial simple logging stuff
LOG = get_logger()
if '--debug' in sys.argv:
    LOG.setLevel(logging.DEBUG)
elif '--verbose' in sys.argv:
    LOG.setLevel(logging.INFO)



class RPackage(object):
    """
    This is the object used to store the information known about a package.
    """
    def __init__(self):
        """ Constructor. """
        self.__dict = {}

    def set(self, key, value):
        """ Set an attribute with a given value to the object.
        If the key is in 'Suggests', 'Depends', 'Imports' we will directly
        format the value the way we want them.
        """
        if key in ['Suggests', 'Depends', 'Imports']:
            if key in self.__dict.keys():
                self.__dict[key].extend(format_dependencies(value))
            else:
                self.__dict[key] = format_dependencies(value)
        else:
            if key in self.__dict.keys():
                self.__dict[key] = self.__dict[key] + value
            else:
                self.__dict[key] = value

    def get(self, key):
        """ Returned the requested attribute attributed to the given key.
        """
        if key in self.__dict.keys():
            return self.__dict[key]
        else:
            return None

    def get_dependencies(self, all_included=False):
        """ Returned the list of 'Depends'. If all_included is True,
        expend this list with 'Suggests' and 'Imports'.
        """
        if 'Depends' in self.__dict.keys():
            dep = self.__dict['Depends']
        else:
            dep = []
        if all_included:
            if 'Suggests' in self.__dict.keys():
                dep.extend(self.__dict['Suggests'])
            if 'Imports' in self.__dict.keys():
                dep.extend(self.__dict['Imports'])
        return dep

    def __str__(self):
        """ Give us a nice representation of the object when needed for
        debugging.
        """
        string = ''
        for key in self.__dict.keys():
            string = string + '%s: %s\n' %(key, self.__dict[key])
        return string


class Rrepo2rpm(object):
    """ Main class for the project Rrepo2rpm.
    This class provides the functions to
    1) retrieve the list of packages provided by R by default.
    2) load the list of all packages in the configured repositories.
    3) find the order in which they should be built.
    4) generate the output.
    """

    def __init__(self, config='repos.cfg'):
        """ Constructor.
        Instanciate the attributes of the object, loads the configuration
        file and generate the logger.
        """
        parser = ConfigParser.ConfigParser()
        parser.read(config)
        self.config = parser

        self.log = get_logger()
        self.log.setLevel(logging.INFO)

        self.provided = []
        self.packages = {}
        self.dependency_level = {}

    def __find_dependency_order(self, all_dep=False, cnt = 0):
        """ For all packages found, determine in which order it should
        be built.
        """
        start = len(self.packages.keys())

        if cnt not in self.dependency_level.keys():
            self.dependency_level[cnt] = []

        known = self.provided[:]
        for el in self.dependency_level.values():
            for pkg in el:
                known.append(pkg.get('Package'))

        for pkg_name in self.packages.keys():
            if pkg_name in self.provided:
                self.log.debug('%s is already provided' % pkg_name)
                del self.packages[pkg_name]
            elif pkg_name in self.dependency_level.values():
                self.log.error('% is present twice, something wrong happened' \
                    % pkg_name)
                sys.exit(1)
            else:
                package = self.packages[pkg_name]
                dep = set(package.get_dependencies(all_dep))
                tmpknown = set(known)
                if dep.issubset(tmpknown):
                    self.dependency_level[cnt].append(package)
                    del self.packages[pkg_name]
        
        stop = len(self.packages.keys())
        self.log.info('Loop: %s, started with %s and ending with %s (added %s)' % (
            cnt, start, stop, start - stop))
        if start != stop:
            self.__find_dependency_order(all_dep=all_dep, cnt = cnt + 1)
        else:
            self.log.info('Could not add any more packages to buid, stopping')
            del self.dependency_level[cnt]
            self.log.info('%s packages are provided' % len(self.provided))
            cnt = sum([len(el) for el in self.dependency_level.values()])
            self.log.info('%s packages can be built' % cnt)
            self.log.info('%s packages had missing dependencies' % len(
                self.packages.keys()))

    def __get_provided_library(self):
        """
        This function returns the list of R libraries provided by the
        R-core rpm.
        """
        provided = Popen(['repoquery', '--provides', 'R-core'], 
            stdout=PIPE).stdout.read()
        self.provided = []
        for prov in provided.split('\n'):
            if prov.startswith('R-'):
                self.provided.append(prov.split(' ')[0].split('R-')[1])

    def __load_repos(self):
        """
        For all repos defined in /etc/R2spec/repos.cfg, retrieve all the
        packages and add them to the list if
        1) it is the latest version
        2) they are not already provided
        """
        repo = None
        version = None
        for section in self.config.sections():
            if section.startswith('repo:'):
                url = self.config.get(section, 'package')
                self.log.debug('Parsing repo: %s' % section)
                try:
                    stream = urllib2.urlopen(url)
                    content = stream.read()
                    stream.close()
                    self.__parse_repo_packages(section, content)
                    self.log.debug('%s done' % section)
                except IOError, err:
                    self.log.info('Something went wrong while retrieving info for repo %s'
                        % url)
                    self.log.debug('ERROR: %s' % err)
        self.log.info('TOTAL: %s packages retrieved' % (len(self.packages.keys())))

    def __parse_repo_packages(self, repo, content):
        """
        This function receive the content of a PACKAGES file from a repo
        and parse it to extract all packages and their information.
        """
        cnt = 0
        for line in content.split('\n'):
            if line.strip() != '':
                if ':' in line:
                    key, value = line.split(':')
                    key = key.strip()
                else:
                    value = line.strip()
                value = value.strip()
                if key == 'Package':
                    cnt = cnt + 1
                    package = RPackage()
                    package.set('repo', repo)
                    package.set(key, value)
                else:
                    package.set(key, value)
            else:
                name = package.get('Package')
                if name not in self.packages.keys():
                    self.log.debug('Adding package: %s'  % (name))
                    self.packages[name] = package
                else:
                    self.log.debug('%s already retrieved' % (name))
                    old_pkg = self.packages[name]
                    self.log.debug('  repo %s vs %s' % (old_pkg.get('repo'),
                        package.get('repo')))
                    old_version = old_pkg.get('Version').replace('-', '.')
                    new_version = package.get('Version').replace('-', '.')
                    if V(old_version) < V(new_version):
                        self.log.debug('    Using %s version which is newer' % package.get('repo'))
                        self.packages[name] = package
        self.log.debug('%s packages retrieved' % (cnt))

    def main(self, args):
        """
        This is the main function which actually does the work.
        """
        self.__get_provided_library()
        self.__load_repos()
        self.__find_dependency_order(all_dep=args.all_dep)
        self.__generate_output()

    def __generate_output(self):
        """ Write down to file the information we have collected.
        """
        filename = 'package_with_missing_dependencies'
        keys = self.packages.keys()
        keys.sort()
        pkgs = [self.packages[key] for key in keys]
        write_package_list(filename, pkgs)

        for level in self.dependency_level.keys():
            filename = 'level_%s_packages' % level
            write_package_list(filename, self.dependency_level[level])


if __name__ == '__main__':
    parser = setup_parser()
    args = parser.parse_args()
    rrepo = Rrepo2rpm(args.config)
    rrepo.main(args)
