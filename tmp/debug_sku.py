import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
client = MongoClient(os.getenv("DB_URI"))
db = client[os.getenv("MONGODB_DATABASE")]

gpu = db.gpus.find_one({"name": {"$regex": "RTX 4070 Super", "$options": "i"}})
if gpu:
    print(f"SKU_REPR: {repr(gpu['sku'])}")
    print(f"SKU_STR: {str(gpu['sku'])}")
else:
    print("GPU NOT FOUND")
client.close()
