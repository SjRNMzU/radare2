#!/usr/bin/env python3
"""Meson build for radare2"""

import argparse
import glob
import logging
import os
import re
import shutil
import subprocess
import sys

BUILDDIR = 'build'
BACKENDS = ['ninja', 'vs2015', 'vs2017', 'vs2019']

PATH_FMT = {}
R2_PATH = {
    'R2_LIBDIR': r'lib',
    'R2_INCDIR': r'include',
    'R2_DATDIR': r'share',
    'R2_WWWROOT': r'{R2_DATDIR}\www',
    'R2_SDB': r'{R2_DATDIR}',
    'R2_ZIGNS': r'{R2_DATDIR}\zigns',
    'R2_THEMES': r'{R2_DATDIR}\cons',
    'R2_FORTUNES': r'{R2_DATDIR}\doc',
    'R2_FLAGS': r'{R2_DATDIR}\flag',
    'R2_HUD': r'{R2_DATDIR}\hud'
}

MESON = None
ROOT = None
log = None

def set_global_variables():
    """[R_API] Set global variables"""
    global log
    global ROOT
    global MESON

    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir))

    logging.basicConfig(format='[%(name)s][%(levelname)s]: %(message)s',
                        level=logging.DEBUG)
    log = logging.getLogger('r2-meson')

    with open(os.path.join(ROOT, 'configure.acr')) as f:
        f.readline()
        version = f.readline().split()[1].rstrip()

    if os.name == 'nt':
        meson = os.path.join(os.path.dirname(sys.executable), 'Scripts', 'meson.exe')
        if os.path.exists(meson):
            MESON = [meson]
        else:
            meson = os.path.join(os.path.dirname(sys.executable), 'Scripts', 'meson.py')
            MESON = [sys.executable, meson]
    else:
        MESON = ['meson']

    PATH_FMT['ROOT'] = ROOT
    PATH_FMT['R2_VERSION'] = version

    log.debug('Root: %s', ROOT)
    log.debug('Meson: %s', MESON)
    log.debug('Version: %s', version)

def meson(root, build, prefix=None, backend=None,
          release=False, shared=False, *, options=[]):
    """[R_API] Invoke meson"""
    command = MESON + [root, build]
    if prefix:
        command.append('--prefix={}'.format(prefix))
    if backend:
        command.append('--backend={}'.format(backend))
    if release:
        command.append('--buildtype=release')
    if shared:
        command.append('--default-library=shared')
    else:
        command.append('--default-library=static')
    if options:
        command.extend(options)

    log.debug('Invoking meson: %s', command)
    ret = subprocess.call(command)
    if ret != 0:
        log.error('Meson error. Exiting.')
        sys.exit(1)

def ninja(folder, *targets):
    """[R_API] Invoke ninja"""
    command = ['ninja', '-C', folder]
    if targets:
        command.extend(targets)
    log.debug('Invoking ninja: %s', command)
    ret = subprocess.call(command)
    if ret != 0:
        log.error('Ninja error. Exiting.')
        sys.exit(1)

def msbuild(project, *params):
    """[R_API] Invoke MSbuild"""
    command = ['msbuild', project]
    if params:
        command.extend(params)
    log.info('Invoking MSbuild: %s', command)
    ret = subprocess.call(command)
    if ret != 0:
        log.error('MSbuild error. Exiting.')
        sys.exit(1)

def copytree(src, dst, exclude=()):
    src = src.format(**PATH_FMT)
    dst = dst.format(**PATH_FMT).format(**PATH_FMT)
    log.debug('copytree "%s" -> "%s"', src, dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*exclude) if exclude else None)

def move(src, dst):
    src = src.format(**PATH_FMT)
    dst = dst.format(**PATH_FMT).format(**PATH_FMT)
    term = os.path.sep if os.path.isdir(dst) else ''
    log.debug('move "%s" -> "%s%s"', src, dst, term)
    for file in glob.iglob(src):
        shutil.move(file, dst)

def copy(src, dst):
    src = src.format(**PATH_FMT)
    dst = dst.format(**PATH_FMT).format(**PATH_FMT)
    term = os.path.sep if os.path.isdir(dst) else ''
    log.debug('copy "%s" -> "%s%s"', src, dst, term)
    for file in glob.iglob(src, recursive='**' in src):
        shutil.copy2(file, dst)

def makedirs(path):
    path = path.format(**PATH_FMT).format(**PATH_FMT)
    log.debug('makedirs "%s"', path)
    os.makedirs(path)

def xp_compat(builddir):
    log.info('Running XP compat script')

    with open(os.path.join(builddir, 'REGEN.vcxproj'), 'r') as f:
        version = re.search('<PlatformToolset>(.*)</PlatformToolset>', f.read()).group(1)

    if version.endswith('_xp'):
        log.info('Skipping %s', builddir)
        return

    log.debug('Translating from %s to %s_xp', version, version)
    newversion = version+'_xp'

    for f in glob.iglob(os.path.join(builddir, '**', '*.vcxproj'), recursive=True):
        with open(f, 'r') as proj:
            c = proj.read()
        c = c.replace(version, newversion)
        with open(f, 'w') as proj:
            proj.write(c)
            log.debug("%s .. OK", f)

def win_dist(args):
    """Create r2 distribution for Windows"""
    builddir = os.path.join(ROOT, args.dir)
    PATH_FMT['DIST'] = args.install
    PATH_FMT['BUILDDIR'] = builddir

    makedirs(r'{DIST}')
    makedirs(r'{DIST}\bin')
    copy(r'{BUILDDIR}\binr\*\*.exe', r'{DIST}\bin')

    r2_bat_fname = args.install + r'\bin\r2.bat'
    log.debug('create "%s"', r2_bat_fname)
    with open(r2_bat_fname, 'w') as r2_bat:
        r2_bat.write('@"%~dp0\\radare2" %*\n')

    copy(r'{BUILDDIR}\libr\*\*.dll', r'{DIST}\bin')
    makedirs(r'{DIST}\{R2_LIBDIR}')
    if args.shared:
        copy(r'{BUILDDIR}\libr\*\*.lib', r'{DIST}\{R2_LIBDIR}')
    else:
        copy(r'{BUILDDIR}\libr\*\*.a', r'{DIST}\{R2_LIBDIR}')
    win_dist_libr2(install_webui=args.webui)

def win_dist_libr2(install_webui=False, **path_fmt):
    """[R_API] Add libr2 data/www/include/doc to dist directory"""
    PATH_FMT.update(path_fmt)

    if install_webui:
        copytree(r'{ROOT}\shlr\www', r'{DIST}\{R2_WWWROOT}')
    copytree(r'{ROOT}\libr\magic\d\default', r'{DIST}\{R2_SDB}\magic')
    makedirs(r'{DIST}\{R2_SDB}\syscall')
    copy(r'{BUILDDIR}\libr\syscall\d\*.sdb', r'{DIST}\{R2_SDB}\syscall')
    makedirs(r'{DIST}\{R2_SDB}\fcnsign')
    copy(r'{BUILDDIR}\libr\anal\d\*.sdb', r'{DIST}\{R2_SDB}\fcnsign')
    makedirs(r'{DIST}\{R2_SDB}\opcodes')
    copy(r'{BUILDDIR}\libr\asm\d\*.sdb', r'{DIST}\{R2_SDB}\opcodes')
    makedirs(r'{DIST}\{R2_INCDIR}\sdb')
    makedirs(r'{DIST}\{R2_INCDIR}\r_util')
    makedirs(r'{DIST}\{R2_INCDIR}\r_crypto')
    copy(r'{ROOT}\libr\include\*.h', r'{DIST}\{R2_INCDIR}')
    copy(r'{BUILDDIR}\r_version.h', r'{DIST}\{R2_INCDIR}')
    copy(r'{BUILDDIR}\r_userconf.h', r'{DIST}\{R2_INCDIR}')
    copy(r'{ROOT}\libr\include\sdb\*.h', r'{DIST}\{R2_INCDIR}\sdb')
    copy(r'{ROOT}\libr\include\r_util\*.h', r'{DIST}\{R2_INCDIR}\r_util')
    copy(r'{ROOT}\libr\include\r_crypto\*.h', r'{DIST}\{R2_INCDIR}\r_crypto')
    makedirs(r'{DIST}\{R2_FORTUNES}')
    copy(r'{ROOT}\doc\fortunes.*', r'{DIST}\{R2_FORTUNES}')
    copytree(r'{ROOT}\libr\bin\d', r'{DIST}\{R2_SDB}\format',
             exclude=('Makefile', 'meson.build', 'dll'))
    makedirs(r'{DIST}\{R2_SDB}\format\dll')
    copy(r'{BUILDDIR}\libr\bin\d\*.sdb', r'{DIST}\{R2_SDB}\format\dll')
    copytree(r'{ROOT}\libr\cons\d', r'{DIST}\{R2_THEMES}',
             exclude=('Makefile', 'meson.build'))
    makedirs(r'{DIST}\{R2_FLAGS}')
    copy(r'{BUILDDIR}\libr\flag\d\*.r2', r'{DIST}\{R2_FLAGS}')
    makedirs(r'{DIST}\{R2_HUD}')
    copy(r'{ROOT}\doc\hud', r'{DIST}\{R2_HUD}\main')

def build(args):
    """ Build radare2 """
    log.info('Building radare2')
    r2_builddir = os.path.join(ROOT, args.dir)
    options = ['-D%s' % x for x in args.options]
    if args.webui:
        options.append('-Duse_webui=true')
    if args.local:
        options.append('-Dlocal=true')
    if not os.path.exists(r2_builddir):
        meson(ROOT, r2_builddir, prefix=args.prefix, backend=args.backend,
              release=args.release, shared=args.shared, options=options)
    if args.backend != 'ninja':
        # XP support was dropped in Visual Studio 2019 v142 platform
        if args.backend != 'vs2019' and args.xp:
            xp_compat(r2_builddir)
        if not args.project:
            project = os.path.join(r2_builddir, 'radare2.sln')
            msbuild(project, '/m')
    else:
        ninja(r2_builddir)

def install(args):
    """ Install radare2 """
    if os.name == 'nt':
        win_dist(args)
        return
    log.warning('Install not implemented yet for this platform.')
    # TODO
    #if os.name == 'posix':
    #    os.system('DESTDIR="{destdir}" ninja -C {build} install'
    #            .format(destdir=destdir, build=args.dir))

def main():
    # Create logger and get applications paths
    set_global_variables()

    # Create parser
    parser = argparse.ArgumentParser(description='Mesonbuild scripts for radare2')
    # --asan=address,signed-integer-overflow for faster build
    parser.add_argument('--asan', nargs='?',
            const='address,undefined,signed-integer-overflow', metavar='sanitizers',
            help='Build radare2 with ASAN support (default sanitizers: %(const)s)')
    parser.add_argument('--project', action='store_true',
            help='Create a visual studio project and do not build.')
    parser.add_argument('--release', action='store_true',
            help='Set the build as Release (remove debug info)')
    parser.add_argument('--backend', choices=BACKENDS, default='ninja',
            help='Choose build backend (default: %(default)s)')
    parser.add_argument('--shared', action='store_true',
            help='Link dynamically (shared library) rather than statically')
    parser.add_argument('--local', action='store_true',
            help='Adds support for local/side-by-side installation (sets rpath if needed)')
    parser.add_argument('--prefix', default=None,
            help='Set project installation prefix')
    parser.add_argument('--dir', default=BUILDDIR, required=False,
            help='Destination build directory (default: %(default)s)')
    parser.add_argument('--alias', action='store_true',
            help='Show the "m" alias shell command')
    parser.add_argument('--xp', action='store_true',
            help='Adds support for Windows XP')
    parser.add_argument('--pull', action='store_true',
            help='git pull before building')
    parser.add_argument('--nosudo', action='store_true',
            help='Do not use sudo for install/symstall/uninstall')
    parser.add_argument('--uninstall', action='store_true',
            help='Uninstall')
    parser.add_argument('--symstall', action='store_true',
            help='Install using symlinks')
    parser.add_argument('--webui', action='store_true',
            help='Install WebUIs')
    if os.name == 'nt':
        parser.add_argument('--install', help='Installation directory')
    else:
        parser.add_argument('--install', action='store_true',
            help='Install radare2 after building')
    parser.add_argument('--options', nargs='*', default=[])
    args = parser.parse_args()
    if args.alias:
        print("alias m=\"" + os.path.abspath(__file__) + "\"")
        sys.exit(0);
    if args.asan:
        if os.uname().sysname == 'OpenBSD':
            log.error("Asan insupported under OpenBSD")
            sys.exit(1)
        cflags = os.environ.get('CFLAGS')
        if not cflags:
            cflags = ''
        os.environ['CFLAGS'] = cflags + ' -fsanitize=' + args.asan
        if os.uname().sysname != 'Darwin':
          ldflags = os.environ.get('LDFLAGS')
          if not ldflags:
              ldflags = ''
          os.environ['LDFLAGS'] = ldflags + ' -fsanitize=' + args.asan

    # Check arguments
    if args.pull:
        os.system('git pull')
    if args.project and args.backend == 'ninja':
        log.error('--project is not compatible with --backend ninja')
        sys.exit(1)
    if args.xp and args.backend in 'ninja':
        log.error('--xp is not compatible with --backend ninja')
        sys.exit(1)
    if args.xp and args.backend in 'vs2019':
        log.error('--xp is not compatible with --backend vs2019')
        sys.exit(1)
    if os.name == 'nt' and args.install and os.path.exists(args.install):
        log.error('%s already exists', args.install)
        sys.exit(1)
    if os.name == 'nt' and not args.prefix:
        args.prefix = os.path.join(ROOT, args.dir, 'priv_install_dir')
    for option in args.options:
        if '=' not in option:
            log.error('Invalid option: %s', option)
            sys.exit(1)
        key, value = option.split('=', 1)
        key = key.upper()
        if key not in R2_PATH:
            continue
        if os.path.isabs(value):
            log.error('Relative path is required: %s', option)
            sys.exit(1)
        R2_PATH[key] = os.path.normpath(value)

    PATH_FMT.update(R2_PATH)

    sudo = 'sudo '
    if args.nosudo:
        sudo = ''
    # Build it!
    log.debug('Arguments: %s', args)
    build(args)
    if args.uninstall:
        os.system(sudo + 'make uninstall PWD="$PWD/build" BTOP="$PWD/build/binr"')
    if args.install:
        install(args)
    if args.symstall:
        os.system(sudo + 'make symstall PWD="$PWD/build" BTOP="$PWD/build/binr"')

if __name__ == '__main__':
    main()
