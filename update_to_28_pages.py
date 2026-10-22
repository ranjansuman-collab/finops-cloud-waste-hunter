"""
update_to_28_pages.py
Updates generate_full_project_report.py to use consolidated screenshot panels
and calibrated table sizes to land at exactly 27-29 pages.
"""

with open('generate_full_project_report.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update List of Figures in Front Matter
old_lof = '''    figures_list = [
        ("Figure 1", "High-Level Three-Tier System Architecture Diagram", "18"),
        ("Figure 2", "End-to-End Autonomous Cloud Waste Remediation Workflow", "22"),
        ("Figure 3", "Eight-Point Terraform and GitOps Security Safety Gate Architecture", "23"),
        ("Figure 4", "AWS EC2 Free-Tier Live Production Topology in Sydney (ap-southeast-2)", "24"),
        ("Figure 5", "Automated Test Suite Distribution across 11 Test Suites (163 Passing Tests)", "50"),
        ("Figure 6", "Genuine Application Screenshot: Live Header & Real AWS Connection Status", "51"),
        ("Figure 7", "Genuine Application Screenshot: Cloud Telemetry & Multi-Service Waste Findings", "51"),
        ("Figure 8", "Genuine Application Screenshot: Terraform Unified Diff & Human Sign-Off Gate", "52"),
        ("Figure 9", "Genuine Application Screenshot: GitOps Pull Request & Automated CI Pipeline", "52")
    ]'''

new_lof = '''    figures_list = [
        ("Figure 1", "High-Level Three-Tier System Architecture Diagram", "10"),
        ("Figure 2", "End-to-End Autonomous Cloud Waste Remediation Workflow", "12"),
        ("Figure 3", "Eight-Point Terraform and GitOps Security Safety Gate Architecture", "13"),
        ("Figure 4", "AWS EC2 Free-Tier Live Production Topology in Sydney (ap-southeast-2)", "14"),
        ("Figure 5", "Automated Test Suite Distribution across 11 Test Suites (163 Passing Tests)", "24"),
        ("Figure 6", "Genuine Application Screenshot: Live Cloud Discovery & Waste Detection Dashboard", "25"),
        ("Figure 7", "Genuine Application Screenshot: Terraform IaC Safety Gates & GitOps PR Review", "26")
    ]'''

if old_lof in text:
    text = text.replace(old_lof, new_lof)
    print("Updated List of Figures.")

# 2. Update Table 8.1 to 18 high-impact test cases
old_tc = '''    tc_rows = [
        ["TC-CON-01", "Verify STS caller identity authentication.", "Valid mocked STS credentials.", "Returns Account ID and User ARN.", "Account and ARN verified.", "PASS"],
        ["TC-CON-02", "Handle missing AWS credentials gracefully.", "No AWS credentials in env.", "Returns CREDENTIALS_MISSING status.", "CREDENTIALS_MISSING returned.", "PASS"],
        ["TC-DISC-01", "Discover EC2 instances with pagination.", "Mocked DescribeInstances (2 pages).", "Returns all instances across pages.", "All instances returned.", "PASS"],
        ["TC-DISC-02", "Discover unattached EBS volumes.", "Mocked DescribeVolumes with detached disk.", "Volume state marked as available.", "Status available parsed.", "PASS"],
        ["TC-MET-01", "Ingest CloudWatch CPU metrics.", "14-day CPU metric stream.", "Calculates avg and peak CPU utilization.", "Avg and peak parsed correctly.", "PASS"],
        ["TC-MET-02", "Ingest CloudWatch EBS IOPS metrics.", "14-day Read/Write IOPS stream.", "Calculates average IOPS as 0.", "IOPS correctly evaluated as 0.", "PASS"],
        ["TC-WST-01", "Detect oversized EC2 compute waste.", "Instance CPU avg 3.4%, peak 7.8%.", "Flags OVERSIZED_COMPUTE waste.", "OVERSIZED_COMPUTE flagged.", "PASS"],
        ["TC-WST-02", "Detect unattached EBS storage waste.", "EBS available, IOPS = 0.", "Flags UNATTACHED_STORAGE waste.", "UNATTACHED_STORAGE flagged.", "PASS"],
        ["TC-CST-01", "Calculate EBS monthly storage savings.", "500 GiB gp3 disk at $0.08/GB.", "Calculates $40.00/month savings.", "$40.00/month calculated.", "PASS"],
        ["TC-CST-02", "Calculate GHG carbon reduction.", "c5.4xlarge downsized to t3.medium.", "Calculates kg CO2e reduction.", "161.45 kg CO2e calculated.", "PASS"],
        ["TC-AI-01", "Synthesize Gemini AI recommendation.", "Valid Gemini API response.", "Structured AIRecommendation created.", "Structured output parsed.", "PASS"],
        ["TC-AI-02", "Mask credentials in Gemini payloads.", "Payload containing simulated keys.", "Keys stripped prior to dispatch.", "Zero credentials in payload.", "PASS"],
        ["TC-HCL-01", "Generate Terraform HCL for EBS removal.", "Unattached EBS finding.", "Generates commented-out HCL block.", "Commented HCL generated.", "PASS"],
        ["TC-HCL-02", "Reject HCL containing provisioners.", "HCL containing local-exec.", "Security exception raised; rejected.", "Security exception raised.", "PASS"],
        ["TC-TF-01", "Execute terraform fmt -check.", "Validly formatted HCL file.", "Returns returncode = 0.", "Returncode = 0 observed.", "PASS"],
        ["TC-TF-02", "Execute terraform validate.", "Valid Terraform syntax.", "Returns validation SUCCESS.", "Validation SUCCESS observed.", "PASS"],
        ["TC-TF-03", "Bind unmanaged asset via terraform import.", "Unmanaged EBS volume in live cloud.", "Imports asset into local state.", "State binding verified.", "PASS"],
        ["TC-TF-04", "Enforce dual Human Approval Gate.", "Plan generated without user checkbox.", "Blocks apply with APPROVAL_REQUIRED.", "Apply blocked successfully.", "PASS"],
        ["TC-TF-05", "Require confirmation for destructive apply.", "Plan contains resource destruction.", "Blocks apply if destructive unconfirmed.", "Destructive apply blocked.", "PASS"],
        ["TC-TF-06", "Enforce 15-minute plan expiration.", "Plan timestamp older than 15 min.", "Rejects apply with PLAN_STALE.", "PLAN_STALE returned.", "PASS"],
        ["TC-TF-07", "Detect configuration diff tampering.", "Modified HCL file after plan creation.", "Rejects apply with TAMPERING_DETECTED.", "Tampering detected.", "PASS"],
        ["TC-GIT-01", "Create isolated Git branch.", "Waste finding for vol-0e46e40.", "Creates finops/vol-0e46e40/decommission.", "Branch created successfully.", "PASS"],
        ["TC-GIT-02", "Generate automated CI checklist.", "GitOps PR opened.", "5 CI checks evaluated and recorded.", "5 CI checks populated.", "PASS"],
        ["TC-GIT-03", "Decouple PR approval from terraform apply.", "PR approved by reviewer.", "PR status APPROVED; apply NOT run.", "Apply never triggered.", "PASS"],
        ["TC-E2E-01", "Execute full end-to-end pipeline.", "Enterprise scenario selected.", "All 7 modules execute successfully.", "Full pipeline SUCCESS.", "PASS"]
    ]'''

new_tc = '''    tc_rows = [
        ["TC-CON-01", "Verify STS caller identity authentication.", "Valid mocked STS credentials.", "Returns Account ID & User ARN.", "Account & ARN verified.", "PASS"],
        ["TC-CON-02", "Handle missing AWS credentials gracefully.", "No AWS credentials in env.", "Returns CREDENTIALS_MISSING.", "CREDENTIALS_MISSING returned.", "PASS"],
        ["TC-DISC-01", "Discover EC2 instances with pagination.", "Mocked DescribeInstances (2 pages).", "Returns all instances across pages.", "All instances returned.", "PASS"],
        ["TC-DISC-02", "Discover unattached EBS volumes.", "Mocked DescribeVolumes with detached disk.", "Volume state marked available.", "Status available parsed.", "PASS"],
        ["TC-MET-01", "Ingest CloudWatch CPU & IOPS metrics.", "14-day metric streams for EC2/EBS.", "Calculates avg/peak utilization.", "Avg/peak parsed correctly.", "PASS"],
        ["TC-WST-01", "Detect oversized EC2 compute waste.", "Instance CPU avg 3.4%, peak 7.8%.", "Flags OVERSIZED_COMPUTE waste.", "OVERSIZED_COMPUTE flagged.", "PASS"],
        ["TC-WST-02", "Detect unattached EBS storage waste.", "EBS available, IOPS = 0.", "Flags UNATTACHED_STORAGE waste.", "UNATTACHED_STORAGE flagged.", "PASS"],
        ["TC-CST-01", "Calculate monthly savings & GHG carbon.", "500 GiB gp3 disk & c5.4xlarge.", "Calculates $40/mo & 161 kg CO2.", "Financial & CO2 calculated.", "PASS"],
        ["TC-AI-01", "Synthesize Gemini AI recommendation.", "Valid Gemini API response.", "Structured AIRecommendation.", "Structured output parsed.", "PASS"],
        ["TC-AI-02", "Mask credentials in Gemini payloads.", "Payload with simulated keys.", "Keys stripped prior to dispatch.", "Zero credentials in payload.", "PASS"],
        ["TC-HCL-01", "Generate Terraform HCL patch for EBS.", "Unattached EBS finding.", "Generates commented-out HCL.", "Commented HCL generated.", "PASS"],
        ["TC-TF-01", "Execute terraform fmt & validate.", "Valid HCL patch file.", "Returns validation SUCCESS.", "Validation SUCCESS observed.", "PASS"],
        ["TC-TF-02", "Bind unmanaged asset via terraform import.", "Unmanaged EBS volume in live cloud.", "Imports asset into local state.", "State binding verified.", "PASS"],
        ["TC-TF-03", "Enforce dual Human Approval Gate.", "Plan generated without user sign-off.", "Blocks apply with APPROVAL_REQUIRED.", "Apply blocked successfully.", "PASS"],
        ["TC-TF-04", "Enforce 15-min plan expiry & tampering.", "Plan >15 min or modified diff.", "Rejects apply with PLAN_STALE/TAMPER.", "Security rejection verified.", "PASS"],
        ["TC-GIT-01", "Create isolated GitOps branch & commit.", "Waste finding for vol-0e46e40.", "Creates finops/vol-0e46e40/decom.", "Branch & commit verified.", "PASS"],
        ["TC-GIT-02", "Decouple PR approval from terraform apply.", "PR approved by reviewer.", "PR status APPROVED; apply NOT run.", "Apply never triggered.", "PASS"],
        ["TC-E2E-01", "Execute full end-to-end pipeline.", "Enterprise scenario selected.", "All 7 modules execute successfully.", "Full pipeline SUCCESS.", "PASS"]
    ]'''

if old_tc in text:
    text = text.replace(old_tc, new_tc)
    print("Updated Table 8.1.")

# 3. Update Section 8 figures
old_figs = '''    add_fig("fig_ui_header_overview.png", "6", "Genuine Application Screenshot: Header Navigation Bar, Live AWS Connection Badge (Account 105456916922, ap-southeast-2), and Financial Waste Overview Donut Charts.", width=Inches(5.8))

    add_fig("fig_ui_modules_findings.png", "7", "Genuine Application Screenshot: Discovered Cloud Resource Inventory (Module 1) and Active Waste Findings Table (Module 2) displaying detected idle storage and compute waste.", width=Inches(5.8))

    add_fig("fig_ui_terraform_gate.png", "8", "Genuine Application Screenshot: Module 6 Terraform Unified Diff Viewer and the Explicit Human Sign-Off Gate showing the mandatory approval checkboxes.", width=Inches(5.8))

    add_fig("fig_ui_gitops_review.png", "9", "Genuine Application Screenshot: Module 7 GitOps Review Card showing the Pull Request status, Automated CI/CD Checklist, and Tamper-Evident Audit Trail.", width=Inches(5.8))'''

new_figs = '''    add_fig("fig_ui_dashboard_panel.png", "6", "Genuine Application Screenshot: Live Cloud Discovery & Waste Detection Dashboard showing the authenticated AWS Sydney account (105456916922), financial spend charts, discovered inventory, and real unattached storage waste findings.", width=Inches(4.5))

    add_fig("fig_ui_remediation_panel.png", "7", "Genuine Application Screenshot: Infrastructure as Code Safety Gates and GitOps Pull Request Review showing the Module 6 Terraform unified diff viewer, the dual-checkbox Human Sign-Off Gate, and the Module 7 automated CI/CD validation checklist.", width=Inches(4.5))'''

if old_figs in text:
    text = text.replace(old_figs, new_figs)
    print("Updated Section 8 figures.")

with open('generate_full_project_report.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Saved updated generate_full_project_report.py")
