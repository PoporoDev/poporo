#!/usr/bin/env python3
# Copyright (c) 2017 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""An example functional test

The module-level docstring should include a high-level description of
what the test is doing. It's the first thing people see when they open
the file and should give the reader information about *what* the test
is testing and *how* it's being tested
"""
import time
import threading
from decimal import Decimal
from queue import Queue

from test_framework.test_framework import BitMoneroTestFramework
from test_framework.messages import COIN
from test_framework.monero_node import Daemon, Wallet
from test_framework.util import assert_equal, assert_raises_rpc_error, wait_until, BidCalculator, set_node_times, \
    sync_blocks, pvk_from_address


def dec_bid_amount_when_grow_old(bids, which_btc_height):
    '''
    模拟bid交易的金额随着块龄变老逐渐递减的情况
    :param bids:
    :param bid_height:
    :return:
    '''
    for bid in bids:
        bid['amount'] = bid['amount'] + (120 - which_btc_height) * COIN * 10


def gcb(node):
    return
    print(node.daemon.sync_info())
    # time.sleep(1)


class BidThread(threading.Thread):
    def __init__(self, node, node1, q, pkv, pkv1, miner_sec_key, miner_sec_key1,info):
        threading.Thread.__init__(self)
        # create a new connection to the node, we can't use the same
        # connection from two threads
        # self.node = get_rpc_proxy(node.url, 1, timeout=600, coveragedir=node.coverage_dir)
        # self.node1 = get_rpc_proxy(node1.url, 1, timeout=600, coveragedir=node1.coverage_dir)
        self.node = Daemon(idx=node.index)
        self.node1 = Daemon(idx=node1.index)
        self.wallet = Wallet(idx=10)
        self.q = q
        self.pkv = pkv
        self.pkv1 = pkv1
        self.miner0_sec_key = miner_sec_key
        self.miner1_sec_key = miner_sec_key1
        self.info = info

    def run(self):
        for i in range(20):
            height = self.node.get_height()['height']
            self.node.bid('100', height, self.pkv)
            time.sleep(0.5)
        print('all bid is done.wait for reach height')
        mock_time = self.q.get()
        for i in range(30, 1, -1):
            print('node1 will generate in {} seconds'.format(i))
            time.sleep(1)
        print('thread wakeup! height is {}'.format(self.node1.get_height()['height']))
        # set_node_times([self.node,self.node1],mock_time)
        self.node.setmocktime(mock_time)
        self.node1.setmocktime(mock_time)
        self.info('thead mocktime:{}'.format(mock_time))
        for wallet_id in range(10,20):
            w = Wallet(idx=wallet_id)
            addr = w.get_address()['address']
            prikey = w.query_key('view_key').key
            print('addr:',addr,'prikey:',prikey)
            try:
                print(self.node1.generateblocks(addr, miner_sec_key=prikey))
                break
            except Exception as e:
                print('error:{}'.format(e))
                continue

        for i in range(50, 1, -1):
            print('block will be create in {} seconds'.format(i))
            time.sleep(1)
        # set_node_times([self.node, self.node1], mock_time + 1000)
        time.sleep(5)
        print('thread generate done')


class PopMiningleTest(BitMoneroTestFramework):

    def set_test_params(self):
        super(PopMiningleTest, self).set_test_params()
        self.setup_clean_chain = False
        self.ltcbidstart = 280
        self.calc_bid = BidCalculator(1000, 203)
        self.extra_args = [["-deprecatedrpc=generate"], ["-deprecatedrpc=generate"]]
        self.num_wallets = [10, 10]
        self.xmr_rpctimeout = 60 * 10
        self.monero_extra_args = [
            ['--popforkheight', '1000', '--btcbidstart', '203', '--out-peers', '1024',
             '--block-sync-size', '1', '--db-sync-mode', 'safe:sync', '--reorg-notify',
             '/usr/bin/python3 /home/weigun/reorg.py %s %h %d %n'],
            ['--popforkheight', '1000', '--btcbidstart', '203', '--out-peers', '1024',
             '--block-sync-size', '1', '--db-sync-mode', 'safe:sync', '--reorg-notify',
             '/usr/bin/python3 /home/weigun/reorg.py %s %h %d %n']]

    def add_options(self, parser):
        super(PopMiningleTest, self).add_options(parser)
        parser.add_argument("--startbidnum", dest="start_bid_num", default=100, help="set start bid num")

    def run_test(self):
        # self.xnode1 = self.xnode0
        # self.xmrnodes[1] = self.xnode0
        for n in self.xmrnodes:
            print(n.getblockcount())
        self.prepare()
        keys = self.xnode0.wallet.query_key('view_key')

        balance = self.node0.getbalance()
        xmr_balance = self.xnode0.wallet.get_balance()
        print(balance, xmr_balance)
        for n in (self.nodes + self.xmrnodes):
            print(n.getblockcount(), n.getblockhash(1), n.getblockhash(2))

        self.test_for_amount()
        # return
        self.test_for_blockheight()
        for i in range(200,204):
            print('>>>>>>>>>>>>>>{}:'.format(i),
                  self.node0.getbid(i, 'myV5V3oQWJgzzxwp5suwSJM7HgU1zfsmRj', 0))
        self.log.info('before cur xmr height:{},{}'.format(self.xnode0.getblockcount(), self.xnode1.getblockcount()))
        self.combi_generate(800 - self.xnode0.getblockcount())  # 挖到popforkheight
        self.log.info('cur xmr height:{},{}'.format(self.xnode0.getblockcount(), self.xnode1.getblockcount()))
        self.log.info('cur xmr besthash:{},{}'.format(self.xnode0.getbestblockhash(), self.xnode1.getbestblockhash()))
        # time.sleep(120)
        need_blocks = 1000 - self.xnode0.getblockcount()
        self.combi_generate(need_blocks, 1, 1, callback=lambda: gcb(self.xnode0))  # 挖到popforkheight
        # return
        self.log.info('cur xmr height:{},{}'.format(self.xnode0.getblockcount(), self.xnode1.getblockcount()))
        self.log.info('cur xmr besthash:{},{}'.format(self.xnode0.getbestblockhash(), self.xnode1.getbestblockhash()))
        self.test_block_will_generate_by_max_bid()
        self.test_max_bid_growing_old_can_still_mining()

        self.log.info('start test transfer')
        # self.test_transfer()

        self.test_break_generate_when_recv_new_block()
        self.log.info('start test fork without btc fork')
        self.test_fork()
        self.log.info('start test fork with btc fork')
        self.test_fork(True)
        self.log.info('start test transfer')
        self.test_transfer()
        self.test_generate_unit_1w()

    def prepare(self):
        '''
        挖到预定的高度
        :return:
        '''
        blocks = self.ltcbidstart - self.xnode0.getblockcount()
        self.log.info('xmr prepare {} blocks'.format(blocks))
        self.miner0 = self.xnode0.getnewaddress()
        self.miner1 = self.xnode1.getnewaddress()
        print('pkv:', pvk_from_address(self.miner0), self.miner0)
        print('pkv1:', pvk_from_address(self.miner1), self.miner1)

        # 先每个钱包挖有一个块
        # for n in self.xmrnodes:
        #     for i in range(10):
        #         assert 'error' not in n.generate(1,wallet_index=i)
        blocks = self.ltcbidstart - self.xnode0.getblockcount()
        self.xnode0.generate(blocks - 1, self.miner0)
        self.xnode0.wallet.refresh()
        # 将xmr平分给20个钱包
        reward = int(self.xnode0.getbalance() / 100)
        assert reward > 0
        print('hard_fork_info:', self.xnode0.daemon.hard_fork_info())
        self.log.info('before send,total balance:{}'.format(self.xnode0.getbalance()))
        for i in range(1, 20):
            if i < 10:
                addr = self.xnode0.getnewaddress(i)
            else:
                addr = self.xnode1.getnewaddress(i - 10)
            dst = {
                'address': addr,
                'amount': 10000, }
            self.log.info('send {} to wallet{},addr {}'.format(reward, i, addr))
            self.log.info('remain balance:{}'.format(self.xnode0.getbalance()))
            result = self.xnode0.wallet0.transfer([dst])
            print(result)
        self.sync_all([self.xmrnodes])
        # print(self.xnode1.wallet9.get_transfer_by_txid(result.tx_hash))
        self.xnode1.generate(1)
        self.sync_all([self.xmrnodes])
        # print(self.xnode1.wallet9.get_transfer_by_txid(result.tx_hash))

        # must be refresh tx so the balance can be update
        # check balance
        for node_index in range(2):
            n = self.xmrnodes[node_index]
            # print('hard_fork_info:',n.daemon.hard_fork_info())
            for wallet_index in range(10):
                wallet = getattr(n, 'wallet{}'.format(wallet_index))
                refresh_ret = wallet.refresh()
                self.log.info('wallet{} check balance...'.format(wallet_index))

                def must_has_balance():
                    return n.getbalance(wallet_index=wallet_index) > 0

                wait_until(must_has_balance, timeout=30)
        for n in self.nodes:
            self.sync_all()
            n.generate(1)
        print(self.xnode0.getblockcount())

    def test_for_amount(self):
        node = self.xnode0
        bnode = self.node0
        height = node.getblockcount()
        pkv = pvk_from_address(self.miner0)
        pkv1 = pvk_from_address(self.miner1)
        node.daemon.bid('0', height, pkv).assert_message('Invalid amount for send')
        node.daemon.bid('-1', height, pkv).assert_message('Amount out of range')
        node.daemon.bid(1, height, pkv).assert_message('json not found')
        node.daemon.bid(str(1e512), height, pkv).assert_message('Parse error')
        node.daemon.bid('0.00099999', height, pkv).assert_message('Transaction amount too small')
        node.daemon.bid(str(1e100), height, pkv).assert_message('Invalid amount')
        bid_num = 100 if self.options.start_bid_num == 100 else 4
        self.log.info('start bid num:{}'.format(bid_num))
        for i in range(bid_num - 1):
            if bid_num == 4:
                if i < 2:
                    ret = self.xnode1.daemon.bid(str(20 - i), height, pkv1)
                else:
                    ret = self.xnode0.daemon.bid('5', height, pkv)
            else:
                if i < 20:
                    if i < 10:
                        addr = self.xnode0.getnewaddress(wallet_index=i)
                        tmp_pkv = pvk_from_address(addr)
                        # print(i, addr, tmp_pkv)
                        if i == 8:
                            ret = self.xnode0.daemon.bid(str(16.5), height, tmp_pkv)
                        elif i == 9:
                            ret = self.xnode0.daemon.bid(str(15.5), height, tmp_pkv)
                        else:
                            ret = self.xnode0.daemon.bid(str(20 - i), height, tmp_pkv)
                    else:
                        addr = self.xnode1.getnewaddress(wallet_index=i - 10)
                        tmp_pkv = pvk_from_address(addr)
                        if i == 11:
                            ret = self.xnode1.daemon.bid(str(17.5), height, tmp_pkv)
                        elif i == 12:
                            ret = self.xnode1.daemon.bid(str(18.5), height, tmp_pkv)
                        else:
                            ret = self.xnode1.daemon.bid(str(20 - i), height, tmp_pkv)
                else:
                    print(i, self.miner0, pkv)
                    ret = self.xnode0.daemon.bid('5', height, pkv)
                print(i, addr, tmp_pkv)
            assert ret.data.result is not None
        assert self.xnode1.daemon.bid('1000', height, pkv1).data.result is not None

        self.sync_all()
        # make sure two transactions are in mempool and can be packaged to block
        assert_equal(len(self.node0.getrawmempool()), len(self.node1.getrawmempool()))
        self.node0.generate(1)
        self.sync_all()
        btc_bid_height = self.node0.getblockcount()
        self.log.info('xmr height {},bid at btc {} succ'.format(self.xnode0.getblockcount(), btc_bid_height))
        bids = self.node1.getbid(btc_bid_height, 'myV5V3oQWJgzzxwp5suwSJM7HgU1zfsmRj', 0)
        assert_equal(len(bids['bids']), bid_num)
        self.sync_all()
        assert_equal(len(self.node0.getrawmempool()), 0)
        assert_equal(len(self.node1.getrawmempool()), 0)
        assert_equal(self.node0.getblockcount(), self.node1.getblockcount())

        # check balance
        self.log.info('check balance...')
        for n in self.xmrnodes:
            for i in range(10):
                print(n.getbalance(wallet_index=i))

    def test_for_blockheight(self):
        # blockheight nosence
        node = self.xnode0
        bnode = self.node0
        pkv = pvk_from_address(self.miner0)
        pkv1 = pvk_from_address(self.miner1)
        print(node.daemon.bid('1', -1, pkv))
        print(node.daemon.bid('1', 0, pkv))
        node.daemon.bid('1', '100.236', pkv).assert_message('json not found')
        node.daemon.bid('1', 'abc', pkv).assert_message('json not found')
        node.daemon.bid('1', str(1000000000000000000000000000000000000000), pkv).assert_message('json not found')

    def test_generate_unit_1w(self):
        self.combi_generate(100)  # 应该可以一直挖的

    def test_block_will_generate_by_max_bid(self):
        node0_total_balance = self.xnode0.getbalance()
        node1_total_balance = self.xnode1.getbalance()
        self.generate(1, 1)
        try:
            self.generate(1, 1)
        except AssertionError:
            self.log.info('node1 generate should failed,because of can not repeat mining in same address')
        self.sync_all([self.xmrnodes])

        # node0 should mining over 2min because bid is not the max
        # ming 101 blocks make 1002 can spend
        print(self.node0.getblockcount())
        # self.generate(0, 1)
        self.generate2(0, 1)
        pkv = pvk_from_address(self.miner0)
        pkv1 = pvk_from_address(self.miner1)

        # 将xmr平分给20个钱包
        print('hard_fork_info:', self.xnode0.daemon.hard_fork_info())
        self.log.info('before send,total balance:{}'.format(self.xnode0.getbalance()))
        for i in range(1, 20):
            if i < 10:
                addr = self.xnode0.getnewaddress(i)
            else:
                addr = self.xnode1.getnewaddress(i - 10)
            dst = {
                'address': addr,
                'amount': 100, }
            self.log.info('remain balance:{}'.format(self.xnode0.getbalance()))
            print(self.xnode0.wallet0.transfer([dst]))

        def callback():
            once = False

            def warp():
                nonlocal once
                if not once:
                    print('------------', self.calc_bid(self.xnode0.getblockcount()), self.node0.getblockcount())
                    if self.node0.getblockcount() == 347:#347:318
                        print('once')
                        self.xnode0.daemon.bid('5', self.xnode0.getblockcount(), pkv)
                        self.sync_all([self.xmrnodes])
                        self.sync_all()
                        self.generate(0, 1, bitchain=True)
                        self.sync_all()
                        once = True

            return warp

        self.combi_generate(100, 1, callback=callback())
        # print('diff:', self.xnode0.getbalance() - node0_total_balance)
        # assert self.xnode0.getbalance() > node0_total_balance

    def test_max_bid_growing_old_can_still_mining(self):
        ltc_height = self.xnode0.getblockcount()
        btc_height = self.node0.getblockcount()
        should_get_bid_height = self.calc_bid(ltc_height)
        print(ltc_height, btc_height, should_get_bid_height)
        pkv = pvk_from_address(self.miner0)
        pkv1 = pvk_from_address(self.miner1)
        # 当前块先埋19个bid
        for i in range(19):
            i = i - 10 if i > 9 else i
            addr = self.xnode1.getnewaddress(wallet_index=i)
            tmp_pkv = pvk_from_address(addr)
            self.xnode1.daemon.bid(str(max(5 - i, 0.1)), ltc_height, tmp_pkv)
        self.sync_all([self.xmrnodes])
        self.sync_all()
        self.generate(0, 10, bitchain=True)  # avoid btc blocks not enough,then header not accept
        self.sync_all()
        assert_equal(len(self.node1.getrawmempool()), 0)
        bid_data_height = btc_height + 1
        bids = self.get_bid_info(bid_data_height)
        assert_equal(len(bids), 19)

        # 埋好后，需要将ltc的高度提上来，直到self.calc_bid(ltc_height) == bid_data_height
        # 这里必须-3，因为往前搜索块的时候，如果有找到，就最多往前搜120个块的限制，超出就不找了，所以会出现不满20的情况
        blocks = 1600 - self.xnode0.getblockcount() - 1
        print('need to generate {} blocks to 1600'.format(blocks))
        self.combi_generate(blocks, node_index=1)  #1599挖不了
        blocks = (bid_data_height - self.calc_bid(self.xnode0.getblockcount())) * 5 - 5
        print('need to generate {} blocks to reach bid height {}'.format(blocks, bid_data_height))
        self.combi_generate(blocks,node_index=0)

        bid_319 = self.get_bid_info(348)  #348  319
        print(bid_319)
        self.log.info('319 or 348 bid info:{}'.format(bid_319))
        # amount做递减处理
        dec_bid_amount_when_grow_old(bids, self.calc_bid(self.xnode0.getblockcount() + 1))
        dec_bid_amount_when_grow_old(bid_319, 348) #348 319
        print(bid_319)
        # 先合并要找到的bids
        bids.extend(bid_319)
        assert_equal(len(bids), 20)
        sort_bids = sorted(bids, key=lambda x: x['amount'], reverse=True)
        self.log.info('bids after sorted')
        for i in sort_bids:
            print('>> ',i)
        # 这里只能是node1来挖，因为上一个块的出块者是node0的某个地址（bid最大），到这里递减后，依然是最大，但有一个规则
        # 就是同一个地址不能连续出块
        while self.calc_bid(self.xnode0.getblockcount() + 1) < 340:
            self.log.info('not enought 340,xmr generate.xnode0 height {}'.format(self.xnode0.getblockcount() ))
            self.generate(0,1)
        self.generate2(1, 1)
        self.generate2(1, 1)  # 这里可以连续出块，因为node1有多笔交易
        self.generate(0, 1)  # 这里可以node0可以出块了
        print(self.xnode0.getblockcount(), self.node0.getblockcount(), self.calc_bid(self.xnode0.getblockcount()))

    def test_break_generate_when_recv_new_block(self):
        '''
        没有充值交易，挖矿会一直重试，直到收到其他节点同步过来的新块；然后该节点可以出下一个新块
        :return:
        '''
        ltc_height = self.xnode0.getblockcount()
        btc_height = self.node0.getblockcount()
        should_get_bid_height = self.calc_bid(ltc_height)
        print(ltc_height, btc_height, should_get_bid_height)
        pkv = pvk_from_address(self.miner0)
        pkv1 = pvk_from_address(self.miner1)
        # node0开始充值
        queue = Queue()
        privk = self.xnode0.wallet.query_key('view_key').key
        privk1 = self.xnode1.wallet.query_key('view_key').key
        thr = BidThread(self.node0, self.node1, queue, pkv, pkv1, privk, privk1,self.log.info)
        thr.start()

        thr.join(10)  # 等待一些充值交易
        self.generate(0, 1, bitchain=True)
        # self.sync_all([self.bitnodes])
        sync_blocks([self.node0, self.node1])
        bid_data_height = btc_height + 1
        bids = self.get_bid_info(bid_data_height)
        self.log.info('bid number:{}'.format(len(bids)))  #should be 1?

        # avoid btc blocks not enough,then header not accept
        self.generate(0, 2, bitchain=True)
        self.sync_all()

        # 埋好后，需要将ltc的高度提上来，直到self.calc_bid(ltc_height) == bid_data_height
        # 这里必须-3，因为往前搜索块的时候，如果有找到，就最多往前搜120个块的限制，超出就不找了，所以会出现不满20的情况
        self.log.info('{},{},{},{}'.format(self.xnode0.getblockcount(), self.xnode1.getblockcount(),self.node0.getblockcount(), self.calc_bid(self.xnode0.getblockcount())))
        blocks = (bid_data_height - self.calc_bid(self.xnode0.getblockcount())) * 5 - 4  # -1是为了模拟一直挖不出来的情况
        print('need to generate {} blocks to reach bid height {}'.format(blocks, bid_data_height))
        self.combi_generate(blocks, 1)
        print(self.xnode0.getblockcount(), self.node0.getblockcount(), self.calc_bid(self.xnode0.getblockcount()))
        self.log.info('cur mocktime:{}'.format(self.mocktime))
        queue.put(self.get_mocktime())  # 通知线程继续挖矿
        self.log.info('wait for generate.....')

        # self.generate(0, 1)  #这里应该等一段时间才会挖出来
        # self.generate(1, 1)  # 应该用0挖的，但是这里只有2个抵押的交易，上次是用0来出块，这里只能用1了
        def gen():
            try:
                self.generate(0, 1)
                return True
            except AssertionError:
                # self.get_mocktime(offset=-150)
                return False

        wait_until(lambda: gen(), timeout=120)
        # self.generate(0, 1)  # 应该用0挖的，但是这里只有2个抵押的交易，上次是用0来出块，这里只能用1了
        self.log.info('SUCCESS')
        thr.join()
        # self.node_time += 1500
        print(self.xnode0.getblockcount(), self.node0.getblockcount(), self.calc_bid(self.xnode0.getblockcount()))

    def test_fork(self, fork_btc=False):
        '''
        测试分叉情况：
        1.只有LTC分叉
        2.都分叉
        3.无视BTC单独分叉的情况
        :param fork_ltc:
        :param fork_btc:
        :return:
        '''
        ltc_height = self.xnode0.getblockcount()
        btc_height = self.node0.getblockcount()
        should_get_bid_height = self.calc_bid(ltc_height)
        pkv = pvk_from_address(self.miner0)
        pkv1 = pvk_from_address(self.miner1)
        print(ltc_height, btc_height, should_get_bid_height)

        # 当前块先埋20个bid
        # for i in range(20):
        #     if i % 2 == 0:
        #         self.xnode0.daemon.bid('1', ltc_height, pkv)
        #     else:
        #         self.xnode1.daemon.bid('1', ltc_height, pkv1)

        for i in range(20):
            if i % 2 == 0:
                i = i - 10 if i > 9 else i
                addr = self.xnode0.getnewaddress(wallet_index=i)
                tmp_pkv = pvk_from_address(addr)
                if i == 0:
                    self.xnode0.daemon.bid('10', ltc_height, tmp_pkv)
                elif i == 1:
                    self.xnode0.daemon.bid('7', ltc_height, tmp_pkv)
                else:
                    self.xnode0.daemon.bid('1', ltc_height, tmp_pkv)
            else:
                i = i - 10 if i > 9 else i
                addr = self.xnode1.getnewaddress(wallet_index=i)
                tmp_pkv = pvk_from_address(addr)
                if i == 0:
                    self.xnode1.daemon.bid('9', ltc_height, tmp_pkv)
                elif i == 1:
                    self.xnode1.daemon.bid('6', ltc_height, tmp_pkv)
                else:
                    self.xnode1.daemon.bid('1', ltc_height, tmp_pkv)

        self.sync_all([self.xmrnodes])
        self.sync_all()
        self.generate(0, 1, bitchain=True)
        self.sync_all()
        assert_equal(len(self.node1.getrawmempool()), 0)
        bid_data_height = btc_height + 1
        bids = self.get_bid_info(bid_data_height)
        assert_equal(len(bids), 20)

        # avoid btc blocks not enough,then header not accept
        self.generate(0, 10, bitchain=True)
        self.sync_all()

        # 埋好后，需要将ltc的高度提上来，直到self.calc_bid(ltc_height) == bid_data_height
        # 这里必须-3，因为往前搜索块的时候，如果有找到，就最多往前搜120个块的限制，超出就不找了，所以会出现不满20的情况
        blocks = (bid_data_height - self.calc_bid(self.xnode0.getblockcount())) * 5 - 1
        print('need to generate {} blocks to reach bid height {}'.format(blocks, bid_data_height))
        # def cb():
        #     print('cur ltc height {},btc height {}'.format(self.node0.getblockcount(),self.bnode0.getblockcount()))
        self.combi_generate(blocks, [0,1], callback=lambda: gcb(self.xnode0))
        print(self.xnode0.getblockcount(), self.node0.getblockcount(), self.calc_bid(self.xnode0.getblockcount()))

        # 这里随便一个挖都可以
        self.generate2(1, 1)
        self.sync_all([self.xmrnodes])
        self.sync_all()
        print(self.xnode0.getblockcount(), self.xnode1.getblockcount(),self.node0.getblockcount(), self.node1.getblockcount(),
              self.calc_bid(self.xnode0.getblockcount()))
        start_split_height = self.xnode0.getblockcount()
        start_split_btcheight = self.node0.getblockcount()

        # 分割网络,各自挖矿
        self.log.info('split network...')
        self.split_network()
        if fork_btc:
            self.split_network(bitchain=True)
        self.combi_generate(50, 0, split=True)
        self.combi_generate(60, 1, 1, split=True)

        assert_equal(self.xnode0.getblockcount(), start_split_height + 50)
        assert_equal(self.xnode1.getblockcount(), start_split_height + 60)
        node0_besthash = self.xnode0.getbestblockhash()
        node1_besthash = self.xnode1.getbestblockhash()
        if fork_btc:
            for n in self.nodes:
                print(n.getpeerinfo(), n.getbestblockhash())
            assert_equal(self.node0.getblockcount(), start_split_btcheight + int(50 / 5))
            assert_equal(self.node1.getblockcount(), start_split_btcheight + int(60 / 5))
            bnode0_besthash = self.node0.getbestblockhash()
            bnode1_besthash = self.node1.getbestblockhash()

        # 合并网络
        self.log.info('join network...')
        self.join_network(timeout=self.xmr_rpctimeout)
        if fork_btc:
            self.join_network(bitchain=True)
        for n in self.xmrnodes:
            assert_equal(n.getblockcount(), start_split_height + 60)
            assert_equal(n.getbestblockhash(), node1_besthash)
        if fork_btc:
            for n in self.nodes:
                assert_equal(n.getblockcount(), start_split_btcheight + 60 / 5)
                assert_equal(n.getbestblockhash(), bnode1_besthash)

        self.combi_generate(20, 1, callback=lambda: gcb(self.xnode0))

        for n in (self.xmrnodes + self.nodes):
            print(n.getpeerinfo())
            print(n.getbestblockhash())

    def get_bid_info(self, btc_height):
        return self.node0.getbid(btc_height, 'myV5V3oQWJgzzxwp5suwSJM7HgU1zfsmRj', 0)['bids']

    def test_transfer(self):
        for _ in range(50):
            for i in range(1, 20):
                if i < 10:
                    addr = self.xnode0.getnewaddress(i)
                else:
                    addr = self.xnode1.getnewaddress(i - 10)
                dst = {
                    'address': addr,
                    'amount': 1000, }
                print(self.xnode0.wallet0.transfer([dst]))
            self.combi_generate(4, 1)


if __name__ == '__main__':
    PopMiningleTest().main()
