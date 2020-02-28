#!/usr/bin/env python3

# Copyright (c) 2019 The Monero Project
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are
# permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of
#    conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list
#    of conditions and the following disclaimer in the documentation and/or other
#    materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors may be
#    used to endorse or promote products derived from this software without specific
#    prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL
# THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF
# THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""Class for monero daemon and wallet node under test"""

import requests
import json
import os
import sys
import logging
import subprocess
import tempfile
import time
import socket
import shlex

from random import choice

from test_framework.util import get_local_ip

requests.adapters.DEFAULT_RETRIES = 5


class MoneroNode(object):
    '''
    该类只是做简单的monero进程管理与钱包RPC的维护
    '''

    def __init__(self, i, datadir, monerod, wall_rpc_bin, wallet_dir, num_wallet, btc_peer={}, exclusive_nodes=[],
                 extra_args=None,rpctimeout = 60):
        # --add-exclusive-node
        self.index = i
        self.datadir = datadir
        self.btc_peer = btc_peer
        self.exclusive_nodes = exclusive_nodes
        self.num_wallet = num_wallet
        self.monerod = monerod
        self.rpc_bin = wall_rpc_bin
        self.wallet_dir = wallet_dir
        self.stdout_dir = os.path.join(self.datadir, "stdout")
        self.stderr_dir = os.path.join(self.datadir, "stderr")
        self.is_daemon = True
        self.extra_args = extra_args
        self.rpctimeout = rpctimeout
        argv = ''
        if not exclusive_nodes:
            if i == 0:
                # exclusive_nodes = ['127.0.0.1:18281']
                exclusive_nodes = ['{}:18281'.format(get_local_ip())]
            else:
                # exclusive_nodes = ['127.0.0.1:18280']
                exclusive_nodes = ['{}:18280'.format(get_local_ip())]
        for n in exclusive_nodes:
            argv = argv + '--add-exclusive-node ' + n + ' '
        self.monero_args = [
            self.monerod,
            "--data-dir",
            self.datadir,
            "--btc-rpc-ip",
            btc_peer['ip'],
            "--btc-rpc-port",
            btc_peer['port'],
            "--btc-rpc-login",
            btc_peer['login'],
            "--regtest",
            "--fixed-difficulty",
            "1",
            # "--offline",
            "--no-igd",
            "--p2p-bind-ip",
            get_local_ip(),
            "--p2p-bind-port",
            str(18280 + i),
            "--rpc-bind-ip",
            get_local_ip(),
            "--rpc-bind-port",
            str(18180 + i),
            "--confirm-external-bind",
            "--zmq-rpc-bind-ip",
            get_local_ip(),
            "--zmq-rpc-bind-port",
            str(18380 + i),
            "--non-interactive",
            "--disable-dns-checkpoints",
            "--check-updates",
            "disabled",
            "--rpc-ssl",
            "disabled",
            "--log-level",
            "1",
            "--add-peer",
            "{}:".format(get_local_ip())+ str(18281) if i == 0 else str(18280),
            # "--allow-local-ip"
        ]
        self.monero_args.extend(shlex.split(argv))
        if extra_args:
            self.monero_args.extend(extra_args)

        self.rpc_list = []
        daemon_port = str(18180 + i)
        for j in range(num_wallet):
            if i > 0:
                j = 10+j
            args = [
                self.rpc_bin,
                "--wallet-dir",
                wallet_dir,
                "--rpc-bind-ip",
                get_local_ip(),
                "--rpc-bind-port",
                str(18090 + j),
                "--confirm-external-bind",
                "--disable-rpc-login",
                "--rpc-ssl",
                "disabled",
                "--daemon-ssl",
                "disabled",
                "--daemon-host",
                get_local_ip(),
                "--daemon-port",
                daemon_port,
                "--log-level",
                "1",
                "--log-file",
                os.path.join(wallet_dir, 'wallet{}.log'.format(j))
            ]
            self.rpc_list.append(args)
        self.rpc_process_list = []
        self.wallets = []
        self.monerod_process = None
        self.log = logging.getLogger('TestFramework.node%d' % i)
        self.ports = [18180 + i]
        for j in range(num_wallet):
            if i > 0:
                j += 10
            self.ports.append(18090 + j)

    def start(self, reboot=False):
        '''

        :return:
        '''
        # Add a new stdout and stderr file each time bitcoind is started
        if not os.path.exists(self.stderr_dir):
            os.makedirs(self.stderr_dir)
        if not os.path.exists(self.stdout_dir):
            os.makedirs(self.stdout_dir)
        stderr = tempfile.NamedTemporaryFile(dir=self.stderr_dir, delete=False, prefix='daemon_')
        stdout = tempfile.NamedTemporaryFile(dir=self.stdout_dir, delete=False, prefix='daemon_')
        # print(self.monero_args)
        self.monerod_process = subprocess.Popen(self.monero_args, stdout=stdout, stderr=stderr)
        stderr = tempfile.NamedTemporaryFile(dir=self.stderr_dir, delete=False, prefix='wallet_')
        stdout = tempfile.NamedTemporaryFile(dir=self.stdout_dir, delete=False, prefix='wallet_')
        # self.log.info('cmd:' + ' '.join(self.rpc_args))
        if reboot:
            pass
            # # 如果是重启服务，需要打开之前创建的钱包
            # reboot_args = self.rpc_args
            # for i,argv in enumerate(reboot_args):
            #     if argv == '--wallet-dir':
            #         # replace it
            #         reboot_args[i] = '--wallet-file'
            #         reboot_args[i + 1] = os.path.join(self.wallet_dir,'wallet{}.dat'.format(self.index))
            #         break
            # self.rpc_process = subprocess.Popen(reboot_args, stdout=stdout, stderr=stderr)
        else:
            for i,rpc_args in enumerate(self.rpc_list):
                stderr = tempfile.NamedTemporaryFile(dir=self.stderr_dir, delete=False, prefix='wallet{}_'.format(i))
                stdout = tempfile.NamedTemporaryFile(dir=self.stdout_dir, delete=False, prefix='wallet{}_'.format(i))
                self.rpc_process_list.append(subprocess.Popen(rpc_args, stdout=stdout, stderr=stderr))

        # check start is ok
        for i in range(10):
            time.sleep(1)
            all_open = True
            for port in self.ports:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1)
                if s.connect_ex((get_local_ip(), port)) != 0:
                    all_open = False
                    break
                s.close()
            if all_open:
                self.log.info('monerod and walletRPC is ready')
                break

        if not all_open:
            self.log.info('Failed to start wallet or daemon')
            self.stop()
            raise Exception("monero nodes not start")

        self.daemon = Daemon(port=self.ports[0],rpctimeout=self.rpctimeout)
        for i,p in enumerate(self.ports[1:]):
            wallet = Wallet(port=p,rpctimeout=self.rpctimeout)
            self.wallets.append(wallet)
            setattr(self,'wallet{}'.format(i),wallet)
            # 创建本地钱包
            if not os.path.exists(os.path.join(self.wallet_dir, 'wallet{}.dat'.format(i))):
                self.log.info(
                    'create wallet:{}'.format(os.path.join(self.wallet_dir, 'wallet{}.dat'.format(i))))
                wallet.create_wallet('wallet{}.dat'.format(i))
            assert 'error' not in wallet.refresh()
        self.wallet = self.wallet0

    def stop(self):
        '''

        :return:
        '''
        if self.rpc_process_list:
            map(lambda w: w.store(), self.wallets)
            for r in self.rpc_process_list:
                print('wallet kill?',r.kill())
            # map(lambda rpc: rpc.kill(),self.rpc_process_list)
        if self.monerod_process:
            ret = self.daemon.save_bc()
            if ret['status'] != 'OK':
                self.log.info('save blockchain failed:{}'.format(ret))
            self.monerod_process.terminate()

    def getnewaddress(self,wallet_index = 0):
        wallet = getattr(self,'wallet{}'.format(wallet_index),None)
        if wallet:
            result = wallet.get_address()
            addr_num = len(result.get('addresses'))
            index = choice([i for i in range(addr_num)])
            return result['addresses'][index]['address']
        raise Exception('wallet{} not found'.format(wallet_index))

    def getblockcount(self):
        '''
        返回当前高度
        门罗币的height是从1开始算的，这里需要-1，为了与比例特同步，容易理解
        :return:
        '''
        return self.daemon.get_height()['height']

    def getblockhash(self, height):
        return self.daemon.on_get_block_hash(height)

    def generate(self, blocks, toaddr=None,wallet_index = 0):
        wallet = getattr(self, 'wallet{}'.format(wallet_index), None)
        if wallet:
            toaddr = toaddr if toaddr else self.getnewaddress(wallet_index=wallet_index)
            privk = wallet.query_key('view_key').key
            return self.daemon.generateblocks(toaddr, blocks=blocks, miner_sec_key=privk)
        raise Exception('wallet{} not found'.format(wallet_index))

    def getbestblockhash(self):
        height = self.daemon.get_height()['height']
        return self.getblockhash(height)

    def getbalance(self,wallet_index = 0):
        wallet = getattr(self, 'wallet{}'.format(wallet_index), None)
        if wallet:
            return wallet.get_balance()['balance']
        raise Exception('wallet{} not found'.format(wallet_index))

    def getpeerinfo(self):
        return self.daemon.get_connections()


class Response(dict):
    def __init__(self, d):
        if not isinstance(d, dict):
            self['data'] = d
        else:
            for k in d.keys():
                if type(d[k]) == dict:
                    self[k] = Response(d[k])
                elif type(d[k]) == list:
                    self[k] = []
                    for i in range(len(d[k])):
                        if type(d[k][i]) == dict:
                            self[k].append(Response(d[k][i]))
                        else:
                            self[k].append(d[k][i])
                else:
                    self[k] = d[k]

    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        self[key] = value

    def __eq__(self, other):
        if type(other) == dict:
            return self == Response(other)
        if self.keys() != other.keys():
            return False
        for k in self.keys():
            if self[k] != other[k]:
                return False
        return True

    def assert_message(self, message):
        if message not in json.dumps(self):
            raise AssertionError('{} not in {}'.format(message, json.dumps(self)))


class JSONRPC(object):
    def __init__(self, url,timeout = 60):
        self.url = url
        self.session = requests.session()
        self.session.keep_alive = False
        self.timeout = timeout

    def send_request(self, path, inputs, result_field=None):
        resp = self.session.post(
            self.url + path,
            data=json.dumps(inputs),
            timeout=self.timeout,
            headers={
                'content-type': 'application/json',
                'Connection': 'close'
            })
        try:
            res = resp.json(strict=False)
        except Exception as e:
            print('exception:', e)
            print('rpc return is not a json,raw data:\n{}'.format(resp))
            res = {'result': 'json not found'}

        assert 'error' not in res, res

        if result_field:
            res = res[result_field]
        return Response(res)

    def send_json_rpc_request(self, inputs):
        return self.send_request("/json_rpc", inputs, 'result')


class Daemon(object):

    def __init__(self, protocol='http', host=get_local_ip(), port=0, idx=0,rpctimeout = 60):
        self.host = host
        self.port = port
        self.rpc = JSONRPC(
            '{protocol}://{host}:{port}'.format(protocol=protocol, host=host, port=port if port else 18180 + idx),timeout=rpctimeout)
        self.is_daemon = True

    def count_mempool(self):
        ret = self.rpc.send_request('/get_transaction_pool_stats', {})
        if ret.get('pool_stats'):
            return ret.pool_stats.txs_total
        raise Exception("mempool not return?{}".format(ret))


    def setmocktime(self,mock_time):
        if not mock_time:
            return
        setmocktime = {
            'method': 'setmocktime',
            'params': {
                'timestamp': mock_time,
            },
            'jsonrpc': '2.0',
            'id': '0',
        }
        return self.rpc.send_json_rpc_request(setmocktime)

    def sync_info(self):
        sync_info = {
            'method': 'sync_info',
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(sync_info)

    def save_bc(self):
        return self.rpc.send_request('/save_bc', {})

    def get_block_count(self):
        get_block_count = {
            'method': 'get_block_count',
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(get_block_count)

    def getblocktemplate(self, address, prev_block=""):
        getblocktemplate = {
            'method': 'getblocktemplate',
            'params': {
                'wallet_address': address,
                'reserve_size': 1,
                'prev_block': prev_block,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(getblocktemplate)

    def send_raw_transaction(self, tx_as_hex, do_not_relay=False, do_sanity_checks=True):
        send_raw_transaction = {
            'tx_as_hex': tx_as_hex,
            'do_not_relay': do_not_relay,
            'do_sanity_checks': do_sanity_checks,
        }
        return self.rpc.send_request("/send_raw_transaction", send_raw_transaction)

    def submitblock(self, block):
        submitblock = {
            'method': 'submitblock',
            'params': [block],
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(submitblock)

    def getblock(self, height=0):
        getblock = {
            'method': 'getblock',
            'params': {
                'height': height
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(getblock)

    def getlastblockheader(self):
        getlastblockheader = {
            'method': 'getlastblockheader',
            'params': {
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(getlastblockheader)

    def getblockheaderbyhash(self, hash):
        getblockheaderbyhash = {
            'method': 'getblockheaderbyhash',
            'params': {
                'hash': hash,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(getblockheaderbyhash)

    def getblockheaderbyheight(self, height):
        getblockheaderbyheight = {
            'method': 'getblockheaderbyheight',
            'params': {
                'height': height,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(getblockheaderbyheight)

    def getblockheadersrange(self, start_height, end_height, fill_pow_hash=False):
        getblockheadersrange = {
            'method': 'getblockheadersrange',
            'params': {
                'start_height': start_height,
                'end_height': end_height,
                'fill_pow_hash': fill_pow_hash,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(getblockheadersrange)

    def get_connections(self):
        get_connections = {
            'method': 'get_connections',
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(get_connections)

    def get_info(self):
        get_info = {
            'method': 'get_info',
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(get_info)

    def hard_fork_info(self):
        hard_fork_info = {
            'method': 'hard_fork_info',
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(hard_fork_info)

    def generateblocks(self, address, blocks=1, prev_block="", starting_nonce=0, miner_sec_key=""):
        generateblocks = {
            'method': 'generateblocks',
            'params': {
                'amount_of_blocks': blocks,
                'reserve_size': 20,
                'wallet_address': address,
                'prev_block': prev_block,
                'starting_nonce': starting_nonce,
                'miner_sec_key': miner_sec_key,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(generateblocks)

    def get_height(self):
        get_height = {
            'method': 'get_height',
            'jsonrpc': '2.0',
            'id': '0'
        }
        ret = self.rpc.send_request("/get_height", get_height)
        ret['height'] = int(ret['height']) - 1
        return ret

    def pop_blocks(self, nblocks=1):
        pop_blocks = {
            'nblocks': nblocks,
        }
        return self.rpc.send_request("/pop_blocks", pop_blocks)

    def start_mining(self, miner_address, threads_count=0, do_background_mining=False, ignore_battery=False):
        start_mining = {
            'miner_address': miner_address,
            'threads_count': threads_count,
            'do_background_mining': do_background_mining,
            'ignore_battery': ignore_battery,
        }
        return self.rpc.send_request('/start_mining', start_mining)

    def stop_mining(self):
        stop_mining = {
        }
        return self.rpc.send_request('/stop_mining', stop_mining)

    def mining_status(self):
        mining_status = {
        }
        return self.rpc.send_request('/mining_status', mining_status)

    def get_transaction_pool(self):
        get_transaction_pool = {
        }
        return self.rpc.send_request('/get_transaction_pool', get_transaction_pool)

    def get_transaction_pool_hashes(self):
        get_transaction_pool_hashes = {
        }
        return self.rpc.send_request('/get_transaction_pool_hashes', get_transaction_pool_hashes)

    def flush_txpool(self, txids=[]):
        flush_txpool = {
            'method': 'flush_txpool',
            'params': {
                'txids': txids
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(flush_txpool)

    def get_version(self):
        get_version = {
            'method': 'get_version',
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(get_version)

    def get_bans(self):
        get_bans = {
            'method': 'get_bans',
            'params': {
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(get_bans)

    def set_bans(self, bans=[]):
        set_bans = {
            'method': 'set_bans',
            'params': {
                'bans': bans
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(set_bans)

    def get_transactions(self, txs_hashes=[], decode_as_json=False, prune=False, split=False):
        get_transactions = {
            'txs_hashes': txs_hashes,
            'decode_as_json': decode_as_json,
            'prune': prune,
            'split': split,
        }
        return self.rpc.send_request('/get_transactions', get_transactions)

    def get_outs(self, outputs=[], get_txid=False):
        get_outs = {
            'outputs': outputs,
            'get_txid': get_txid,
        }
        return self.rpc.send_request('/get_outs', get_outs)

    def get_coinbase_tx_sum(self, height, count):
        get_coinbase_tx_sum = {
            'method': 'get_coinbase_tx_sum',
            'params': {
                'height': height,
                'count': count,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(get_coinbase_tx_sum)

    def get_output_distribution(self, amounts=[], from_height=0, to_height=0, cumulative=False, binary=False,
                                compress=False):
        get_output_distribution = {
            'method': 'get_output_distribution',
            'params': {
                'amounts': amounts,
                'from_height': from_height,
                'to_height': to_height,
                'cumulative': cumulative,
                'binary': binary,
                'compress': compress,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(get_output_distribution)

    def get_output_histogram(self, amounts=[], min_count=0, max_count=0, unlocked=False, recent_cutoff=0):
        get_output_histogram = {
            'method': 'get_output_histogram',
            'params': {
                'amounts': amounts,
                'min_count': min_count,
                'max_count': max_count,
                'unlocked': unlocked,
                'recent_cutoff': recent_cutoff,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(get_output_histogram)

    def set_log_level(self, level):
        set_log_level = {
            'level': level,
        }
        return self.rpc.send_request('/set_log_level', set_log_level)

    def set_log_categories(self, categories=''):
        set_log_categories = {
            'categories': categories,
        }
        return self.rpc.send_request('/set_log_categories', set_log_categories)

    def get_alt_blocks_hashes(self):
        get_alt_blocks_hashes = {
        }
        return self.rpc.send_request('/get_alt_blocks_hashes', get_alt_blocks_hashes)

    def get_alternate_chains(self):
        get_alternate_chains = {
            'method': 'get_alternate_chains',
            'params': {
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(get_alternate_chains)

    def bid(self, amount, block_height, pub_view_key):
        bid = {
            'amount': amount,
            'block_height': block_height,
            'pub_view_key': pub_view_key,
        }
        ret = self.rpc.send_request('/bid', bid)
        try:
            result = json.loads(ret.txid)
            ret.pop('txid')
            ret.data = result
            return Response(ret)
        except Exception as e:
            return ret

    def get_peer_list(self):
        return self.rpc.send_request('/get_peer_list', {})

    def on_get_block_hash(self, height):
        on_get_block_hash = {
            'method': 'on_get_block_hash',
            'params': [height],
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(on_get_block_hash)


class Wallet(object):

    def __init__(self, protocol='http', host=get_local_ip(), port=0, idx=0,rpctimeout = 60):
        self.host = host
        self.port = port
        self.rpc = JSONRPC(
            '{protocol}://{host}:{port}'.format(protocol=protocol, host=host, port=port if port else 18090 + idx),timeout=rpctimeout)

    def store(self):
        store = {
            'method': 'store',
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(store)

    def make_uniform_destinations(self, address, transfer_amount, transfer_number_of_destinations=1):
        destinations = []
        for i in range(transfer_number_of_destinations):
            destinations.append({"amount": transfer_amount, "address": address})
        return destinations

    def make_destinations(self, addresses, transfer_amounts):
        destinations = []
        for i in range(len(addresses)):
            destinations.append({'amount': transfer_amounts[i], 'address': addresses[i]})
        return destinations

    def transfer(self, destinations, account_index=0, subaddr_indices=[], priority=0, ring_size=0, unlock_time=0,
                 payment_id='', get_tx_key=True, do_not_relay=False, get_tx_hex=False, get_tx_metadata=False):
        transfer = {
            'method': 'transfer',
            'params': {
                'destinations': destinations,
                'account_index': account_index,
                'subaddr_indices': subaddr_indices,
                'priority': priority,
                'ring_size': ring_size,
                'unlock_time': unlock_time,
                'payment_id': payment_id,
                'get_tx_key': get_tx_key,
                'do_not_relay': do_not_relay,
                'get_tx_hex': get_tx_hex,
                'get_tx_metadata': get_tx_metadata,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(transfer)

    def transfer_split(self, destinations, account_index=0, subaddr_indices=[], priority=0, ring_size=0, unlock_time=0,
                       payment_id='', get_tx_key=True, do_not_relay=False, get_tx_hex=False, get_tx_metadata=False):
        transfer = {
            "method": "transfer_split",
            "params": {
                'destinations': destinations,
                'account_index': account_index,
                'subaddr_indices': subaddr_indices,
                'priority': priority,
                'ring_size': ring_size,
                'unlock_time': unlock_time,
                'payment_id': payment_id,
                'get_tx_key': get_tx_key,
                'do_not_relay': do_not_relay,
                'get_tx_hex': get_tx_hex,
                'get_tx_metadata': get_tx_metadata,
            },
            "jsonrpc": "2.0",
            "id": "0"
        }
        return self.rpc.send_json_rpc_request(transfer)

    def get_transfer_by_txid(self, txid, account_index=0):
        get_transfer_by_txid = {
            'method': 'get_transfer_by_txid',
            'params': {
                'txid': txid,
                'account_index': account_index,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(get_transfer_by_txid)

    def get_bulk_payments(self, payment_ids=[], min_block_height=0):
        get_bulk_payments = {
            'method': 'get_bulk_payments',
            'params': {
                'payment_ids': payment_ids,
                'min_block_height': min_block_height,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(get_bulk_payments)

    def describe_transfer(self, unsigned_txset='', multisig_txset=''):
        describe_transfer = {
            'method': 'describe_transfer',
            'params': {
                'unsigned_txset': unsigned_txset,
                'multisig_txset': multisig_txset,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(describe_transfer)

    def create_wallet(self, filename='', password='', language='English'):
        create_wallet = {
            'method': 'create_wallet',
            'params': {
                'filename': filename,
                'password': password,
                'language': language
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(create_wallet)

    def get_balance(self, account_index=0, address_indices=[], all_accounts=False):
        get_balance = {
            'method': 'get_balance',
            'params': {
                'account_index': account_index,
                'address_indices': address_indices,
                'all_accounts': all_accounts,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(get_balance)

    def sweep_dust(self):
        sweep_dust = {
            'method': 'sweep_dust',
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(sweep_dust)

    def sweep_all(self, address='', account_index=0, subaddr_indices=[], priority=0, ring_size=0, outputs=1,
                  unlock_time=0, payment_id='', get_tx_keys=False, below_amount=0, do_not_relay=False, get_tx_hex=False,
                  get_tx_metadata=False):
        sweep_all = {
            'method': 'sweep_all',
            'params': {
                'address': address,
                'account_index': account_index,
                'subaddr_indices': subaddr_indices,
                'priority': priority,
                'ring_size': ring_size,
                'outputs': outputs,
                'unlock_time': unlock_time,
                'payment_id': payment_id,
                'get_tx_keys': get_tx_keys,
                'below_amount': below_amount,
                'do_not_relay': do_not_relay,
                'get_tx_hex': get_tx_hex,
                'get_tx_metadata': get_tx_metadata,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(sweep_all)

    def sweep_single(self, address='', priority=0, ring_size=0, outputs=1, unlock_time=0, payment_id='',
                     get_tx_keys=False, key_image="", do_not_relay=False, get_tx_hex=False, get_tx_metadata=False):
        sweep_single = {
            'method': 'sweep_single',
            'params': {
                'address': address,
                'priority': priority,
                'ring_size': ring_size,
                'outputs': outputs,
                'unlock_time': unlock_time,
                'payment_id': payment_id,
                'get_tx_keys': get_tx_keys,
                'key_image': key_image,
                'do_not_relay': do_not_relay,
                'get_tx_hex': get_tx_hex,
                'get_tx_metadata': get_tx_metadata,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(sweep_single)

    def get_address(self, account_index=0, subaddresses=[]):
        get_address = {
            'method': 'get_address',
            'params': {
                'account_index': account_index,
                'address_index': subaddresses
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(get_address)

    def create_account(self, label=""):
        create_account = {
            'method': 'create_account',
            'params': {
                'label': label
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(create_account)

    def create_address(self, account_index=0, label=""):
        create_address = {
            'method': 'create_address',
            'params': {
                'account_index': account_index,
                'label': label
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(create_address)

    def label_address(self, subaddress_index, label):
        label_address = {
            'method': 'label_address',
            'params': {
                'index': {'major': subaddress_index[0], 'minor': subaddress_index[1]},
                'label': label
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(label_address)

    def label_account(self, account_index, label):
        label_account = {
            'method': 'label_account',
            'params': {
                'account_index': account_index,
                'label': label
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(label_account)

    def get_address_index(self, address):
        get_address_index = {
            'method': 'get_address_index',
            'params': {
                'address': address
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(get_address_index)

    def query_key(self, key_type):
        query_key = {
            'method': 'query_key',
            'params': {
                'key_type': key_type
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(query_key)

    def restore_deterministic_wallet(self, seed='', seed_offset='', filename='', restore_height=0, password='',
                                     language='', autosave_current=True):
        restore_deterministic_wallet = {
            'method': 'restore_deterministic_wallet',
            'params': {
                'restore_height': restore_height,
                'filename': filename,
                'seed': seed,
                'seed_offset': seed_offset,
                'password': password,
                'language': language,
                'autosave_current': autosave_current,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(restore_deterministic_wallet)

    def generate_from_keys(self, restore_height=0, filename="", password="", address="", spendkey="", viewkey="",
                           autosave_current=True):
        generate_from_keys = {
            'method': 'generate_from_keys',
            'params': {
                'restore_height': restore_height,
                'filename': filename,
                'address': address,
                'spendkey': spendkey,
                'viewkey': viewkey,
                'password': password,
                'autosave_current': autosave_current,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(generate_from_keys)

    def open_wallet(self, filename, password='', autosave_current=True):
        open_wallet = {
            'method': 'open_wallet',
            'params': {
                'filename': filename,
                'password': password,
                'autosave_current': autosave_current,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(open_wallet)

    def close_wallet(self, autosave_current=True):
        close_wallet = {
            'method': 'close_wallet',
            'params': {
                'autosave_current': autosave_current
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(close_wallet)

    def refresh(self):
        refresh = {
            'method': 'refresh',
            'params': {
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(refresh)

    def incoming_transfers(self, transfer_type='all', account_index=0, subaddr_indices=[]):
        incoming_transfers = {
            'method': 'incoming_transfers',
            'params': {
                'transfer_type': transfer_type,
                'account_index': account_index,
                'subaddr_indices': subaddr_indices,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(incoming_transfers)

    def get_transfers(self, in_=True, out=True, pending=True, failed=True, pool=True, min_height=None, max_height=None,
                      account_index=0, subaddr_indices=[], all_accounts=False):
        get_transfers = {
            'method': 'get_transfers',
            'params': {
                'in': in_,
                'out': out,
                'pending': pending,
                'failed': failed,
                'pool': pool,
                'min_height': min_height,
                'max_height': max_height,
                'filter_by_height': min_height or max_height,
                'account_index': account_index,
                'subaddr_indices': subaddr_indices,
                'all_accounts': all_accounts,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(get_transfers)

    def make_integrated_address(self, standard_address='', payment_id=''):
        make_integrated_address = {
            'method': 'make_integrated_address',
            'params': {
                'standard_address': standard_address,
                'payment_id': payment_id,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(make_integrated_address)

    def split_integrated_address(self, integrated_address):
        split_integrated_address = {
            'method': 'split_integrated_address',
            'params': {
                'integrated_address': integrated_address,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(split_integrated_address)

    def auto_refresh(self, enable, period=0):
        auto_refresh = {
            'method': 'auto_refresh',
            'params': {
                'enable': enable,
                'period': period
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(auto_refresh)

    def set_daemon(self, address, trusted=False, ssl_support="autodetect", ssl_private_key_path="",
                   ssl_certificate_path="", ssl_allowed_certificates=[], ssl_allowed_fingerprints=[],
                   ssl_allow_any_cert=False):
        set_daemon = {
            'method': 'set_daemon',
            'params': {
                'address': address,
                'trusted': trusted,
                'ssl_support': ssl_support,
                'ssl_private_key_path': ssl_private_key_path,
                'ssl_certificate_path': ssl_certificate_path,
                'ssl_allowed_certificates': ssl_allowed_certificates,
                'ssl_allowed_fingerprints': ssl_allowed_fingerprints,
                'ssl_allow_any_cert': ssl_allow_any_cert,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(set_daemon)

    def is_multisig(self):
        is_multisig = {
            'method': 'is_multisig',
            'params': {
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(is_multisig)

    def prepare_multisig(self):
        prepare_multisig = {
            'method': 'prepare_multisig',
            'params': {
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(prepare_multisig)

    def make_multisig(self, multisig_info, threshold, password=''):
        make_multisig = {
            'method': 'make_multisig',
            'params': {
                'multisig_info': multisig_info,
                'threshold': threshold,
                'password': password,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(make_multisig)

    def exchange_multisig_keys(self, multisig_info, password=''):
        exchange_multisig_keys = {
            'method': 'exchange_multisig_keys',
            'params': {
                'multisig_info': multisig_info,
                'password': password,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(exchange_multisig_keys)

    def export_multisig_info(self):
        export_multisig_info = {
            'method': 'export_multisig_info',
            'params': {
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(export_multisig_info)

    def import_multisig_info(self, info=[]):
        import_multisig_info = {
            'method': 'import_multisig_info',
            'params': {
                'info': info
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(import_multisig_info)

    def sign_multisig(self, tx_data_hex):
        sign_multisig = {
            'method': 'sign_multisig',
            'params': {
                'tx_data_hex': tx_data_hex
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(sign_multisig)

    def submit_multisig(self, tx_data_hex):
        submit_multisig = {
            'method': 'submit_multisig',
            'params': {
                'tx_data_hex': tx_data_hex
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(submit_multisig)

    def sign_transfer(self, unsigned_txset, export_raw=False, get_tx_keys=False):
        sign_transfer = {
            'method': 'sign_transfer',
            'params': {
                'unsigned_txset': unsigned_txset,
                'export_raw': export_raw,
                'get_tx_keys': get_tx_keys,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(sign_transfer)

    def submit_transfer(self, tx_data_hex):
        submit_transfer = {
            'method': 'submit_transfer',
            'params': {
                'tx_data_hex': tx_data_hex,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(submit_transfer)

    def get_tx_key(self, txid):
        get_tx_key = {
            'method': 'get_tx_key',
            'params': {
                'txid': txid,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(get_tx_key)

    def check_tx_key(self, txid='', tx_key='', address=''):
        check_tx_key = {
            'method': 'check_tx_key',
            'params': {
                'txid': txid,
                'tx_key': tx_key,
                'address': address,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(check_tx_key)

    def get_tx_proof(self, txid='', address='', message=''):
        get_tx_proof = {
            'method': 'get_tx_proof',
            'params': {
                'txid': txid,
                'address': address,
                'message': message,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(get_tx_proof)

    def check_tx_proof(self, txid='', address='', message='', signature=''):
        check_tx_proof = {
            'method': 'check_tx_proof',
            'params': {
                'txid': txid,
                'address': address,
                'message': message,
                'signature': signature,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(check_tx_proof)

    def get_reserve_proof(self, all_=True, account_index=0, amount=0, message=''):
        get_reserve_proof = {
            'method': 'get_reserve_proof',
            'params': {
                'all': all_,
                'account_index': account_index,
                'amount': amount,
                'message': message,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(get_reserve_proof)

    def check_reserve_proof(self, address='', message='', signature=''):
        check_reserve_proof = {
            'method': 'check_reserve_proof',
            'params': {
                'address': address,
                'message': message,
                'signature': signature,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(check_reserve_proof)

    def sign(self, data):
        sign = {
            'method': 'sign',
            'params': {
                'data': data,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(sign)

    def verify(self, data, address, signature):
        verify = {
            'method': 'verify',
            'params': {
                'data': data,
                'address': address,
                'signature': signature,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(verify)

    def get_height(self):
        get_height = {
            'method': 'get_height',
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(get_height)

    def relay_tx(self, hex_):
        relay_tx = {
            'method': 'relay_tx',
            'params': {
                'hex': hex_,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(relay_tx)

    def get_languages(self):
        get_languages = {
            'method': 'get_languages',
            'params': {
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(get_languages)

    def export_outputs(self):
        export_outputs = {
            'method': 'export_outputs',
            'params': {
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(export_outputs)

    def import_outputs(self, outputs_data_hex):
        import_outputs = {
            'method': 'import_outputs',
            'params': {
                'outputs_data_hex': outputs_data_hex
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(import_outputs)

    def export_key_images(self, all_=False):
        export_key_images = {
            'method': 'export_key_images',
            'params': {
                'all': all_
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(export_key_images)

    def import_key_images(self, signed_key_images, offset=0):
        import_key_images = {
            'method': 'import_key_images',
            'params': {
                'offset': offset,
                'signed_key_images': signed_key_images,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(import_key_images)

    def set_log_level(self, level):
        set_log_level = {
            'method': 'set_log_level',
            'params': {
                'level': level,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(set_log_level)

    def set_log_categories(self, categories):
        set_log_categories = {
            'method': 'set_log_categories',
            'params': {
                'categories': categories,
            },
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(set_log_categories)

    def get_version(self):
        get_version = {
            'method': 'get_version',
            'jsonrpc': '2.0',
            'id': '0'
        }
        return self.rpc.send_json_rpc_request(get_version)
