#!/usr/bin/env python
# vim: set fileencoding=utf-8
#
# ARVIDA C++ Preprocessor
# Copyright (C) 2015-2019 German Research Center for Artificial Intelligence (DFKI)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import sys
import os
import os.path
import time
import traceback
import argparse

import arvidapp
import arvidapp.generator
import clang.cindex

args = None
source_files = []
invocation_dir = None


def debug(msg):
    global args
    if args.verbose:
        sys.stderr.write(msg + "\n")


def warn(msg):
    sys.stderr.write("%s: Warning: %s\n" % (os.path.basename(sys.argv[0]), msg))


def error(msg):
    sys.stderr.write("%s: Error: %s\n" % (os.path.basename(sys.argv[0]), msg))
    sys.exit(1)


def should_process_file(filename, source_files):
    global args

    def is_system_header():
        return (os.path.isabs(filename.name) and
                os.path.relpath(filename.name, invocation_dir).startswith(".."))

    return (filename and
            (args.all_headers or
             (args.non_system_headers and not is_system_header()) or
             os.path.realpath(filename.name) in source_files))


def main():
    global args
    global source_files
    global invocation_dir

    parser = argparse.ArgumentParser(
        description="Generate code from AST of C++ source code.",
        usage="\n%(prog)s [options] -- <compiler command line>"
              "\n%(prog)s [options] --compile-commands=<compile_commands.json>"
              " <source-file> ...")
    parser.add_argument("-t", "--template", metavar="TEMPLATE",
                        help='select generation template (default: sord)',
                        default='sord')
    parser.add_argument("-f", "-o", "--output", metavar="FILE",
                        help='write dump to %(metavar)s;'
                             ' "-" writes dump to stdout'
                             ' (default: stdout)')
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="enable debugging output")
    parser.add_argument("--version", action="version",
                        version="%(prog)s 0.1")
    parser.add_argument("--all-headers", action="store_true",
                        help="write dump for all header files encountered "
                             "(not just those specified on the command line)")
    parser.add_argument("--non-system-headers", action="store_true",
                        help="write dump for all non-system header files encountered")
    parser.add_argument("--dump", action="store_true",
                        help="dump parsed database")
    parser.add_argument("args", nargs="+", help=argparse.SUPPRESS)

    args = parser.parse_args(sys.argv[1:])
    if not args.output:
        args.output = "-"
    args.source_files = args.args
    source_files = [os.path.realpath(x) for x in args.source_files]
    args.compiler_command_line = args.args

    invocation_dir = os.getcwd()

    tool_dir = os.path.dirname(os.path.realpath(__file__))

    config_filename = os.path.join(tool_dir, 'arvidapp.cfg')

    try:
        start = time.time()
        trans_unit = arvidapp.build_translation_unit(config_filename, args.compiler_command_line)
        debug("  clang parse took %.2fs" % (time.time() - start))
    except Exception as e:
        debug(traceback.format_exc())
        error("Clang failed to parse '%s': %s" % (" ".join(args.compiler_command_line), e))

    errors = [diag_error for diag_error in trans_unit.diagnostics
              if diag_error.severity in (clang.cindex.Diagnostic.Error, clang.cindex.Diagnostic.Fatal)]

    if errors:
        for diag_error in errors:
            sys.stderr.write('%s:%i:%i: error: %s' %
                             (diag_error.location.file, diag_error.location.line, diag_error.location.column, diag_error.spelling))
            sys.stderr.write('\n')
        error("File '%s' failed clang's parsing and type-checking" % trans_unit.spelling)

    environment = arvidapp.Environment.from_cursor(
        trans_unit.cursor,
        cursor_filter=lambda c: should_process_file(c.location.file, source_files))

    template_name = args.template + '.cpp'
    template_dir = os.path.join(tool_dir, 'templates')

    rendered = arvidapp.generator.generate_from_template(environment, template_name, template_dir)

    if args.dump:
        sys.stderr.write(environment.dump() + '\n')

    if args.output == "-":
        out = sys.stdout
    else:
        out = open(args.output, "wb")

    out.write(rendered)
    out.flush()

    if out is not sys.stdout:
        out.close()
    else:
        out.flush()

    return 0


if __name__ == "__main__":
    sys.exit(main())
