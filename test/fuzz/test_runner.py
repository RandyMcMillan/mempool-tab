#!/usr/bin/env python3
# Copyright (c) 2019-2020 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Run fuzz test targets.
"""

import argparse
import configparser
import os
import sys
import subprocess
import logging


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description='''Run the fuzz targets with all inputs from the seed_dir once.''',
    )
    parser.add_argument(
        "-l",
        "--loglevel",
        dest="loglevel",
        default="INFO",
        help="log events at this level and higher to the console. Can be set to DEBUG, INFO, WARNING, ERROR or CRITICAL. Passing --loglevel DEBUG will output all logs to console.",
    )
    parser.add_argument(
        '--valgrind',
        action='store_true',
        help='If true, run fuzzing binaries under the valgrind memory error detector',
    )
    parser.add_argument(
        '-x',
        '--exclude',
        help="A comma-separated list of targets to exclude",
    )
    parser.add_argument(
        'seed_dir',
        help='The seed corpus to run on (must contain subfolders for each fuzz target).',
    )
    parser.add_argument(
        'target',
        nargs='*',
        help='The target(s) to run. Default is to run all targets.',
    )
    parser.add_argument(
        '--m_dir',
        help='Merge inputs from this directory into the seed_dir. Needs /target subdirectory.',
    )

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        format='%(message)s',
        level=int(args.loglevel) if args.loglevel.isdigit() else args.loglevel.upper(),
    )

    # Read config generated by configure.
    config = configparser.ConfigParser()
    configfile = os.path.abspath(os.path.dirname(__file__)) + "/../config.ini"
    config.read_file(open(configfile, encoding="utf8"))

    if not config["components"].getboolean("ENABLE_FUZZ"):
        logging.error("Must have fuzz targets built")
        sys.exit(1)

    # Build list of tests
    test_list_all = parse_test_list(makefile=os.path.join(config["environment"]["SRCDIR"], 'src', 'Makefile.test.include'))

    if not test_list_all:
        logging.error("No fuzz targets found")
        sys.exit(1)

    logging.debug("{} fuzz target(s) found: {}".format(len(test_list_all), " ".join(sorted(test_list_all))))

    args.target = args.target or test_list_all  # By default run all
    test_list_error = list(set(args.target).difference(set(test_list_all)))
    if test_list_error:
        logging.error("Unknown fuzz targets selected: {}".format(test_list_error))
    test_list_selection = list(set(test_list_all).intersection(set(args.target)))
    if not test_list_selection:
        logging.error("No fuzz targets selected")
    if args.exclude:
        for excluded_target in args.exclude.split(","):
            if excluded_target not in test_list_selection:
                logging.error("Target \"{}\" not found in current target list.".format(excluded_target))
                continue
            test_list_selection.remove(excluded_target)
    test_list_selection.sort()

    logging.info("{} of {} detected fuzz target(s) selected: {}".format(len(test_list_selection), len(test_list_all), " ".join(test_list_selection)))

    test_list_seedless = []
    for t in test_list_selection:
        corpus_path = os.path.join(args.seed_dir, t)
        if not os.path.exists(corpus_path) or len(os.listdir(corpus_path)) == 0:
            test_list_seedless.append(t)
    test_list_seedless.sort()
    if test_list_seedless:
        logging.info(
            "Fuzzing harnesses lacking a seed corpus: {}".format(
                " ".join(test_list_seedless)
            )
        )
        logging.info("Please consider adding a fuzz seed corpus at https://github.com/bitcoin-core/qa-assets")

    try:
        help_output = subprocess.run(
            args=[
                os.path.join(config["environment"]["BUILDDIR"], 'src', 'test', 'fuzz', test_list_selection[0]),
                '-help=1',
            ],
            timeout=20,
            check=True,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        ).stderr
        if "libFuzzer" not in help_output:
            logging.error("Must be built with libFuzzer")
            sys.exit(1)
    except subprocess.TimeoutExpired:
        logging.error("subprocess timed out: Currently only libFuzzer is supported")
        sys.exit(1)

    if args.m_dir:
        merge_inputs(
            corpus=args.seed_dir,
            test_list=test_list_selection,
            build_dir=config["environment"]["BUILDDIR"],
            merge_dir=args.m_dir,
        )
        return

    run_once(
        corpus=args.seed_dir,
        test_list=test_list_selection,
        build_dir=config["environment"]["BUILDDIR"],
        use_valgrind=args.valgrind,
    )


def merge_inputs(*, corpus, test_list, build_dir, merge_dir):
    logging.info("Merge the inputs in the passed dir into the seed_dir. Passed dir {}".format(merge_dir))
    for t in test_list:
        args = [
            os.path.join(build_dir, 'src', 'test', 'fuzz', t),
            '-merge=1',
            '-use_value_profile=1',  # Also done by oss-fuzz https://github.com/google/oss-fuzz/issues/1406#issuecomment-387790487
            os.path.join(corpus, t),
            os.path.join(merge_dir, t),
        ]
        os.makedirs(os.path.join(corpus, t), exist_ok=True)
        os.makedirs(os.path.join(merge_dir, t), exist_ok=True)
        logging.debug('Run {} with args {}'.format(t, args))
        output = subprocess.run(args, check=True, stderr=subprocess.PIPE, universal_newlines=True).stderr
        logging.debug('Output: {}'.format(output))


def run_once(*, corpus, test_list, build_dir, use_valgrind):
    for t in test_list:
        corpus_path = os.path.join(corpus, t)
        os.makedirs(corpus_path, exist_ok=True)
        args = [
            os.path.join(build_dir, 'src', 'test', 'fuzz', t),
            '-runs=1',
            corpus_path,
        ]
        if use_valgrind:
            args = ['valgrind', '--quiet', '--error-exitcode=1'] + args
        logging.debug('Run {} with args {}'.format(t, args))
        result = subprocess.run(args, stderr=subprocess.PIPE, universal_newlines=True)
        output = result.stderr
        logging.debug('Output: {}'.format(output))
        try:
            result.check_returncode()
        except subprocess.CalledProcessError as e:
            if e.stdout:
                logging.info(e.stdout)
            if e.stderr:
                logging.info(e.stderr)
            logging.info("Target \"{}\" failed with exit code {}: {}".format(t, e.returncode, " ".join(args)))
            sys.exit(1)


def parse_test_list(makefile):
    with open(makefile, encoding='utf-8') as makefile_test:
        test_list_all = []
        read_targets = False
        for line in makefile_test.readlines():
            line = line.strip().replace('test/fuzz/', '').replace(' \\', '')
            if read_targets:
                if not line:
                    break
                test_list_all.append(line)
                continue

            if line == 'FUZZ_TARGETS =':
                read_targets = True
    return test_list_all


if __name__ == '__main__':
    main()
