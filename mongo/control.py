#! /usr/bin/env python2
# Simple python script to control a fuse filesystem
#
# Supports the following commands:
#
# Server
# ------------
# start - start and mount a fuse filesystem and log output to a file
# stop_all - stop the fuse filesystems
# getlog - get the log file from start
#
# Client
# -----------
# add_fault - add a fault
# clear_faults - clear all the faults
#


# Example
#  client.set_fault(['write'], False, 0, 100000, ".*watchdog_probe.txt", False, 50000000, False)

from __future__ import absolute_import, print_function

import argparse
import io
import logging
import os
import subprocess
import sys
import time
os.sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../cookbook/gen-py"))
from typing import Any

# Generated Thrift Proxy
from server import server
from server.ttypes import *

from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol

CHARYBDEFS_BIN='charybdefs'

def get_bin_path():
    # type: () -> str
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), CHARYBDEFS_BIN)

def check_mounts(mount_path):
    # type: (str) -> bool
    """Check /proc/mounts if the file system is mounted."""
    with io.open('/proc/mounts') as fh:
        mounts = fh.readlines()

    for mount in mounts:
        if CHARYBDEFS_BIN in mount and mount_path in mount:
            return True

    return False

def start_args(args):
    # type: (Any) -> None
    start(args.fuse_mount, args.backing_path, args.log_file)

def start(fuse_mount, backing_path, log_file):
    # type: (str, str, str) -> None
    """Start the fuse file system."""
    if not os.path.isdir(fuse_mount):
        raise ValueError("Fuse mount %s is not a directory" % (fuse_mount))

    if not os.path.isdir(backing_path):
        raise ValueError("Backing Directory %s is not a directory" % (backing_path))

    log_file = os.path.abspath(log_file)

    # TODO: remove the nohup file here

    cmd = ['nohup', '/bin/sh', 
        '-c', '%s %s -omodules=subdir,subdir=%s,allow_other -f 2>&1 > %s' % 
        (get_bin_path(), fuse_mount, backing_path, log_file)]
    logging.info("Starting server %s" % (cmd))

    # Launch it, this will leave "sh", and "charydebfs" in the background.
    # Create pipes so that we do not inherit our parent handles. This ensures mongo shell
    # does not reading one of control.py's handles.
    subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Give it some time to mount
    retry_count = 0
    fuse_mount_real = os.path.realpath(fuse_mount)
    while retry_count < 10:
        logging.info("Checking file system is mounted.")
        is_mounted = check_mounts(fuse_mount_real)
        if is_mounted:
            break

        time.sleep(1)

        retry_count += 1
    
    if not is_mounted:
        # TODO: cat the log files here
        raise ValueError("Could not find mounted file system at '%s'" % (fuse_mount))

    logging.info("FUSE started.")


def stop_all_args(args):
    # type: (Any) -> None
    stop_all(args.fuse_mount)

def stop_all(fuse_mount):
    # type: (str) -> None
    """Stop all FUSE file systems"""
    logging.info("Kill all processes name '%s'" % (CHARYBDEFS_BIN))
    # Do not SIGKILL so we do not need to force umount later.
    subprocess.call(['pkill', '--echo', CHARYBDEFS_BIN])

    # Ignore the return code as it may not be mounted
    logging.info("Unmounting '%s'" % (fuse_mount))
    subprocess.call(['umount', fuse_mount])


def get_log_args(args):
    # type: (Any) -> None
    """Get the log file."""
    get_log(args.log_file)

def get_log(log_file):
    # type: (str) -> None
    log_file = os.path.abspath(log_file)
    pass

# -----------
# add_fault - add a fault
# clear_faults - clear all the faults

def connect():
    # type: () -> server.Client
    """Connect to the FUSE server."""
    transport = TSocket.TSocket('127.0.0.1', 9787)
    transport = TTransport.TBufferedTransport(transport)
    protocol = TBinaryProtocol.TBinaryProtocol(transport)
    client = server.Client(protocol)
    transport.open()
    return client


def clear_all_faults_args(args):
    # type: (Any) -> None
    """Clear all the faults, assumes server is started."""
    client = connect()

    logging.info("Clearing all faults")
    client.clear_all_faults()

def set_fault_args(args):
    # type: (Any) -> None
    """Set a fault, assumes server is started."""
    set_fault(args.methods, args.random, args.errno, args.probability, args.regexp, args.delay_us)

def set_fault(methods, random, errno, probability, regexp, delay_us):
    # type: (List[str], bool, int, int, str, int) -> None
    """Set a fault, assumes server is started."""
    if probability < 0 or probability > 100000:
        raise ValueError("Probably must be less then 100000.")

    logging.info("Setting fault: Methods=%s Random=%s Errno=%s Probability=%s Regexp=%s Delay_us=%s"
        % (methods, random, errno, probability, regexp, delay_us))

    client = connect()

    # Do not kill caller or auto_delay
    client.set_fault(methods, random, errno, probability, regexp, False, delay_us, False)

def main():
    # type: () -> None
    """Main Entry point."""
    parser = argparse.ArgumentParser(description='MongoDB FUSE Controller.')

    parser.add_argument('-v', "--verbose", action='store_true', help="Enable verbose logging")

    sub = parser.add_subparsers(title="Controller subcommands", help="sub-command help")

    parser_start = sub.add_parser('start', help='Start fuse')
    parser_start.add_argument("--fuse_mount", required="True", help="Fuse Mount Path")
    parser_start.add_argument("--backing_path", required="True", help="Backing Directory")
    parser_start.add_argument("--log_file", required="True", help="Log File Path")
    parser_start.set_defaults(func=start_args)

    parser_stop_all = sub.add_parser('stop_all', help='Stop all FUSE filesystems')
    parser_stop_all.add_argument("--fuse_mount", required="True", help="Fuse Mount Path")
    parser_stop_all.set_defaults(func=stop_all_args)

    parser_get_log = sub.add_parser('get_log', help='Get the log file')
    parser_get_log.add_argument("--log_file", required="True", help="Log File Path")
    parser_get_log.set_defaults(func=get_log_args)

    parser_clear_all_faults = sub.add_parser('clear_all_faults', help='Clear all faults')
    parser_clear_all_faults.set_defaults(func=clear_all_faults_args)

    parser_set_fault = sub.add_parser('set_fault', help='Set a fault')
    parser_set_fault.add_argument("--methods", nargs='*', required="True", help="Methods to fault")
    parser_set_fault.add_argument("--random", action='store_true', help="File Path")
    parser_set_fault.add_argument("--errno", type=int, required="True", help="Error to inject")
    parser_set_fault.add_argument("--probability", type=int, required="True", help="Chance to inject, over 100,000")
    parser_set_fault.add_argument("--regexp", required="True", help="File Path")
    parser_set_fault.add_argument("--delay_us", type=int, required="True", help="Delay in micro seconds")
    parser_set_fault.set_defaults(func=set_fault_args)


    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    args.func(args)

    sys.exit(0)

if __name__ == "__main__":
    main()
