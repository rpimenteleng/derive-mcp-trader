# Generate a random Ethereum keypair for use as a Derive.xyz session key.
from eth_account import Account

acct = Account.create()
print(f"Private Key: {acct.key.hex()}")
print(f"Address:     {acct.address}")
