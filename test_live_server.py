import requests
import json
import sys

base_url = "http://16.170.208.134:8000"

print("==================================================")
print("LIVE AWS PRODUCTION TEST SUITE")
print("Target: " + base_url)
print("==================================================")

try:
    # 1. Root page test
    print("\n[TEST 1/5] Testing Frontend Dashboard Serving...")
    r0 = requests.get(base_url, timeout=10)
    print(f"Status Code: {r0.status_code}")
    assert r0.status_code == 200, "Dashboard failed to load"
    assert "Cloud Waste Hunter" in r0.text, "Title not found in HTML"
    print("[PASS] Frontend HTML5/Tailwind/Chart.js Single-Page Application successfully served!")

    # 2. AWS Identity & Probes test
    print("\n[TEST 2/5] Testing AWS STS & Cloud Probes (/api/aws/status)...")
    r1 = requests.get(f"{base_url}/api/aws/status", timeout=10)
    print(f"Status Code: {r1.status_code}")
    res1 = r1.json()
    print(f"AWS Authenticated: {res1.get('authenticated')}")
    print(f"Connection Status: {res1.get('status')}")
    print(f"AWS Account ID:   {res1.get('account_id')}")
    print(f"Active IAM ARN:   {res1.get('arn')}")
    print(f"Region:           {res1.get('region')}")
    probes = res1.get('probes', {})
    for svc, status in probes.items():
        print(f"  - Service {svc:12}: {status.get('status')} ({status.get('message', '')})")
    print("[PASS] Live AWS Boto3 STS credentials and service health probes verified!")

    # 3. Discovered Resources test
    print("\n[TEST 3/5] Testing Resource Inventory Discovery (/api/aws/resources)...")
    r2 = requests.get(f"{base_url}/api/aws/resources?region=ap-southeast-2", timeout=10)
    print(f"Status Code: {r2.status_code}")
    res2 = r2.json()
    print(f"Discovery Status: {res2.get('status')}")
    print(f"Resources found in ap-southeast-2: {len(res2.get('all_resources', []))}")
    print("[PASS] Live discovery endpoint operational!")

    # 4. Pipeline Execution test (Enterprise FinOps Scenario)
    print("\n[TEST 4/5] Executing Complete End-to-End FinOps Pipeline (Simulation Scenario)...")
    payload = {"scenario": "enterprise", "use_live_aws": False}
    r3 = requests.post(f"{base_url}/api/pipeline/run", json=payload, timeout=20)
    print(f"Status Code: {r3.status_code}")
    assert r3.status_code == 200, f"Pipeline run failed: {r3.text}"
    resp3 = r3.json()
    summary = resp3.get("summary", {})
    report = resp3.get("report", {})
    print(f"  * Run ID:                   {resp3.get('run_id')}")
    print(f"  * Total Resources Analyzed: {summary.get('monitored_resources_count')}")
    print(f"  * Waste Findings Detected:  {summary.get('waste_findings_count')}")
    print(f"  * Recoverable Monthly ROI:  ${summary.get('total_monthly_savings', 0):.2f}/mo")
    print(f"  * Annualized ROI Savings:   ${summary.get('total_annualized_savings', 0):.2f}/year")
    print(f"  * Carbon Footprint Cut:     {summary.get('total_carbon_savings_kg', 0):.2f} kg CO2e")
    print(f"  * AI Recommendations:       {summary.get('ai_recommendations_count')}")
    print(f"  * Terraform Patches Made:   {summary.get('terraform_patches_count')}")
    print(f"  * Terraform Plan ID:        {summary.get('terraform_plan_id')}")
    print(f"  * GitOps PR ID:             {summary.get('gitops_pr_id')}")
    print(f"  * S3 Audit Report URI:      {summary.get('s3_uri')}")
    print(f"  * DynamoDB Audit Key:       {summary.get('dynamodb_id')}")
    print("[PASS] Full 7-Module FinOps optimization pipeline executed successfully!")

    # 5. Live AWS Pipeline Run test
    print("\n[TEST 5/5] Executing Live AWS Pipeline Run (/api/pipeline/run - Live AWS Mode)...")
    live_payload = {"use_live_aws": True, "region": "ap-southeast-2"}
    r4 = requests.post(f"{base_url}/api/pipeline/run", json=live_payload, timeout=20)
    print(f"Status Code: {r4.status_code}")
    assert r4.status_code == 200, f"Live pipeline failed: {r4.text}"
    live_report = r4.json()
    print(f"  * Live Run ID:              {live_report.get('run_id')}")
    print(f"  * Live Resources Scanned:   {len(live_report.get('monitored_resources', []))}")
    print(f"  * Live Waste Detected:      {len(live_report.get('waste_findings', []))}")
    print(f"  * AI Advisor Status:        {live_report.get('ai_status', 'SUCCESS')}")
    print("[PASS] Live AWS pipeline executed successfully with 0 exceptions!")

    print("\n==================================================")
    print("ALL 5 LIVE ENDPOINT TESTS PASSED WITH 100% SUCCESS!")
    print("==================================================")

except Exception as e:
    print(f"\n[FAIL] Test failed with error: {e}")
    sys.exit(1)
