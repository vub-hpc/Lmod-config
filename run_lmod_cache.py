#!/usr/bin/python3 -E
# -*- encoding: utf-8 -*-
#
# Copyright 2016-2016 Ghent University
#
# This file is part of Lmod-UGent,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://www.vscentrum.be),
# the Flemish Research Foundation (FWO) (http://www.fwo.be/en)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
"""
This script runs the Lmod cache creation script.
It also can check if the age of the current age and will report if it's too old.

@author: Ward Poelmans (Vrije Universiteit Brussel)
@author: Samuel Moors (Vrije Universiteit Brussel)
"""
import glob
import json
import os
import sys
import time

from vsc.utils import fancylogger
from vsc.utils.run import run as run_simple, asyncloop
from vsc.utils.generaloption import SimpleOption

# log setup
logger = fancylogger.getLogger(__name__)
fancylogger.logToScreen(True)
fancylogger.setLogLevelInfo()

MODULES_BASEDIR = '/apps/brussel/RL9'


def _get_archs(archs, basedir):
    """Helper to get a list of all architectures in basedir"""
    if not archs:
        return os.listdir(basedir)
    return archs


def _get_lmod_dir():
    """Helper to resolve Lmod directory."""
    lmod_dir = os.environ.get("LMOD_DIR")
    if not lmod_dir:
        raise RuntimeError("Cannot find $LMOD_DIR in the environment.")
    return lmod_dir


def run_cache_create(basedir, archs=None):
    """Run the script to create the Lmod cache"""
    lmod_dir = _get_lmod_dir()

    for arch in _get_archs(archs, basedir):
        modpath = os.path.join(basedir, arch, "modules")
        if not os.path.isdir(modpath):
            continue
        logger.info("Creating cache for %s", arch)
        modsubpathglob = os.path.join(modpath, "20[0-9][0-9][ab]", "all")
        modsubpathsystem = glob.glob(os.path.join(modpath, 'system', 'all'))
        modsubpaths = os.pathsep.join(sorted(glob.glob(modsubpathglob)) + modsubpathsystem)

        cachedir = os.path.join(basedir, arch, "cacheDir")
        systemfile = os.path.join(cachedir, "system.txt")

        cmd = f"{lmod_dir}/update_lmod_system_cache_files -d {cachedir} -t {systemfile} {modsubpaths}"
        exitcode, msg = run_simple(cmd)
        if exitcode != 0:
            return exitcode, msg

    return 0, ''


def run_spider_create(basedir, archs=None, modulepath=None):
    """Run the script to create the Lmod cache"""
    lmod_dir = _get_lmod_dir()

    for arch in _get_archs(archs, basedir):
        cachedir = os.path.join(basedir, arch, "cacheDir")
        jsonfile = os.path.join(cachedir, "hydra.json")

        if not modulepath:
            modulepath = os.getenv('MODULEPATH')
            if not modulepath:
                raise RuntimeError("Cannot find $MODULEPATH in the environment.")

        logger.info("Creating Spider cache for %s", arch)
        cmd = f'{lmod_dir}/spider -o spider-json {modulepath}'
        exitcode, result = asyncloop(cmd)
        if exitcode != 0:
            return exitcode, result

        with open(jsonfile, 'w') as f:
            f.write(result)


def find_oldest_cache(basedir, archs=None):
    """Find the oldest Lmod cache"""
    oldest = time.time()

    for arch in _get_archs(archs, basedir):
        systemfile = os.path.join(basedir, arch, "cacheDir", "system.txt")
        if not os.path.isfile(systemfile):
            continue
        timestamp = os.stat(systemfile)

        if timestamp.st_mtime < oldest:
            oldest = timestamp.st_mtime

    logger.debug("Oldest cache is %s", oldest)

    return oldest


def get_lmod_config():
    """Get the modules root and cache path from the Lmod config"""
    lmod_cmd = os.environ.get("LMOD_CMD", None)
    if not lmod_cmd:
        raise RuntimeError("Cannot find $LMOD_CMD in the environment.")

    ec, out = run_simple(f"{lmod_cmd} bash --config-json")
    if ec != 0:
        raise RuntimeError(f"Failed to get Lmod configuration: {out}")

    try:
        lmodconfig = json.loads(out)

        config = {
            'modules_root': lmodconfig['configT']['mpath_root'],
            'cache_dir': lmodconfig['cache'][0][0],
            'cache_timestamp': lmodconfig['cache'][0][1],
        }
        logger.debug("Found Lmod config: %s", config)
    except (ValueError, KeyError, IndexError, TypeError) as err:
        raise RuntimeError(f"Failed to parse the Lmod configuration: {err}") from err

    return config


def main():
    """
    Set the options and initiates the main run.
    """
    options = {
        'create-cache': ('Create the Lmod cache', None, 'store_true', False),
        'create-spider-cache': ('Run the spider command to generate a spider cache', None, 'store_true', False),
        'architecture': ('Specify the architecture to create the cache for. Default: all architectures',
                         'strlist', 'add', None),
        'freshness-threshold': ('The interval in minutes for how long we consider the cache to be fresh',
                                'int', 'store', 60 * 7),  # cron runs every 6 hours
        'module-basedir': ('Specify the base dir for the modules', 'str', 'store', MODULES_BASEDIR),
        'check-cache-age': ('Show age in seconds of oldest cache and exit', None, 'store_true', False),
        'modulepath': ('Specify the module path. Default: $MODULEPATH', 'str', 'store', False),
    }
    opts = SimpleOption(options)

    timestamp = find_oldest_cache(opts.options.module_basedir, archs=opts.options.architecture)
    age = time.time() - timestamp

    if opts.options.check_cache_age:
        print(int(age))
        sys.exit()

    if opts.options.create_spider_cache:
        try:
            opts.log.info("Updating the Spider cache")
            run_spider_create(opts.options.module_basedir, archs=opts.options.architecture,
                              modulepath=opts.options.modulepath)
            opts.log.info("Spider cache updated.")
        except RuntimeError as err:
            logger.exception("Failed to update Spider cache: %s", err)
            sys.exit(5)
        except Exception as err:  # pylint: disable=W0703
            logger.exception("critical exception caught: %s", err)
            sys.exit(6)

    opts.log.info("Checking the Lmod cache freshness")
    # give a warning when the cache is older than --freshness-threshold
    if age > opts.options.freshness_threshold * 60:
        errmsg = "Lmod cache is not fresh"
        logger.warning(errmsg)

    if opts.options.create_cache:
        try:
            opts.log.info("Updating the Lmod cache")
            exitcode, msg = run_cache_create(opts.options.module_basedir, archs=opts.options.architecture)
            if exitcode != 0:
                logger.error("Lmod cache update failed: %s", msg)
                sys.exit(1)

            opts.log.info("Lmod cache updated.")
        except RuntimeError as err:
            logger.exception("Failed to update Lmod cache: %s", err)
            sys.exit(3)
        except Exception as err:  # pylint: disable=W0703
            logger.exception("critical exception caught: %s", err)
            sys.exit(4)


if __name__ == '__main__':
    main()
