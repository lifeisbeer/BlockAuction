from web3 import Web3, HTTPProvider

start = 12388956
end = 12389865
#contract_address = '0xC7fcE7b6048B2Fce3D8617cbBD5f86562Bf430C1' #10
#contract_address = '0xfcCBAC67eFc05D0f7Af60eABE3a8A305Cb90e203' #100
contract_address = '0x0af2Ab50df46c1BDFCb0b165abf9e774751dE2F6' #1000

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

count = 0

for b in range(start, end+1):
    block = w3.eth.get_block(b, True)
    for tx in block.transactions:
        if tx.to == contract_address:
            count += 1

print(count)
