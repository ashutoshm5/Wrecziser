import threading
import time
import requests
import uvicorn
from main import app
from config import SERVER_HOST, SERVER_PORT

def start_server():
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, log_level="warning")

def run_integration_tests():
    print("=" * 60)
    print("STARTING TEST SERVER")
    print("=" * 60)
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    base_url = f"http://{SERVER_HOST}:{SERVER_PORT}"
    
    # Wait for server to boot
    for _ in range(15):
        try:
            res = requests.get(f"{base_url}/health", timeout=1.0)
            if res.status_code == 200:
                print("Server online at", base_url)
                break
        except Exception:
            time.sleep(0.5)
    else:
        print("[FAIL] Server failed to start within timeout.")
        return

    print("\n" + "=" * 60)
    print("TEST 1: Health Check Endpoint (GET /health)")
    print("=" * 60)
    h_res = requests.get(f"{base_url}/health")
    print("Status Code:", h_res.status_code)
    h_data = h_res.json()
    print("Health Data:", h_data)
    assert h_res.status_code == 200
    assert h_data["ollama_connected"] is True
    assert h_data["model_available"] is True
    print("[PASS] Health endpoint verified.")

    print("\n" + "=" * 60)
    print("TEST 2: Ingestion Endpoint (POST /api/summary)")
    print("=" * 60)
    ingest_payload = {"title": "Test Sync", "url": "https://example.com", "summary": "Sample sync."}
    ingest_res = requests.post(f"{base_url}/api/summary", json=ingest_payload)
    print("Status Code:", ingest_res.status_code)
    print("Response:", ingest_res.json())
    assert ingest_res.status_code == 200
    print("[PASS] Ingestion endpoint verified.")

    print("\n" + "=" * 60)
    print("TEST 3: Validation Error Handling (POST /summarize with empty/short text)")
    print("=" * 60)
    err_res = requests.post(f"{base_url}/summarize", json={"title": "Empty", "content": "Tiny"})
    print("Status Code (Expect 422 or 400):", err_res.status_code)
    assert err_res.status_code in [400, 422]
    print("[PASS] Validation error properly handled.")

    print("\n" + "=" * 60)
    print("TEST 4: Live Summarization (POST /summarize)")
    print("=" * 60)
    payload = {
        "title": "Quantum Resistance Update 2026",
        "url": "https://tech-news.example/articles/quantum-2026",
        "content": (
            "Researchers at the Berlin Cyber Institute have completed a 6-month evaluation of "
            "ML-KEM algorithms. Their findings demonstrate a 99.4% resistance to side-channel "
            "attacks under extreme thermal conditions. Deployment across European financial "
            "networks is slated to commence by November 2026."
        )
    }

    t0 = time.time()
    s_res = requests.post(f"{base_url}/summarize", json=payload, timeout=60.0)
    duration = time.time() - t0
    print(f"Status Code: {s_res.status_code} in {duration:.2f}s")
    assert s_res.status_code == 200
    s_data = s_res.json()
    print("\nSummary Title:", s_data.get("title"))
    print("Summary Text:", s_data.get("summary"))
    print("Key Points:", s_data.get("key_points"))
    print("Important Facts:", s_data.get("important_facts"))

    assert len(s_data.get("key_points", [])) >= 1
    assert "99.4" in (s_data.get("summary", "") + str(s_data.get("important_facts", "")))
    print("[PASS] Live summarization API test successful!")
    print("\nAll integration tests PASSED!")

if __name__ == "__main__":
    run_integration_tests()
