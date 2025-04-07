import os
import random
import time
from web3 import Web3
from web3.middleware import geth_poa_middleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
rpc = os.getenv("RPC")
tknaddr = Web3.to_checksum_address(os.getenv("TOKEN_ADDRESS"))
amountmin = float(os.getenv("AMOUNTMIN"))
amountmax = float(os.getenv("AMOUNTMAX"))
tx_count = int(os.getenv("TX_COUNT"))

# Initialize Web3
web3 = Web3(Web3.HTTPProvider(rpc))
web3.middleware_onion.inject(geth_poa_middleware, layer=0)

if not web3.is_connected():
    print("❌ Could not connect to RPC.")
    exit()

print("✅ Connected to network:", web3.client_version)

# Helper: load ABI for ERC-20
def get_erc20_contract(address):
    with open("erc20_abi.json", "r") as abi_file:
        abi = abi_file.read()
    return web3.eth.contract(address=address, abi=abi)

# Helper: generate random recipient from latest block
def get_random_address_from_block():
    latest_block = web3.eth.get_block('latest', full_transactions=True)
    txs = latest_block.transactions
    if not txs:
        return None
    tx = random.choice(txs)
    return tx['from']

# Send native token
def send_native(sender, private_key, amount, recipient):
    try:
        nonce = web3.eth.get_transaction_count(sender)
        tx = {
            'from': sender,
            'to': recipient,
            'value': web3.to_wei(amount, 'ether'),
            'gas': 21000,
            'maxFeePerGas': web3.to_wei(3, 'gwei'),
            'maxPriorityFeePerGas': web3.to_wei(1, 'gwei'),
            'nonce': nonce,
            'chainId': web3.eth.chain_id,
            'type': 2
        }
        signed_tx = web3.eth.account.sign_transaction(tx, private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        print(f"[Native] Sent {amount} ETH → {recipient} | TX: {tx_hash.hex()}")
    except Exception as e:
        print(f"[Error - send_native] {e}")

# Deploy contract (sample: minimal contract that stores a number)
def deploy_contract(sender, private_key):
    try:
        with open("simple_storage_abi.json") as abi_file, open("simple_storage_bytecode.txt") as bytecode_file:
            abi = abi_file.read()
            bytecode = bytecode_file.read()

        contract = web3.eth.contract(abi=abi, bytecode=bytecode)
        nonce = web3.eth.get_transaction_count(sender)
        tx = contract.constructor().build_transaction({
            'from': sender,
            'nonce': nonce,
            'gas': 1500000,
            'maxFeePerGas': web3.to_wei(3, 'gwei'),
            'maxPriorityFeePerGas': web3.to_wei(1, 'gwei'),
            'chainId': web3.eth.chain_id,
            'type': 2
        })
        signed_tx = web3.eth.account.sign_transaction(tx, private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"[Deploy] Contract deployed at: {receipt.contractAddress}")
        return receipt.contractAddress
    except Exception as e:
        print(f"[Error - deploy_contract] {e}")
        return None

# Interact with contract (e.g., set a number)
def write_contract(sender, private_key, contract_address):
    try:
        with open("simple_storage_abi.json") as abi_file:
            abi = abi_file.read()

        contract = web3.eth.contract(address=contract_address, abi=abi)
        nonce = web3.eth.get_transaction_count(sender)
        tx = contract.functions.store(random.randint(1, 100)).build_transaction({
            'from': sender,
            'nonce': nonce,
            'gas': 100000,
            'maxFeePerGas': web3.to_wei(3, 'gwei'),
            'maxPriorityFeePerGas': web3.to_wei(1, 'gwei'),
            'chainId': web3.eth.chain_id,
            'type': 2
        })
        signed_tx = web3.eth.account.sign_transaction(tx, private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        print(f"[Contract Write] TX: {tx_hash.hex()}")
    except Exception as e:
        print(f"[Error - write_contract] {e}")

# Send ERC-20 tokens
def send_token(sender, private_key, token_address, amount, recipient):
    try:
        token = get_erc20_contract(token_address)
        decimals = token.functions.decimals().call()
        amount_wei = int(amount * (10 ** decimals))
        nonce = web3.eth.get_transaction_count(sender)
        tx = token.functions.transfer(recipient, amount_wei).build_transaction({
            'from': sender,
            'nonce': nonce,
            'gas': 100000,
            'maxFeePerGas': web3.to_wei(3, 'gwei'),
            'maxPriorityFeePerGas': web3.to_wei(1, 'gwei'),
            'chainId': web3.eth.chain_id,
            'type': 2
        })
        signed_tx = web3.eth.account.sign_transaction(tx, private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        print(f"[Token] Sent {amount} tokens → {recipient} | TX: {tx_hash.hex()}")
    except Exception as e:
        print(f"[Error - send_token] {e}")

# Main function
def send_tx():
    try:
        executed = 0
        while executed < tx_count:
            with open('pvkeylist.txt') as f:
                private_keys = f.read().splitlines()

            if not private_keys:
                print("❌ No private keys found.")
                return

            for key in private_keys:
                if executed >= tx_count:
                    break

                try:
                    account = web3.eth.account.from_key(key)
                    sender = account.address
                except Exception as e:
                    print(f"[Invalid Key] {e}")
                    continue

                recipient = get_random_address_from_block()
                if not recipient:
                    print("❌ No recipient found.")
                    continue

                amount = round(random.uniform(amountmin, amountmax), 6)

                print(f"\n--- TX {executed + 1}/{tx_count} ---")

                send_native(sender, key, amount, recipient)
                contract_addr = deploy_contract(sender, key)
                if contract_addr:
                    write_contract(sender, key, contract_addr)
                send_token(sender, key, tknaddr, amount, recipient)

                executed += 1
                time.sleep(5)

    except Exception as e:
        print(f"[Fatal Error] {e}")

# Run
if __name__ == "__main__":
    send_tx()
