from fastapi.testclient import TestClient
from server import app
import json

client = TestClient(app)

def test_api():
    print("=" * 60)
    print("      TEST API FASTAPI & SECURITY ENDPOINTS")
    print("=" * 60)

    # 1. Test root dashboard
    res = client.get("/")
    assert res.status_code == 200, f"Dashboard failed: {res.status_code}"
    print("1. [PASS] GET / (Dashboard HTML)")

    # 2. Test overview endpoint
    res = client.get("/api/overview")
    assert res.status_code == 200, f"Overview failed: {res.status_code}"
    data = res.json()
    assert "summary" in data and "trips" in data
    print("2. [PASS] GET /api/overview -> Summary:", data['summary'])

    # 3. Test hardware status
    res = client.get("/api/hardware/status")
    assert res.status_code == 200
    hw = res.json()
    print("3. [PASS] GET /api/hardware/status -> Device:", hw.get('device_name'), "| Cores:", hw.get('cpu_cores'))

    # 4. Test storage status
    res = client.get("/api/storage/status")
    assert res.status_code == 200
    st = res.json()
    print("4. [PASS] GET /api/storage/status -> Total GB:", st.get('total_gb'), "| Free GB:", st.get('free_gb'))

    # 5. Test engine status
    res = client.get("/api/engine/status")
    assert res.status_code == 200
    eng = res.json()
    print("5. [PASS] GET /api/engine/status -> Stream Status:", eng['telemetry']['stream_status'])

    # 6. Test simulate incident (recovered)
    res = client.post("/api/engine/simulate_incident?incident_type=recovered")
    assert res.status_code == 200
    print("6. [PASS] POST /api/engine/simulate_incident (recovered) ->", res.json()['message'])

    # 7. Test simulate incident (theft)
    res = client.post("/api/engine/simulate_incident?incident_type=theft")
    assert res.status_code == 200
    print("7. [PASS] POST /api/engine/simulate_incident (theft) ->", res.json()['message'])

    # 8. Test trips endpoint
    res = client.get("/api/trips")
    assert res.status_code == 200
    print("8. [PASS] GET /api/trips -> Total recorded trips:", len(res.json()))

    # 9. Test anomalies endpoint
    res = client.get("/api/anomalies")
    assert res.status_code == 200
    print("9. [PASS] GET /api/anomalies -> Total recorded anomalies:", len(res.json()))

    # 10. Test input validation / path traversal block on engine/start
    res = client.post("/api/engine/start", json={"source": "../../etc/passwd", "start_minute": 20})
    assert res.status_code == 400
    print("10. [PASS] Path Traversal Security Blocked -> Status 400 (Expected)")

    print("\n" + "=" * 60)
    print("      SEMUA 10/10 PENGUJIAN API BERHASIL 100%!")
    print("=" * 60)

if __name__ == "__main__":
    test_api()

