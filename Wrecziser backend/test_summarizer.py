import time
from ollama_client import OllamaClient
from summarizer import WebpageSummarizer
from schemas import SummarizeRequest

def run_tests():
    print("=" * 60)
    print("STEP 1: Testing Ollama Health & Model Availability")
    print("=" * 60)
    client = OllamaClient()
    health = client.check_health()
    print("Ollama Connected:   ", health["connected"])
    print("Model Available:    ", health["model_available"])
    print("Available Models:   ", health["available_models"])

    if not health["connected"] or not health["model_available"]:
        print("[FAIL] Ollama or target model not ready. Aborting test.")
        return

    print("\n" + "=" * 60)
    print("STEP 2: Testing Factuality & Summarization with Qwen3")
    print("=" * 60)

    sample_text = (
        "On September 15, 2026, DeepOrbit Technologies unveiled their new quantum-resistant "
        "cryptographic chipset, the Kyber-900. Operating at an ultra-low power consumption of "
        "1.8 Watts, the chipset achieved a verified throughput of 42.5 Gbps in independent "
        "benchmarks conducted by the Munich Cryptography Lab. Dr. Elena Rostova, lead architect, "
        "announced that commercial mass production is slated for Q1 2027 with an initial unit "
        "pricing of $145. The hardware implements post-quantum lattice algorithms compliant with "
        "NIST FIPS 203 standards."
    )

    req = SummarizeRequest(
        title="DeepOrbit Unveils Kyber-900 Quantum Cryptographic Chipset",
        url="https://deeporbit.example/news/kyber-900",
        content=sample_text
    )

    summarizer = WebpageSummarizer(client=client)

    start_time = time.time()
    result = summarizer.summarize(req)
    elapsed = time.time() - start_time

    print(f"\nCompleted in {elapsed:.2f} seconds!")
    print("\n[RESULT TITLE]:", result.title)
    print("\n[EXECUTIVE SUMMARY]:\n", result.summary)
    print("\n[KEY POINTS]:")
    for kp in result.key_points:
        print(f"  • {kp}")
    print("\n[IMPORTANT FACTS]:")
    for fact in result.important_facts:
        print(f"  • {fact}")

    print("\n" + "=" * 60)
    print("VERIFICATION CHECKLIST:")
    print("=" * 60)
    checks = {
        "Contains 'Kyber-900'": "Kyber-900" in (result.summary + " ".join(result.key_points) + " ".join(result.important_facts)),
        "Contains '1.8 Watts' or '1.8 W'": "1.8" in (result.summary + " ".join(result.important_facts) + " ".join(result.key_points)),
        "Contains '42.5 Gbps'": "42.5" in (result.summary + " ".join(result.important_facts) + " ".join(result.key_points)),
        "Contains 'Elena Rostova'": "Elena" in (result.summary + " ".join(result.important_facts) + " ".join(result.key_points)),
        "Contains '2026' or '2027'": any(y in (result.summary + " ".join(result.important_facts) + " ".join(result.key_points)) for y in ["2026", "2027"]),
        "Valid JSON structure parsed": bool(result.summary and result.key_points)
    }

    all_passed = True
    for check_name, passed in checks.items():
        status_str = "[PASS]" if passed else "[FAIL]"
        print(f"{status_str} {check_name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\nAll factuality & structure checks PASSED!")
    else:
        print("\nSome checks failed; review prompt or model parameters.")

if __name__ == "__main__":
    run_tests()
