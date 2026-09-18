"""
FinOps Cloud Waste Hunter & Auto-Remediator CLI
Command-line interface for headless automation, CI/CD pipelines, and terminal demonstrations.
ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import sys
import json
import argparse

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.engine import FinOpsEngine


def main():
    parser = argparse.ArgumentParser(
        description="FinOps Cloud Waste Hunter & Auto-Remediator (ISWE309L Cloud Computing)"
    )
    parser.add_argument(
        "--scenario",
        choices=["enterprise", "startup", "clean"],
        default="enterprise",
        help="Cloud infrastructure scenario to analyze (default: enterprise)"
    )
    parser.add_argument(
        "--module",
        type=int,
        choices=[1, 2, 3, 4, 5, 6, 7],
        help="Inspect a specific module (1 to 7) individually"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)"
    )
    parser.add_argument(
        "--live-aws",
        action="store_true",
        help="Connect to live AWS account via Boto3 if configured"
    )

    args = parser.parse_args()
    engine = FinOpsEngine(use_live_aws=args.live_aws)

    if args.module:
        data = engine.get_module_data(args.module, scenario_id=args.scenario)
        print(json.dumps(data, indent=2))
        return

    # Full execution
    report = engine.execute_full_pipeline(scenario_id=args.scenario)

    if args.format == "json":
        print(json.dumps(report.model_dump(), indent=2))
        return
    elif args.format == "markdown":
        print(engine.module5._generate_markdown_report(report.model_dump()))
        return

    # Rich Text Terminal Output
    print("=" * 80)
    print(" [FINOPS] Cloud Waste Hunter & Auto-Remediator")
    print(" Course: ISWE309L Cloud Computing | Slot: A1 + TA1 | VIT Vellore")
    print(" Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)")
    print("=" * 80)
    print(f"[*] Execution Run ID:      {report.run_id}")
    print(f"[*] Analyzed Scenario:     {report.scenario.upper()}")
    print(f"[*] Monitored Assets:      {len(report.monitored_resources)} cloud resources")
    print(f"[*] Inefficiencies:        {len(report.waste_findings)} waste conditions detected")
    print(f"[*] Current Monthly Cost:  ${report.total_current_monthly_cost:.2f}")
    print(f"[*] Optimized Monthly:     ${report.total_optimized_monthly_cost:.2f}")
    print(f"[*] Total Monthly Savings: ${report.total_monthly_savings:.2f} / month")
    print(f"[*] Total Annual Savings:  ${report.total_annualized_savings:.2f} / year")
    print(f"[*] Carbon Offset:         {report.total_carbon_savings_kg:.2f} kg CO2e")
    print(f"[*] Amazon Bedrock Model:  amazon.nova-lite-v1:0 ({len(report.ai_recommendations)} recs)")
    print(f"[*] Terraform Patches:     {len(report.terraform_patches)} files patched")
    if report.gitops_pr:
        print(f"[*] GitOps Pull Request:   #{report.gitops_pr.pr_number} [{report.gitops_pr.status}] on '{report.gitops_pr.branch_name}'")
    print(f"[*] S3 Audit Archive:      {report.s3_uri}")
    print("=" * 80)
    print("\n[+] Top Waste Findings & Auto-Remediation Patches:")
    for idx, f in enumerate(report.waste_findings, 1):
        sev_val = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
        type_val = f.resource_type.value if hasattr(f.resource_type, "value") else str(f.resource_type)
        print(f"  {idx}. [{sev_val}] {f.resource_name} ({type_val})")
        print(f"     Issue:   {f.description}")
        print(f"     Target:  {f.recommended_specs}")
    print("\n[OK] Run completed successfully. Run `start_app.bat` to launch the interactive UI.\n")


if __name__ == "__main__":
    main()
