import httpx
import time
import json

URL = "http://127.0.0.1:8000/matches"

# IDs DEFINITIVOS (SKUs Literais do seu banco)
payload = {
    "use_case": "aaa",
    "resolution": "1440p",
    "owned_cpu_sku": "AMD Ryzen 7 5700X3D",
    "owned_gpu_sku": "geforce-rtx-4070-super",
    "include_review_consensus": True,
    "review_consensus_limit": 1,
    "refresh": True
}

print(f"Enviando request para: {URL}")
start_time = time.time()

try:
    with httpx.Client(timeout=120.0) as client:
        response = client.post(URL, json=payload)
    
    elapsed = time.time() - start_time
    print(f"Status: {response.status_code}")
    print(f"Tempo total: {elapsed:.2f} segundos")
    
    if response.status_code == 200:
        data = response.json()
        items = data.get("items", [])
        if items:
            match = items[0]
            print("-" * 30)
            print(f"Match: {match['cpu']['name']} + {match['gpu']['name']}")
            print(f"Score: {match['score']}")
            print(f"Consensus Status: {match['review_consensus_status']}")
            
            consensus = match.get("review_consensus")
            if consensus:
                print(f"FPS Médio (Geral): {consensus.get('average_explicit_fps')}")
                print("Jogos Testados:")
                for game in consensus.get("tested_games", []):
                    print(f" - {game['name']}: {game['avg_fps']} FPS @ {game['resolution']}")
            else:
                print("Aviso: Review Consensus veio vazio (provavelmente status 'pending').")
        else:
            print("Nenhum match retornado.")
    else:
        print(f"Erro: {response.text}")

except Exception as e:
    print(f"Erro de conexão: {e}")
