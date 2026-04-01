import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

client = MongoClient(os.getenv("DB_URI"))
db = client[os.getenv("MONGODB_DATABASE")]

def find_sku(collection, name_pattern):
    item = collection.find_one({"name": {"$regex": name_pattern, "$options": "i"}}, {"sku": 1, "name": 1})
    return item

cpu = find_sku(db.cpus, "Ryzen 7 5700X3D")
gpu = find_sku(db.gpus, "RTX 4070 Super")

print("-" * 30)
if cpu:
    print(f"CPU: {cpu['name']}")
    print(f"ID (SKU): {cpu['sku']}")
else:
    print("CPU 'Ryzen 7 5700X3D' não encontrada.")

print("-" * 30)
if gpu:
    print(f"GPU: {gpu['name']}")
    print(f"ID (SKU): {gpu['sku']}")
else:
    print("GPU 'RTX 4070 Super' não encontrada.")
print("-" * 30)
client.close()
