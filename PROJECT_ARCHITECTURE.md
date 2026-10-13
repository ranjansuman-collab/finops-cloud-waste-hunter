# PROJECT ARCHITECTURE & AWS INTEGRATION MIGRATION PLAN
**FinOps Cloud Waste Hunter & Auto-Remediator**
*ISWE309L Cloud Computing Course Project*

---

## 1. Existing Architecture Overview

The existing application is structured as a 7-module automated FinOps lifecycle platform with a FastAPI backend, a responsive web dashboard (Tailwind CSS + Chart.js), and a PyInstaller Windows packaging configuration.

```
finops-cloud-waste-hunter/
├── app/
│   ├── server.py              # FastAPI application & REST API endpoints
│   └── static/                # Frontend UI assets (index.html, app.js, styles.css)
├── core/
│   ├── models.py              # Pydantic domain models for telemetry, waste, cost, AI, TF, GitOps
│   ├── engine.py              # FinOpsEngine orchestrator executing modules 1 through 7
│   ├── module1_monitoring.py  # Resource telemetry collection & inventory polling
│   ├── module2_waste_detection.py # Heuristic waste rule matching (compute, storage, serverless, network)
│   ├── module3_cost_estimation.py # Cost delta & carbon footprint calculator
│   ├── module4_ai_advisor.py  # Amazon Bedrock Nova Lite integration & rationale generator
│   ├── module5_storage.py     # Local JSON and S3/DynamoDB report persistence
│   ├── module6_terraform.py   # HCL patch generation & unified diff creator
│   └── module7_gitops.py      # GitOps pull request workflow & review simulator
├── data/
│   └── scenarios.py           # Predefined demo scenarios (enterprise, startup, clean)
├── sample_infrastructure/
│   └── main.tf                # Reference Terraform infrastructure file for patching
├── storage/                   # Local file storage simulating S3 and DynamoDB audit records
├── tests/
│   └── test_modules.py        # 8 unit tests covering engine and modules 1-7
├── run_app.py                 # Application launcher (free port finder, browser opener, uvicorn)
├── FinOps-Waste-Hunter.spec   # PyInstaller build specification
├── build_exe.bat              # Batch script to produce Windows standalone executable
└── requirements.txt           # Python dependencies (fastapi, uvicorn, pydantic, boto3, requests, PyGithub, pyinstaller)
```

---

## 2. Where Simulated AWS Data is Produced

Currently, simulated data is injected at multiple points in the codebase:

1. **`data/scenarios.py`**:
   - Contains static dictionaries for `enterprise`, `startup`, and `clean` scenarios.
   - Hardcodes synthetic resource identifiers (e.g., `i-09f84a8123bc45e01`, `vol-0e4b8893d5678a123`), simulated hardware specs, and mock metric properties (`cpu_utilization_avg: 3.4`, `days_unattached: 45`, `invocations_30d: 0`, `bytes_processed_30d_mb: 4.2`).
2. **`core/module1_monitoring.py`**:
   - `fetch_resources()` falls back to `_fetch_simulated_resources(scenario_id)` which reads from `data/scenarios.py`.
   - `_generate_timeseries()` uses `random.seed()` to generate fake 7-day sparkline charts.
   - `_fetch_live_aws_resources()` only looks for explicit `AWS_ACCESS_KEY_ID` environment variables (ignoring standard AWS credential profiles/SSO), hardcodes `metrics={"cpu_utilization_avg": 5.0}` instead of querying CloudWatch, and falls back to simulated enterprise data on any exception or empty resource list.
3. **`core/module3_cost_estimation.py`**:
   - Uses hardcoded static lookup tables (`EC2_HOURLY_PRICING`, `EBS_GB_MONTHLY_PRICING`, `EIP_HOURLY_PENALTY`, `NAT_GATEWAY_HOURLY`) rather than live AWS Cost Explorer or AWS Price List queries.
4. **`core/module4_ai_advisor.py`**:
   - Falls back to `_generate_intelligent_recommendation()` with static template text strings whenever live Bedrock invocation fails or credentials are not supplied via environment variables.
5. **`core/module6_terraform.py`**:
   - Performs regex text substitution directly on `sample_infrastructure/main.tf` in memory instead of creating a controlled Terraform workspace or executing real `terraform fmt`, `terraform validate`, and `terraform plan`.
6. **`core/module7_gitops.py`**:
   - Maintains an in-memory dictionary of simulated pull requests with hardcoded pass/pending checks and mock audit log entries without invoking git CLI commands.

---

## 3. Target System Architecture & Migration Plan

The system will be transitioned from synthetic simulations to a real, live AWS-connected application while strictly preserving existing UI capabilities, core abstractions, and safety guardrails.

### Target Workflow:
```
Windows EXE / Python App
  ↓
AWS Authentication (Standard AWS Credential Chain: ~/.aws/credentials, ~/.aws/config, Env Vars, IAM Role)
  ↓
AWS Account + Region Verification (STS get_caller_identity, default: ap-southeast-2, configurable)
  ↓
Real AWS Resource Discovery (EC2, EBS, Elastic IP, Lambda, S3 via Boto3 with pagination)
  ↓
Real CloudWatch Metrics (EC2 CPUUtilization over 7/14/30 configurable days via GetMetricData/Statistics)
  ↓
Waste Detection (Evidence-grounded: unattached EBS, unused EIP, idle EC2, dormant Lambda)
  ↓
AWS Cost Explorer Spend + Estimated Resource Savings (actual cost distinguished from estimated savings)
  ↓
Amazon Bedrock Real Analysis (Analysis & recommendation only; real errors surfaced if unavailable)
  ↓
Terraform Change Generation in Controlled Workspace (fmt -> validate -> plan -> capture plan file)
  ↓
Explicit Approval Guardrail (UI displays plan; apply blocked until user clicks [Approve & Apply])
  ↓
Terraform Apply with Saved Plan (Targeted apply of reviewed plan only)
  ↓
Verify AWS Changes (Re-query AWS to verify resource status)
  ↓
Git Commit & Audit History (git diff -> git add -> git commit with meaningful message; no secrets)
```

---

## 4. Checkpoint Implementation Breakdown

### Checkpoint 1: Inspection & Architecture Documentation (Current)
- Completed repository inspection and identified simulation origins.
- Created `PROJECT_ARCHITECTURE.md`.

### Checkpoint 2: Real AWS Connection Layer
- Implement `core/aws/connection.py` using standard Boto3 session credential chain.
- Default region: `ap-southeast-2` (configurable).
- Expose `GET /api/aws/status` with `sts.get_caller_identity()` retrieving Account ID, ARN, and Region.
- Probe read access for EC2, CloudWatch, S3, Cost Explorer, and Bedrock.
- Return explicit status states: `CONNECTED`, `NO_PERMISSION`, `ACCOUNT_VERIFICATION_REQUIRED`, `NOT_AVAILABLE`, `ERROR`.

### Checkpoint 3: Real AWS Resource Discovery
- Implement `core/aws/discovery.py` handling EC2, EBS, Elastic IP, Lambda, and S3.
- Handle API pagination tokens cleanly.
- Normalize resources into `CloudResource` schema.
- Return empty arrays when zero resources exist (no fake injection).
- Expose `GET /api/aws/resources` and sub-endpoints.

### Checkpoint 4: Real CloudWatch Telemetry, Cost Explorer & Waste Engine
- Implement `core/aws/cloudwatch.py` fetching real `CPUUtilization` metrics via `GetMetricData` / `GetMetricStatistics`.
- Configurable periods: 7, 14, and 30 days.
- Implement `core/aws/costs.py` querying AWS Cost Explorer where available; distinguish `ACTUAL AWS COST` from `ESTIMATED RESOURCE COST`.
- Update `WasteDetectionModule` to operate on real telemetry evidence.

### Checkpoint 5: Real Amazon Bedrock Integration
- Implement `core/aws/bedrock.py` using Boto3 `bedrock-runtime` (`invoke_model`).
- Configurable model (defaulting to Amazon Nova Lite / Claude / Titan).
- Return structured problem explanation, evidence, recommendation, risk rating, expected savings, and Terraform change snippet.
- If Bedrock is unavailable due to account verification or IAM permissions, report exact AWS error (no fake AI strings).

### Checkpoint 6: Terraform Workspace, Validate & Plan
- Create an isolated, controlled Terraform execution workspace.
- Generate valid HCL patches.
- Run `terraform fmt`, `terraform validate`, and `terraform plan -out=<planfile>`.
- Capture plan output and expose via API for UI inspection.

### Checkpoint 7: Safety Approval Protection & Apply
- Hard safety requirement: `terraform apply` CANNOT be called automatically.
- Provide `POST /api/terraform/apply` requiring explicit confirmation token matching the saved plan.
- Execute `terraform apply <saved-plan>` and verify the AWS change post-apply.
- Record verification status in audit history.

### Checkpoint 8: Git Integration, History & UI Controls
- Perform local Git commit (`git diff`, `git add`, `git commit`) for the Terraform change.
- Never commit secrets, tokens, or credentials.
- Add AWS Connection & Scan panel in UI with region selection (`ap-southeast-2`), Bedrock analysis card, and Plan Approval modal.

### Checkpoint 9: Comprehensive Test Suite
- Write unit and integration tests with mocked AWS responses (`unittest.mock`) to prevent unintended AWS modifications.
- Test connection checks, resource discovery, CloudWatch metric retrieval, waste detection, Bedrock handling, approval protection, and Terraform plan generation.

### Checkpoint 10: Executable Rebuild & Packaging Verification
- Update `FinOps-Waste-Hunter.spec` to bundle all new modules and templates.
- Ensure executable relies strictly on the user's standard AWS credential chain without embedding credentials.
- Test executable build via `build_exe.bat`.
