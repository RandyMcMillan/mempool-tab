#!/usr/bin/env python2
# Copyright (c) 2016 The Bitcoin Core developers
# Distributed under the MIT/X11 software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
#

from test_framework.mininode import *
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import *
import time

'''
FeeFilterTest -- test processing of feefilter messages
'''

def hashToHex(hash):
    return format(hash, '064x')

# Wait up to 60 secs to see if the testnode has received all the expected invs
def allInvsMatch(invsExpected, testnode):
    for x in xrange(60):
        with mininode_lock:
            if (sorted(invsExpected) == sorted(testnode.txinvs)):
                return True;
        time.sleep(1)
    return False;

# TestNode: bare-bones "peer".  Used to track which invs are received from a node
# and to send the node feefilter messages.
class TestNode(SingleNodeConnCB):
    def __init__(self):
        SingleNodeConnCB.__init__(self)
        self.txinvs = []

    def on_inv(self, conn, message):
        for i in message.inv:
            if (i.type == 1):
                self.txinvs.append(hashToHex(i.hash))

    def clear_invs(self):
        with mininode_lock:
            self.txinvs = []

    def send_filter(self, feerate):
        self.send_message(msg_feefilter(feerate))
        self.sync_with_ping()

class FeeFilterTest(BitcoinTestFramework):
    def setup_network(self):
        # Node1 will be used to generate txs which should be relayed from Node0
        # to our test node
        self.nodes = []
        self.nodes.append(start_node(0, self.options.tmpdir, ["-debug", "-logtimemicros"]))
        self.nodes.append(start_node(1, self.options.tmpdir, ["-debug", "-logtimemicros"]))
        connect_nodes(self.nodes[0], 1)

    def run_test(self):
        node1 = self.nodes[1]
        # Get out of IBD
        node1.generate(1)
        sync_blocks(self.nodes)

        # Setup the p2p connections and start up the network thread.
        test_node = TestNode()
        connection = NodeConn('127.0.0.1', p2p_port(0), self.nodes[0], test_node)
        test_node.add_connection(connection)
        NetworkThread().start()
        test_node.wait_for_verack()

        # Test that invs are received for all txs at feerate of 20 sat/byte
        node1.settxfee(Decimal("0.00020000"))
        txids = [node1.sendtoaddress(node1.getnewaddress(), 1) for x in xrange(3)]
        assert(allInvsMatch(txids, test_node))
        test_node.clear_invs()

        # Set a filter of 15 sat/byte
        test_node.send_filter(15000)

        # Test that txs are still being received (paying 20 sat/byte)
        txids = [node1.sendtoaddress(node1.getnewaddress(), 1) for x in xrange(3)]
        assert(allInvsMatch(txids, test_node))
        test_node.clear_invs()

        # Change tx fee rate to 10 sat/byte and test they are no longer received
        node1.settxfee(Decimal("0.00010000"))
        [node1.sendtoaddress(node1.getnewaddress(), 1) for x in xrange(3)]
        sync_mempools(self.nodes) # must be sure node 0 has received all txs 
        time.sleep(10) # wait 10 secs to be sure its doesn't relay any
        assert(allInvsMatch([], test_node))
        test_node.clear_invs()

        # Remove fee filter and check that txs are received again
        test_node.send_filter(0)
        txids = [node1.sendtoaddress(node1.getnewaddress(), 1) for x in xrange(3)]
        assert(allInvsMatch(txids, test_node))
        test_node.clear_invs()

if __name__ == '__main__':
    FeeFilterTest().main()
