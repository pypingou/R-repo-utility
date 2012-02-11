#!/usr/bin/env python
#-*- coding: utf-8 -*-

#***********************************************
# update_rpms
#
# update_rpms reads a file containing the name of
# outdated package, update their spec file and
# rebuild them using more
#
# Made the 26th April 2010
# by Pierre-Yves chibon
# Updated on February 11 2012 by Pierre-Yves Chibon
# for the R-repo project
#
#
# Distributed under License GPLv3 or later
# You can find a copy of this license on the website
# http://www.gnu.org/licenses/gpl.html
#
#***********************************************

import urllib, re, os, subprocess, sys, datetime
from r2spec.r2spec_obj import RPackage
from r2spec import get_rpm_tag
from r2spec.build import Build

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

def addToKnown(known, deps, source, filterlist):
    ''' Add all the dependencies given in deps and the source
        to the list given as known.
    '''
    for dep in deps:
        p =  parseConfig( dep.split('\n') )
        if p != {}:
            if p['package'] in filterlist:
                p['source'] = source
                known[ p['package'] ] = p
    return known

def updateSpec(specfile, new_version):
    ''' For a given package name, find the spec in the %_specdir and
       update its version, release and changelog
    '''
    new_version = new_version.replace('-','.')
    if not os.path.exists(specfile):
        print 'ERROR: spec file "%s" not found' % specfile
        return 1
    else:
        print ' ** Updating spec: %s' % specfile
        f = open(specfile)
        s = f.read()
        f.close()
        spec = s.split('\n')
        
        cnt = 0
        for line in spec:
            # Update version
            if line.startswith('Version'):
                newline = line.strip().split(' ')
                newline[len(newline) -1] = new_version
                newline = ' '.join(newline)
                if newline != line:
                    print ' Update version'
                    spec[cnt] = newline
            # Update release
            if line.startswith('Release'):
                newline = line.strip().split(' ')
                newline[len(newline) -1] = '1%{dist}'
                newline = ' '.join(newline)
                if newline != line:
                    print ' Update release'
                    spec[cnt] = newline
            # Update changelog
            if line.startswith('%changelog'):
                date= datetime.datetime.now().strftime('%a %b %d %Y')
                string1 = '* %s Pierre-Yves Chibon <pingou@pingoured.fr> %s-1' %(date, new_version)
                string2 ='- Update to version %s'%(new_version)
                if spec[cnt+1] != string1:
                    print ' Update changelog'
                    spec.insert(cnt+1, string1)
                    spec.insert(cnt+2, string2)
                    spec.insert(cnt+3, '')
            
            # Counter for the rows
            cnt = cnt + 1
            
    # Write down the new spec
    spec = '\n'.join(spec)
    if spec != s:
        f = open(specfile, 'w')
        s = f.write(spec)
        f.close()
    
    return 0

def downloadSources(url):
    ''' For a given url to a tarball, check if the sources
       are already in the %_sourcedir, else download them.
    '''
    start_folder = os.getcwd()
    os.chdir(get_rpm_tag('_sourcedir'))
    tarball = url.rsplit('/',1)[1]
    if os.path.exists(tarball):
        print '%s already there, no need to re-download it'%tarball
    else:
        cmd = 'wget %s' % url
        outcode = subprocess.call(cmd , shell=True)
    os.chdir(start_folder)

def build(specfile, mock_config, mock_resultdir):
    ''' For a given package, build the new version.
    '''
    print ' Building %s' % specfile
    build = Build()
    build.build(specfile, mock_config=mock_config,
        mock_resultdir=mock_resultdir)
    build.outcode

def addSpec(package):
    ''' Add the spec file to the git.
    '''
    print ' Add to git R-%s.spec' %package
    cmd = 'git add R-%s.spec'%package
    print cmd
    outcode = subprocess.call(cmd , shell=True)
    return outcode

def main():
    ''' Main function.
    This function reads the content of the file provided. This file
    should contain the name of the packages to update.
    Their spec files are updated and build using mock.
    '''
    if len(sys.argv) < 2:
        print 'Not enough arguments specified. Usage: python update_rpms.py'\
        ' outdate_rpms path/to/R-repo-spec_folder'
        return 1
    if len(sys.argv) > 3:
        print 'Too many arguments specified. Usage: python update_rpms.py outdate_rpms'
        return 2

    if not os.path.exists(sys.argv[1]):
        print 'The file "%s" could not be found' % sys.argv[1]
        return 3

    folder = os.path.expanduser(sys.argv[2])
    if not os.path.exists(folder):
        print 'The file "%s" could not be found' % folder
        return 4
    if not os.path.isdir(folder):
        print 'The folder "%s" has not been identified as being a folder' % folder
        return 5

    outdatedlist = []
    stream = open(sys.argv[1])
    outdatelist = []
    for line in stream.readlines():
        outdatedlist.append(line.strip())
    stream.close()

    print '%s packages to update' %len(outdatedlist)

    urls = [
            'http://www.bioconductor.org/packages/release/data/experiment/src/contrib/PACKAGES',
            'http://www.bioconductor.org/packages/release/data/annotation/src/contrib/PACKAGES',
            'http://www.bioconductor.org/packages/release/bioc/src/contrib/PACKAGES',
            'http://cran-mirror.cs.uu.nl/src/contrib/PACKAGES',
            'http://cran.at.r-project.org/src/contrib/PACKAGES',
            'http://r-forge.r-project.org/src/contrib/PACKAGES',
            ]

    upstream = {}
    for url in urls:
        f = urllib.urlopen(url)
        s = f.read()
        f.close()
        upstream = addToKnown( upstream, s.split('\n\n'), url, outdatedlist )

    print '%s packages found in the repository' %len(upstream)

    updatefailed = []
    buildfailed = []
    ok = []
    mock_resultdir = '/data/mock/results/'
    for package in outdatedlist:
        if package != '':
            version = upstream[package]['version']
            specfile = folder + 'R-%s.spec' % package
            code = updateSpec(specfile, version)
            if code == 1:
                updatefailed.append(package)
            downloadSources( upstream[package]['source'].split(
                'PACKAGES')[0] + '%s_%s.tar.gz' %(package, version) )
            for mock in ['epel-6-i386', 'epel-6-x86_64']:
                try:
                    outcode = build(specfile, mock, mock_resultdir)
                except:
                    print 'Could not build %s' % specfile
                    buildfailed.append(package)
                    continue
                if outcode:
                    buildfailed.append(package)
                if not code and not outcode:
                    ok.append(package)

    print '%s packages were successfully updated' %len(ok)
    print '%s spec failed to be updated' %len(updatefailed)
    print '%s package failed to be build' %len(buildfailed)

if __name__ == '__main__':
    main()
