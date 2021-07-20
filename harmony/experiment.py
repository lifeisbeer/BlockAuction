from helper import *
import os
import json
from web3 import Web3, HTTPProvider
import secrets
import sys
from ecies.utils import generate_key
from ecies import encrypt, decrypt
import time
import random
import hashlib
from operator import attrgetter
import matplotlib.pyplot as plt
import time
from datetime import datetime

# setup web3 instance
f = open('./data/endpoint.dat', 'r')
#f = open('./data/endpoint_main.dat', 'r')
endpoint = f.read()
f.close()
w3 = Web3(HTTPProvider(endpoint))
if w3.isConnected():
    print("Web3 Connected.")
else:
    sys.exit("Couldn't connect to the blockchain via web3.")

# ------------------------------------------------------------------------------
# Parameters
# ------------------------------------------------------------------------------

# general parameters
assets = ['g','t','f'] # list of tradable assets
matchings = ["Periodic", "Volume", "MV"] # list of matching modes
verbose = False #True
over_verbose = True
gas_verbose = False #True
graph_verbose = False #True
total_gas = 0

clKey = [] # keeps private key of all clients' ethereum addresses
clAdd = [] # keeps accoint of all clients' ethereum addresses
ciphertexts = {} # keeps ciphertext of order for every client address
addr2keys = {} # keeps client specific public key for every client address
addr2name = {} # keeps name given to every client address

# experiment parameters
matching = 1
client_num = 1000
deposit = w3.toWei(0.01, 'ether')
duration = 1 # just for experiments, should be set to something resonable

# ------------------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------------------

# path to parent directory
parent_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# contract path
contract_path = parent_path+'/truffle/build/contracts/darkPool.json'
contractAddress = ''

# open compiled file and get abi
truffleFile = json.load(open(contract_path))
abi = truffleFile['abi']

# get private key and account of operator
f=open('./data/key_owner.dat', 'r')
opKey = f.read()
f.close()
opAdd = w3.eth.account.privateKeyToAccount(opKey).address

# create clients and transfer some funds
nonce = w3.eth.get_transaction_count(opAdd)
tx_hashes = []
for i in range(client_num):
    # generate private keys for clients
    prKey = "0x" + secrets.token_hex(32)
    # store addresses and keys
    clKey.append(prKey)
    addr = w3.eth.account.privateKeyToAccount(prKey).address
    clAdd.append(addr)
    addr2name[addr] = str(i)
    # transfer funds to client
    # sign transaction
    sign_tx = w3.eth.account.sign_transaction(
        {
            'chainId': w3.eth.chainId,
            'from': opAdd,
            'to': addr,
            'value': deposit*2,
            'nonce': nonce+i,
            'gas': 6721975,
            'gasPrice': w3.toWei(1, 'gwei')
        },
        opKey
    )
    # send the transaction
    tx_hash = w3.eth.sendRawTransaction(sign_tx.rawTransaction)
    tx_hashes.append(tx_hash)
# wait for transaction receipt
for i in range(client_num):
    tx_receipt = w3.eth.waitForTransactionReceipt(tx_hashes[i], timeout=3000)
    if verbose:
        print("Client {} created with address {}.".format(i, clAdd[i]))

# if contract is not deployed, deploy it and return address
if not contractAddress:
    contractAddress = deploy_contract(w3, contract_path)

# contract interface
darkPool = w3.eth.contract(address=contractAddress, abi=abi)

# ------------------------------------------------------------------------------
# Contract function calls
# ------------------------------------------------------------------------------

print("START: {}.".format(w3.eth.blockNumber))

if over_verbose:
    print("-----------------------------------------------------------------------------------------------")
    print("At Registration phase. Current block: {}.".format(w3.eth.blockNumber))

# register some clients
tx_hashes = []
nonce = w3.eth.getTransactionCount(opAdd)
for i in range(client_num):
    # this address will be send to the operator by the client in the final
    # application, but for now we will just use one of the existing addresses
    addr = clAdd[i]
    # generate a key pair and store
    addr2keys[addr] = generate_key()
    pk = addr2keys[addr].public_key.format(True)
    # send the address and the corresonding public key to the contract
    # build transaction
    tx = darkPool.functions.register_client(addr, pk).buildTransaction({
        'from': opAdd,
        'nonce': nonce+i,
        'gas': 6721975,
        'gasPrice': w3.toWei(1, 'gwei')
    })
    # sign transaction
    sign_tx = w3.eth.account.signTransaction(tx, opKey)
    # send the transaction
    tx_hash = w3.eth.sendRawTransaction(sign_tx.rawTransaction)
    tx_hashes.append(tx_hash)
# wait for all transactions to go through
for i in range(len(tx_hashes)):
    tx_receipt = w3.eth.waitForTransactionReceipt(tx_hashes[i])
    total_gas += tx_receipt.gasUsed
    if verbose:
        print("Client {} registered.".format(i))
    if gas_verbose:
        print("Gas used: {}.".format(tx_receipt.gasUsed))

# initiate trading phase
# build transaction
tx = darkPool.functions.trading_phase(duration, matching, deposit).buildTransaction({
    'from': opAdd,
    'nonce': w3.eth.getTransactionCount(opAdd),
    'gas': 6721975,
    'gasPrice': w3.toWei(1, 'gwei')
})
# sign transaction
sign_tx = w3.eth.account.signTransaction(tx, opKey)
# send the transaction
tx_hash = w3.eth.sendRawTransaction(sign_tx.rawTransaction)
tx_receipt = w3.eth.waitForTransactionReceipt(tx_hash)
total_gas += tx_receipt.gasUsed

# save block at the start of the trading day
start = w3.eth.blockNumber

expiration = darkPool.functions.expiration().call()
if over_verbose:
    print("Total gas used during the registration phase (client registration): {}.".format(total_gas))
    total_gas = 0
    print("-----------------------------------------------------------------------------------------------")
    print("At Trading phase. Current block: {}, Expiration: {}.".format(tx_receipt.blockNumber, expiration))
    print("Auction Matching type: {}.".format(matchings[matching]))
    print("Tx Hash:", tx_receipt.transactionHash.hex())
    print("Timestamp:", datetime.utcfromtimestamp(w3.eth.getBlock(tx_receipt.blockNumber).timestamp).strftime('%Y-%m-%d %H:%M:%S'))
if gas_verbose:
    print("Gas used: {}.".format(tx_receipt.gasUsed))

# now the clients that wish to transact will send in their orders
# for this demonstration we will simulate this from this script

# the register clients send their commitments
tx_hashes = []
for i in range(client_num):
    addr = clAdd[i]
    key = clKey[i]
    # order is a comma-separated string consisting of
    # 1) char: direction, b for buy & s for sell
    # 2) char: instrument, representing tradable asset
    # 3) int : limit price (in pence)
    # 4) int : size of order
    # 5) int : minimum order execution size (mes)
    # 6) int : random nonce
    # eg "s,t,100,1005,50,1234" represents a sell order for asset t with
    #    volume 100, price 10.5 each and minimum order execution size 50
    # order will be provided by the client, generate random for this test
    order = create_random_order(assets, 100, 100)
    '''
    # for this demonstration, client 3 will send an invalid order
    if i == 3:
        order.type = 'a' # invalid type
        #order.price = -1 # invalid price
        #order.volume = -1 # invalid volume
        #order.mes = order.volume + 1 # invalid mes
        print("Client 3 will send an invalid order.")
    '''
    # format order into string
    order_string = "{},{},{},{},{}".format(order.type,order.asset,
                   order.price,order.volume,order.mes)
    '''
    # for this demonstration, client 3 will send an empty order
    if i == 3:
        order_string = "None"
    '''
    if verbose:
        print("Client's {} order: {}.".format(i, order_string))
    # generate random 32 byte nonce
    nonce = os.urandom(32)
    # append nonce and encode order string
    order_bytes = order_string.encode('utf-8') + nonce
    # get assigned public key from contract
    pk = darkPool.functions.us_pk(addr).call()
    # encrypt order bytes
    ciphertext = encrypt(pk, order_bytes)
    ciphertexts[addr] = ciphertext
    # hash ciphertext
    #hash = hashlib.sha3_256(ciphertext).digest()
    order_hash = w3.solidityKeccak(['bytes'], [ciphertext])
    # send commitment (hash)
    # build transaction
    tx = darkPool.functions.commit_order(order_hash).buildTransaction({
        'from': addr,
        'value': deposit,
        'nonce': w3.eth.getTransactionCount(addr),
        'gas': 6721975,
        'gasPrice': w3.toWei(1, 'gwei')
    })
    # sign transaction
    sign_tx = w3.eth.account.signTransaction(tx, key)
    # send the transaction
    tx_hash = w3.eth.sendRawTransaction(sign_tx.rawTransaction)
    tx_hashes.append(tx_hash)
    # wait for transaction receipt
    #tx_receipt = w3.eth.waitForTransactionReceipt(tx_hash)
# wait for all transactions to go through
for i in range(len(tx_hashes)):
    tx_receipt = w3.eth.waitForTransactionReceipt(tx_hashes[i])
    total_gas += tx_receipt.gasUsed
    if verbose:
        print("Client {} send order.".format(i))
    if gas_verbose:
        print("Gas used: {}.".format(tx_receipt.gasUsed))

'''
# for this demonstration, client 1 will cancel their commitment
tx_hash = darkPool.functions.cancel_order().transact({
            'from':w3.eth.accounts[1],
            'value':deposit
           })
ciphertexts.pop(w3.eth.accounts[1])
tx_receipt = w3.eth.waitForTransactionReceipt(tx_hash)
if verbose:
    print("Client 1 canceled order")
if gas_verbose:
    total_gas += tx_receipt.gasUsed
    print("Gas used:", tx_receipt.gasUsed)
'''

# the operator waits until (at least) the expiration of the trading phase
while w3.eth.blockNumber < expiration:
    time.sleep(1)

# operator initiates reveil phase
# build transaction
tx = darkPool.functions.reveal_phase(duration).buildTransaction({
    'from': opAdd,
    'nonce': w3.eth.getTransactionCount(opAdd),
    'gas': 6721975,
    'gasPrice': w3.toWei(1, 'gwei')
})
# sign transaction
sign_tx = w3.eth.account.signTransaction(tx, opKey)
# send the transaction
tx_hash = w3.eth.sendRawTransaction(sign_tx.rawTransaction)
tx_receipt = w3.eth.waitForTransactionReceipt(tx_hash)
total_gas += tx_receipt.gasUsed

expiration = darkPool.functions.expiration().call()
if over_verbose:
    print("Total gas used during the trading phase: {}.".format(total_gas))
    total_gas = 0
    print("-----------------------------------------------------------------------------------------------")
    print("At Reveal phase. Current block: {}, Expiration: {}.".format(tx_receipt.blockNumber, expiration))
    print("Tx Hash:", tx_receipt.transactionHash.hex())
    print("Timestamp:", datetime.utcfromtimestamp(w3.eth.getBlock(tx_receipt.blockNumber).timestamp).strftime('%Y-%m-%d %H:%M:%S'))
if gas_verbose:
    print("Gas used: {}.".format(tx_receipt.gasUsed))

'''
#for demonstration, client 2 will send ciphertext that doesn't match
ciphertexts[w3.eth.accounts[2]] = ciphertexts[w3.eth.accounts[3]]
print("Client 2 will send ciphertext that doesn't match its commitment")
'''

# the clients reveal their orders to operator
tx_hashes = []
for i in range(client_num):
    addr = clAdd[i]
    key = clKey[i]
    if addr in ciphertexts.keys(): # in case a client does not send an order
        # each client knows its own ciphertext, here we retreive from list
        ciphertext = ciphertexts[addr]
        # reveal order
        # build transaction
        tx = darkPool.functions.reveal_order(ciphertext).buildTransaction({
            'from': addr,
            'nonce': w3.eth.getTransactionCount(addr),
            'gas': 6721975,
            'gasPrice': w3.toWei(1, 'gwei')
        })
        # sign transaction
        sign_tx = w3.eth.account.signTransaction(tx, key)
        # send the transaction
        tx_hash = w3.eth.sendRawTransaction(sign_tx.rawTransaction)
        tx_hashes.append(tx_hash)
        #tx_receipt = w3.eth.waitForTransactionReceipt(tx_hash)
# wait for all transactions to go through
for i in range(len(tx_hashes)):
    tx_receipt = w3.eth.waitForTransactionReceipt(tx_hashes[i])
    total_gas += tx_receipt.gasUsed
    if verbose:
        print("Client {} revealed order.".format(i)) # numbering might not be entirly correct but it's fine
    if gas_verbose:
        print("Gas used: {}.".format(tx_receipt.gasUsed))

# the operator waits until (at least) the expiration of the reveal phase
while w3.eth.blockNumber < expiration:
    time.sleep(1)

# operator initiates calculation phase
# build transaction
tx = darkPool.functions.calc_phase().buildTransaction({
    'from': opAdd,
    'nonce': w3.eth.getTransactionCount(opAdd),
    'gas': 6721975,
    'gasPrice': w3.toWei(1, 'gwei')
})
# sign transaction
sign_tx = w3.eth.account.signTransaction(tx, opKey)
# send the transaction
tx_hash = w3.eth.sendRawTransaction(sign_tx.rawTransaction)
tx_receipt = w3.eth.waitForTransactionReceipt(tx_hash)
total_gas += tx_receipt.gasUsed

if over_verbose:
    print("Total gas used during the reveal phase: {}.".format(total_gas))
    total_gas = 0
    print("-----------------------------------------------------------------------------------------------")
    print("At Calculation phase. Current block: {}.".format(tx_receipt.blockNumber))
    print("Tx Hash:", tx_receipt.transactionHash.hex())
    print("Timestamp:", datetime.utcfromtimestamp(w3.eth.getBlock(tx_receipt.blockNumber).timestamp).strftime('%Y-%m-%d %H:%M:%S'))
if gas_verbose:
    print("Gas used: {}.".format(tx_receipt.gasUsed))

invalid_addr = []
orders = {}
valid_asks = {}
valid_bids = {}
for a in assets:
    valid_asks[a] = []
    valid_bids[a] = []

time_start = time.perf_counter()

# operator reads commitments and ciphertext for each client
for i in range(client_num):
    # get client address from server memory
    addr = clAdd[i]
    # get order from contract
    order = darkPool.functions.orders(addr).call()
    #print(order)
    commitment = order[0]
    ciphertext = order[1]
    # get keys from memory
    secret = addr2keys[addr].secret
    # check if client submited an order
    if commitment == b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00':
        if verbose:
            print("Client", i, "did not submit an order.")
    else:
        # validate commitment
        status, order = validate_commitment(w3, assets, addr, commitment, ciphertext, secret, True)

        if status != 0:
            invalid_addr.append(addr)
            if verbose:
                print("Client {} {}.".format(i, order))
        else:
            # order is valid
            if verbose:
                print("Client's {} order: {}.".format(i, order))
            # calculate shared secret and append to order
            order.secret = shared_secret(secret, ciphertext)
            # check type and add to appropriate list
            orders[addr] = order.copy()
            if order.type == 's':
                valid_asks[order.asset].append(order.copy())
            elif order.type == 'b':
                valid_bids[order.asset].append(order.copy())

time_end = time.perf_counter()
if over_verbose:
    print("Order verification time: {}.".format(time_end-time_start))

if verbose:
    print("Addresses that send an invalid order: {}.".format(invalid_addr))
    #print(orders)
    #print(valid_asks)
    #print(valid_bids)

tx_hashes = []
nonce = w3.eth.getTransactionCount(opAdd)
# for each asset, perform matching
for a in assets:
    bids = valid_bids[a]
    asks = valid_asks[a]

    time_start = time.perf_counter()
    clearedPrice, clearedOrders = match(matching, a, bids, asks, verbose, graph_verbose)
    time_end = time.perf_counter()
    if over_verbose:
        print("Matching time for asset {}: {}.".format(a, time_end-time_start))

    # publish matched orders
    for c in clearedOrders:
        bAddr = c[0].client
        bSK = c[0].secret
        bName = addr2name[bAddr]
        sAddr = c[1].client
        sSK = c[1].secret
        sName = addr2name[sAddr]
        vol = c[2]
        if matching == 2:
            clearedPrice = c[3]

        if verbose:
            print("Matching: buyer {}, seller {}, volume {}, price {}."
                .format(bName, sName, vol, clearedPrice))

        # operator publishes matched orders
        # build transaction
        tx = darkPool.functions.reveal_match(a, bAddr, bSK, bName,
            sAddr, sSK, sName, vol, clearedPrice).buildTransaction({
                'from': opAdd,
                'nonce': nonce,
                'gas': 6721975,
                'gasPrice': w3.toWei(1, 'gwei')
            })
        nonce += 1
        # sign transaction
        sign_tx = w3.eth.account.signTransaction(tx, opKey)
        # send the transaction
        tx_hash = w3.eth.sendRawTransaction(sign_tx.rawTransaction)
        #tx_receipt = w3.eth.waitForTransactionReceipt(tx_hash)
        tx_hashes.append(tx_hash)

for tx_hash in tx_hashes:
    tx_receipt = w3.eth.waitForTransactionReceipt(tx_hash)
    total_gas += tx_receipt.gasUsed
    if verbose:
        print("Matching published.")
    if gas_verbose:
        print("Gas used: {}.".format(tx_receipt.gasUsed))

# operator initiates results phase
# build transaction
tx = darkPool.functions.res_phase(duration).buildTransaction({
    'from': opAdd,
    'nonce': w3.eth.getTransactionCount(opAdd),
    'gas': 6721975,
    'gasPrice': w3.toWei(1, 'gwei')
})
# sign transaction
sign_tx = w3.eth.account.signTransaction(tx, opKey)
# send the transaction
tx_hash = w3.eth.sendRawTransaction(sign_tx.rawTransaction)
tx_receipt = w3.eth.waitForTransactionReceipt(tx_hash)
total_gas += tx_receipt.gasUsed

expiration = darkPool.functions.expiration().call()
if over_verbose:
    print("Total gas used during the calculation phase: {}.".format(total_gas))
    total_gas = 0
    print("-----------------------------------------------------------------------------------------------")
    print("At Results phase. Current block: {}, Expiration: {}.".format(tx_receipt.blockNumber, expiration))
    print("Tx Hash:", tx_receipt.transactionHash.hex())
    print("Timestamp:", datetime.utcfromtimestamp(w3.eth.getBlock(tx_receipt.blockNumber).timestamp).strftime('%Y-%m-%d %H:%M:%S'))
if gas_verbose:
    print("Gas used: {}.".format(tx_receipt.gasUsed))

# get new published matchings
if verbose:
    print("Getting published matches from contract:")
    matches = darkPool.events.logTrade.getLogs(fromBlock=start)
    for m in matches:
        # get matching details
        buyer = m['args']["buyer"]
        seller = m['args']["seller"]
        asset = m['args']['asset']
        vol = m['args']["amount"]
        price = m['args']["price"]

        print("Found matchig between seller {} and buyer {}, for asset {} with price {} and volume {}."
          .format(seller, buyer, asset, price, vol))

# wait until the expiration of the results phase
while w3.eth.blockNumber < expiration:
    time.sleep(1)

# operator initiates registration phase
# build transaction
tx = darkPool.functions.reg_phase().buildTransaction({
    'from': opAdd,
    'nonce': w3.eth.getTransactionCount(opAdd),
    'gas': 6721975,
    'gasPrice': w3.toWei(1, 'gwei')
})
# sign transaction
sign_tx = w3.eth.account.signTransaction(tx, opKey)
# send the transaction
tx_hash = w3.eth.sendRawTransaction(sign_tx.rawTransaction)
tx_receipt = w3.eth.waitForTransactionReceipt(tx_hash)
total_gas += tx_receipt.gasUsed

if over_verbose:
    print("Total gas used during the results phase: {}.".format(total_gas))
    total_gas = 0
    print("-----------------------------------------------------------------------------------------------")
    print("At Registration phase. Current block: {}.".format(tx_receipt.blockNumber))
    print("Tx Hash:", tx_receipt.transactionHash.hex())
    print("Timestamp:", datetime.utcfromtimestamp(w3.eth.getBlock(tx_receipt.blockNumber).timestamp).strftime('%Y-%m-%d %H:%M:%S'))
if gas_verbose:
    print("Gas used: {}.".format(tx_receipt.gasUsed))

# delete all clients
tx_hashes = []
nonce = w3.eth.getTransactionCount(opAdd)
for i in range(client_num):
    addr = clAdd[i]
    addr2keys.pop(addr)
    # build transaction
    tx = darkPool.functions.remove_client(addr).buildTransaction({
        'from': opAdd,
        'nonce': nonce + i,
        'gas': 6721975,
        'gasPrice': w3.toWei(1, 'gwei')
    })
    # sign transaction
    sign_tx = w3.eth.account.signTransaction(tx, opKey)
    # send the transaction
    tx_hash = w3.eth.sendRawTransaction(sign_tx.rawTransaction)
    tx_hashes.append(tx_hash)
# wait for all transactions to go through
for i in range(len(tx_hashes)):
    tx_receipt = w3.eth.waitForTransactionReceipt(tx_hashes[i])
    total_gas += tx_receipt.gasUsed
    if verbose:
        print("Client", i+1, "deleted from contract.")
    if gas_verbose:
        print("Gas used: {}.".format(tx_receipt.gasUsed))
if over_verbose:
    print("Total gas used during the registration phase (client deletion): {}.".format(total_gas))
    total_gas = 0

# remaining balance in contract
if verbose:
    print("Remaining balance in contract: {}.".format(w3.eth.get_balance(contractAddress)))

print("END: {}.".format(w3.eth.blockNumber))

'''
# re-register all clients
tx_hashes = []
for i in range(0, client_num):
    addr = w3.eth.accounts[i]
    # generate a key pair and store
    addr2keys[addr] = generate_key()
    pk = addr2keys[addr].public_key.format(True)
    # send the address and the corresonding public key to the contract
    tx_hash = darkPool.functions.register_client(addr, pk).transact()
    tx_hashes.append(tx_hash)
# wait for all transactions to go through
for i in range(len(tx_hashes)):
    tx_receipt = w3.eth.waitForTransactionReceipt(tx_hashes[i])
    print("Client", i+1, "registered with address:", w3.eth.accounts[i+1])
'''

'''
# transfer funds back from clients to operator
nonce = w3.eth.get_transaction_count(opAdd)
tx_hashes = []
for i in range(client_num):
    addr = clAdd[i]
    key = clKey[i]
    tx = {
        'chainId': w3.eth.chainId,
        'from': addr,
        'to': opAdd,
        'value': web3.eth.get_balance(addr),
        'nonce': nonce+i,
        'gas': 6721975,
        'gasPrice': w3.toWei(1, 'gwei')
    }
    cost = web3.eth.estimate_gas(tx)
    # transfer funds to client
    # sign transaction
    sign_tx = w3.eth.account.sign_transaction(
        {
            'chainId': w3.eth.chainId,
            'from': addr,
            'to': opAdd,
            'value': web3.eth.get_balance(addr) - cost,
            'nonce': nonce+i,
            'gas': 6721975,
            'gasPrice': w3.toWei(1, 'gwei')
        },
        opKey
    )
    # send the transaction
    tx_hash = w3.eth.sendRawTransaction(sign_tx.rawTransaction)
    tx_hashes.append(tx_hash)
# wait for transaction receipt
for i in range(client_num):
    tx_receipt = w3.eth.waitForTransactionReceipt(tx_hashes[i], timeout=3000)
    if verbose:
        print("Client {} returned balance.".format(i))
'''
