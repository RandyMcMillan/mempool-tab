#!/usr/bin/env python3
# Copyright (c) 2016-2017 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Test version bits warning system.

Generate chains with block versions that appear to be signalling unknown
soft-forks, and test that warning alerts are generated.
"""
import os
import re

from test_framework.blocktools import create_block, create_coinbase
from test_framework.messages import msg_block
from test_framework.mininode import P2PInterface, network_thread_start
from test_framework.test_framework import BitcoinTestFramework

VB_PERIOD = 144           # versionbits period length for regtest
VB_THRESHOLD = 108        # versionbits activation threshold for regtest
VB_TOP_BITS = 0x20000000
VB_UNKNOWN_BIT = 27       # Choose a bit unassigned to any deployment
VB_UNKNOWN_VERSION = VB_TOP_BITS | (1 << VB_UNKNOWN_BIT)

WARN_UNKNOWN_RULES_MINED = "Unknown block versions being mined! It's possible unknown rules are in effect"
WARN_UNKNOWN_RULES_ACTIVE = "unknown new rules activated (versionbit {})".format(VB_UNKNOWN_BIT)
VB_PATTERN = re.compile("^Warning.*versionbit")

class TestNode(P2PInterface):
    def on_inv(self, message):
        pass

class VersionBitsWarningTest(BitcoinTestFramework):
    def set_test_params(self):
        self.setup_clean_chain = True
        self.num_nodes = 1

    def setup_network(self):
        self.alert_filename = os.path.join(self.options.tmpdir, "alert.txt")
        # Open and close to create zero-length file
        with open(self.alert_filename, 'w', encoding='utf8'):
            pass
        self.extra_args = [["-alertnotify=echo %s >> \"" + self.alert_filename + "\""]]
        self.setup_nodes()

    def send_blocks_with_version(self, peer, numblocks, version):
        """Send numblocks blocks to peer with version set"""
        tip = self.nodes[0].getbestblockhash()
        height = self.nodes[0].getblockcount()
        block_time = self.nodes[0].getblockheader(tip)["time"] + 1
        tip = int(tip, 16)

        for _ in range(numblocks):
            block = create_block(tip, create_coinbase(height + 1), block_time)
            block.nVersion = version
            block.solve()
            peer.send_message(msg_block(block))
            block_time += 1
            height += 1
            tip = block.sha256
        peer.sync_with_ping()

    def test_versionbits_in_alert_file(self):
        """Test that the versionbits warning has been written to the alert file.

        Note that this is only called after the node is shutdown, so doesn't need
        a wait_until wrapper."""
        with open(self.alert_filename, 'r', encoding='utf8') as f:
            alert_text = f.read()
        assert(VB_PATTERN.match(alert_text))

    def run_test(self):
        self.nodes[0].add_p2p_connection(TestNode())
        network_thread_start()
        self.nodes[0].p2p.wait_for_verack()

        # Mine one period worth of blocks
        self.nodes[0].generate(VB_PERIOD)

        self.log.info("Check that there is no warning if previous VB_BLOCKS have <VB_THRESHOLD blocks with unknown versionbits version.")
        # Build one period of blocks with < VB_THRESHOLD blocks signaling some unknown bit
        self.send_blocks_with_version(self.nodes[0].p2p, VB_THRESHOLD - 1, VB_UNKNOWN_VERSION)
        self.nodes[0].generate(VB_PERIOD - VB_THRESHOLD + 1)

        # Check that we're not getting any versionbit-related errors in get*info()
        assert(not VB_PATTERN.match(self.nodes[0].getmininginfo()["warnings"]))
        assert(not VB_PATTERN.match(self.nodes[0].getnetworkinfo()["warnings"]))

        # Build one period of blocks with VB_THRESHOLD blocks signaling some unknown bit
        self.send_blocks_with_version(self.nodes[0].p2p, VB_THRESHOLD, VB_UNKNOWN_VERSION)
        self.nodes[0].generate(VB_PERIOD - VB_THRESHOLD)

        self.log.info("Check that there is a warning if <50 blocks in the last 100 were an unknown version")
        # Check that get*info() shows the 51/100 unknown block version error.
        assert(WARN_UNKNOWN_RULES_MINED in self.nodes[0].getmininginfo()["warnings"])
        assert(WARN_UNKNOWN_RULES_MINED in self.nodes[0].getnetworkinfo()["warnings"])

        # Mine a period worth of expected blocks so the generic block-version warning
        # is cleared, and restart the node. This will move the versionbit state
        # to ACTIVE.
        self.nodes[0].generate(VB_PERIOD)
        self.stop_nodes()
        # Empty out the alert file
        with open(self.alert_filename, 'w', encoding='utf8'):
            pass
        self.start_nodes()

        self.log.info("Check that there is a warning if previous VB_BLOCKS have >=VB_THRESHOLD blocks with unknown versionbits version.")
        # Connecting one block should be enough to generate an error.
        self.nodes[0].generate(1)
        assert(WARN_UNKNOWN_RULES_ACTIVE in self.nodes[0].getmininginfo()["warnings"])
        assert(WARN_UNKNOWN_RULES_ACTIVE in self.nodes[0].getnetworkinfo()["warnings"])
        self.stop_nodes()
        self.test_versionbits_in_alert_file()

        # Test framework expects the node to still be running...
        self.start_nodes()

if __name__ == '__main__':
    VersionBitsWarningTest().main()
