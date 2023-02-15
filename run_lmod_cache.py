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
"""
import glob
import json
import os
import sys
import time
from vsc.utils import fancylogger
from vsc.utils.run import run as run_simple
from vsc.utils.generaloption import SimpleOption

# log setup
logger = fancylogger.getLogger(__name__)
fancylogger.logToScreen(True)
fancylogger.setLogLevelInfo()

MODULES_BASEDIR = '/apps/brussel/CO7'


def run_cache_create(basedir, archs=None):
    """Run the script to create the Lmod cache"""
    lmod_dir = os.environ.get("LMOD_DIR", None)
    if not lmod_dir:
        raise RuntimeError("Cannot find $LMOD_DIR in the environment.")

    if not archs:
        archs = os.listdir(basedir)

    for arch in archs:
        modpath = os.path.join(basedir, arch, "modules")
        if not os.path.isdir(modpath):
            continue
        logger.debug("Creating cache for %s", arch)
        modsubpathglob = os.path.join(modpath, "20[0-9][0-9][ab]", "all")
        modsubpaths = os.pathsep.join(sorted(glob.glob(modsubpathglob)))

        cachedir = os.path.join(basedir, arch, "cacheDir")
        systemfile = os.path.join(cachedir, "system.txt")

        cmd = f"{lmod_dir}/update_lmod_system_cache_files -d {cachedir} -t {systemfile} {modsubpaths}"
        exitcode, msg = run_simple(cmd)
        if exitcode != 0:
            return exitcode, msg

    return 0, ''


def find_oldest_cache(basedir, archs=None):
    """Find the oldest Lmod cache"""
    if not archs:
        archs = os.listdir(basedir)

    oldest = time.time()

    for arch in archs:
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
        raise RuntimeError("Failed to get Lmod configuration: %s", out)

    try:
        lmodconfig = json.loads(out)

        config = {
            'modules_root': lmodconfig['configT']['mpath_root'],
            'cache_dir': lmodconfig['cache'][0][0],
            'cache_timestamp': lmodconfig['cache'][0][1],
        }
        logger.debug("Found Lmod config: %s", config)
    except (ValueError, KeyError, IndexError, TypeError) as err:
        raise RuntimeError("Failed to parse the Lmod configuration: %s", err)

    return config


def main():
    """
    Set the options and initiates the main run.
    """
    options = {
        'create-cache': ('Create the Lmod cache', None, 'store_true', False),
        'architecture': ('Specify the architecture to create the cache for. Default: all architectures',
                         'strlist', 'add', None),
        'freshness-threshold': ('The interval in minutes for how long we consider the cache to be fresh',
                                'int', 'store', 60*4),  # cron runs every 3 hours
        'module-basedir': ('Specify the base dir for the modules', 'str', 'store', MODULES_BASEDIR),
        'check-cache-age': ('Show age in seconds of oldest cache and exit', None, 'store_true', False),
    }
    opts = SimpleOption(options)

    timestamp = find_oldest_cache(opts.options.module_basedir, archs=opts.options.architecture)
    age = time.time() - timestamp

    if opts.options.check_cache_age:
        print(int(age))
        sys.exit()

    try:
        if opts.options.create_cache:
            opts.log.info("Updating the Lmod cache")
            exitcode, msg = run_cache_create(opts.options.module_basedir, archs=opts.options.architecture)
            if exitcode != 0:
                logger.error("Lmod cache update failed: %s", msg)
                opts.critical("Lmod cache update failed")

        opts.log.info("Checking the Lmod cache freshness")
        # give a warning when the cache is older than --freshness-threshold
        if age > opts.options.freshness_threshold * 60:
            errmsg = "Lmod cache is not fresh"
            logger.warn(errmsg)
            opts.warning(errmsg)

    except RuntimeError as err:
        logger.exception("Failed to update Lmod cache: %s", err)
        opts.critical("Failed to update Lmod cache. See logs.")
    except Exception as err:  # pylint: disable=W0703
        logger.exception("critical exception caught: %s", err)
        opts.critical("Script failed because of uncaught exception. See logs.")

    if opts.options.create_cache:
        opts.log.info("Lmod cache updated.")
    else:
        opts.log.info("Lmod cache is still fresh.")


if __name__ == '__main__':
    main()
