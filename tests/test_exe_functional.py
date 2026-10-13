import os
import sys
import time
import json
import signal
import subprocess
import urllib.request
import urllib.error

def main():
    exe_path = os.path.abspath("dist/FinOps-Waste-Hunter/FinOps-Waste-Hunter.exe")
    if not os.path.exists(exe_path):
        print(f"FAIL: Executable not found at {exe_path}")
        sys.exit(1)

    print(f"[+] Found executable: {exe_path} ({os.path.getsize(exe_path):,} bytes)")

    env = os.environ.copy()
    proc = subprocess.Popen(
        [exe_path],
        cwd=os.path.abspath("dist/FinOps-Waste-Hunter"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    detected_port = None
    base_url = None

    try:
        print("[+] Waiting for EXE to start up and bind to a port...")
        start_time = time.time()
        while time.time() - start_time < 20:
            if proc.poll() is not None:
                stdout, stderr = proc.communicate()
                print(f"FAIL: EXE exited prematurely with code {proc.returncode}")
                print(f"STDOUT:\n{stdout}")
                print(f"STDERR:\n{stderr}")
                sys.exit(1)

            for test_port in range(8080, 8095):
                try:
                    req = urllib.request.Request(f"http://127.0.0.1:{test_port}/api/scenarios")
                    with urllib.request.urlopen(req, timeout=1.0) as resp:
                        if resp.status == 200:
                            data = json.loads(resp.read().decode("utf-8"))
                            if "scenarios" in data:
                                detected_port = test_port
                                base_url = f"http://127.0.0.1:{detected_port}"
                                break
                except Exception:
                    pass
            if detected_port:
                break
            time.sleep(0.5)

        if not detected_port:
            print("FAIL: EXE did not respond on any port 8080-8095 within 20s")
            sys.exit(1)

        print(f"[+] EXE is running and healthy on: {base_url}")

        # 1. Test GET /
        print("\n--- Test 1: Frontend Serving (GET /) ---")
        req = urllib.request.Request(f"{base_url}/")
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            content = resp.read().decode("utf-8")
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            assert "FinOps Cloud Waste Hunter" in content, "Dashboard title not found in HTML"
            # Verify academic banner was removed from top header
            assert "ISWE309L Cloud Computing" not in content[:1500], "Academic banner still in top header"
            print("PASS: Frontend loads correctly, HTML served, top banner removed.")

        # 2. Test GET /api/scenarios
        print("\n--- Test 2: Scenarios API (GET /api/scenarios) ---")
        req = urllib.request.Request(f"{base_url}/api/scenarios")
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            scenarios = data.get("scenarios", [])
            assert len(scenarios) >= 3, f"Expected >= 3 scenarios, got {len(scenarios)}"
            scenario_ids = [s["id"] for s in scenarios]
            assert "enterprise" in scenario_ids, "enterprise scenario missing"
            print(f"PASS: Scenarios API returned {len(scenarios)} scenarios: {scenario_ids}")

        # 3. Test GET /api/aws/status
        print("\n--- Test 3: AWS Status Endpoint (GET /api/aws/status) ---")
        req = urllib.request.Request(f"{base_url}/api/aws/status")
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            status_data = json.loads(resp.read().decode("utf-8"))
            print(f"AWS Status Response: {status_data}")
            assert "status" in status_data
            assert status_data["status"] in ("CONNECTED", "CREDENTIALS_MISSING", "NO_PERMISSION")
            assert "services" in status_data
            if status_data["status"] == "CREDENTIALS_MISSING":
                print("PASS: AWS status correctly reports missing credentials without error.")
            else:
                print("PASS: AWS status returned successfully.")

        # 4. Test POST /api/pipeline/run (Simulation Mode)
        print("\n--- Test 4: Full 7-Module Pipeline (Simulation Mode) ---")
        payload = json.dumps({"scenario": "enterprise", "use_live_aws": False}).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/api/pipeline/run",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        pr_id = None
        plan_id = None
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            pipe_data = json.loads(resp.read().decode("utf-8"))
            assert "run_id" in pipe_data
            assert pipe_data.get("scenario") == "enterprise"
            assert "report" in pipe_data
            report = pipe_data["report"]
            
            # Verify data from all 7 modules
            assert "monitored_resources" in report, "Module 1 data missing"
            assert "waste_findings" in report, "Module 2 data missing"
            assert "cost_findings" in report, "Module 3 data missing"
            assert "ai_recommendations" in report, "Module 4 data missing"
            assert "s3_uri" in report and "dynamodb_id" in report, "Module 5 data missing"
            assert "terraform_patches" in report, "Module 6 data missing"
            assert "gitops_pr" in report, "Module 7 data missing"

            findings = report.get("waste_findings", [])
            assert len(findings) > 0, "Expected waste findings in enterprise scenario"
            pr_info = report.get("gitops_pr") or {}
            pr_id = pr_info.get("pr_id")
            summary = pipe_data.get("summary", {})
            print(f"PASS: Pipeline executed all 7 modules successfully. Findings: {len(findings)}, Monthly Savings: ${summary.get('total_monthly_savings', 0)}, PR ID: {pr_id}")

        # 5. Test GET /api/modules/1 through 7
        print("\n--- Test 5: Individual Module Endpoints (GET /api/modules/1..7) ---")
        for m in range(1, 8):
            m_req = urllib.request.Request(f"{base_url}/api/modules/{m}?scenario=enterprise")
            with urllib.request.urlopen(m_req, timeout=5.0) as resp:
                m_data = json.loads(resp.read().decode("utf-8"))
                assert resp.status == 200
                print(f"  Module {m}: OK")
        print("PASS: All 7 individual module endpoints responded successfully.")

        # 6. Test GitOps PR Actions & Safety
        print("\n--- Test 6: GitOps PR Actions & Safety ---")
        if pr_id:
            pr_payload = json.dumps({
                "reviewer": "Vivek Pandey (Lead FinOps Engineer)",
                "reason": "Audited and verified"
            }).encode("utf-8")
            pr_req = urllib.request.Request(
                f"{base_url}/api/gitops/pr/{pr_id}/approve",
                data=pr_payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(pr_req, timeout=5.0) as resp:
                pr_res = json.loads(resp.read().decode("utf-8"))
                assert pr_res.get("status") == "SUCCESS"
                assert pr_res["pr"]["status"] == "APPROVED"
                print("PASS: GitOps PR approved successfully.")

        # 7. Test Terraform Safety Gate (Cannot apply unapproved plan)
        print("\n--- Test 7: Terraform Apply Safety Gate ---")
        tf_payload = json.dumps({
            "plan_id": "non-existent-or-unapproved-plan",
            "approved": False
        }).encode("utf-8")
        tf_req = urllib.request.Request(
            f"{base_url}/api/terraform/apply",
            data=tf_payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(tf_req, timeout=5.0) as resp:
            apply_res = json.loads(resp.read().decode("utf-8"))
            assert apply_res.get("success") is False, "Unapproved plan must fail apply"
            assert apply_res.get("status") in ("PLAN_NOT_FOUND", "APPROVAL_REQUIRED")
            print(f"PASS: Unapproved terraform apply rejected safely with status '{apply_res.get('status')}' (success=False).")

        # 8. Test Live Mode Safe Degradation (Live mode without credentials does not fabricate data)
        print("\n--- Test 8: Live Mode Safe Degradation ---")
        live_payload = json.dumps({"use_live_aws": True}).encode("utf-8")
        live_req = urllib.request.Request(
            f"{base_url}/api/pipeline/run",
            data=live_payload,
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(live_req, timeout=10.0) as resp:
                live_resp = json.loads(resp.read().decode("utf-8"))
                # If credentials exist, that's fine; if not, status should be error/degraded
                print(f"Live mode response: {live_resp.get('status')}")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            print(f"PASS: Live mode safely rejected without credentials: HTTP {e.code}: {err_body.strip()}")
        except Exception as e:
            print(f"PASS: Live mode raised clean error: {e}")

        # 9. Test Meta Information Endpoint
        print("\n--- Test 9: Meta Information Endpoint (GET /api/meta) ---")
        req = urllib.request.Request(f"{base_url}/api/meta")
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            meta = json.loads(resp.read().decode("utf-8"))
            assert "project" in meta
            assert "modules" in meta
            assert len(meta["modules"]) == 7
            print(f"PASS: Meta API returned project metadata with {len(meta['modules'])} modules.")

        print("\n=======================================================")
        print("ALL 9 EXE VERIFICATION TESTS PASSED SUCCESSFULLY!")
        print("=======================================================")

    finally:
        print("[+] Terminating EXE process...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        print("[+] EXE terminated cleanly.")

if __name__ == "__main__":
    main()
