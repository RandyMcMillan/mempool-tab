#!/usr/bin/env python3
# Copyright (c) 2020 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
'''
Test script for symbol-check.py
'''
import subprocess
import unittest

def call_symbol_check(cc, source, executable, options):
    subprocess.run([cc,source,'-o',executable] + options, check=True)
    p = subprocess.run(['./contrib/devtools/symbol-check.py',executable], stdout=subprocess.PIPE, universal_newlines=True)
    return (p.returncode, p.stdout.rstrip())

def get_machine(cc):
    p = subprocess.run([cc,'-dumpmachine'], stdout=subprocess.PIPE, universal_newlines=True)
    return p.stdout.rstrip()

class TestSymbolChecks(unittest.TestCase):
    def test_ELF(self):
        source = 'test1.c'
        executable = 'test1'
        cc = 'gcc'

        # there's no way to do this test for RISC-V at the moment; bionic's libc is 2.27
        # and we allow all symbols from 2.27.
        if 'riscv' in get_machine(cc):
            self.skipTest("test not available for RISC-V")

        # memfd_create was introduced in GLIBC 2.27, so is newer than the upper limit of
        # all but RISC-V but still available on bionic
        with open(source, 'w', encoding="utf8") as f:
            f.write('''
                #define _GNU_SOURCE
                #include <sys/mman.h>

                int memfd_create(const char *name, unsigned int flags);

                int main()
                {
                    memfd_create("test", 0);
                    return 0;
                }
        ''')

        self.assertEqual(call_symbol_check(cc, source, executable, []),
                (1, executable + ': symbol memfd_create from unsupported version GLIBC_2.27\n' +
                    executable + ': failed IMPORTED_SYMBOLS'))

        # -lutil is part of the libc6 package so a safe bet that it's installed
        # it's also out of context enough that it's unlikely to ever become a real dependency
        source = 'test2.c'
        executable = 'test2'
        with open(source, 'w', encoding="utf8") as f:
            f.write('''
                #include <utmp.h>

                int main()
                {
                    login(0);
                    return 0;
                }
        ''')

        self.assertEqual(call_symbol_check(cc, source, executable, ['-lutil']),
                (1, executable + ': NEEDED library libutil.so.1 is not allowed\n' +
                    executable + ': failed LIBRARY_DEPENDENCIES'))

        # finally, check a conforming file that simply uses a math function
        source = 'test3.c'
        executable = 'test3'
        with open(source, 'w', encoding="utf8") as f:
            f.write('''
                #include <math.h>

                int main()
                {
                    return (int)pow(2.0, 4.0);
                }
        ''')

        self.assertEqual(call_symbol_check(cc, source, executable, ['-lm']),
                (0, ''))

if __name__ == '__main__':
    unittest.main()

