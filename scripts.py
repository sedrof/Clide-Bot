import base58

# Paste the keypair array from your wallet.json file here
keypair_array = [
  119, 112, 186, 131, 227, 181, 221, 107, 54, 45, 49, 157, 178, 200, 52, 171,
  202, 121, 246, 191, 30, 241, 145, 38, 224, 227, 199, 218, 99, 202, 191, 215,
  57, 28, 55, 37, 86, 54, 90, 216, 82, 200, 10, 243, 120, 138, 184, 11, 33, 164,
  46, 97, 204, 125, 214, 140, 114, 220, 163, 41, 188, 168, 97, 147
]

# Convert the array of numbers into bytes
private_key_bytes = bytes(keypair_array)

# Encode the bytes into a Base58 string
base58_private_key = base58.b58encode(private_key_bytes).decode('utf-8')

print("Your Base58 Private Key is:")
print(base58_private_key)