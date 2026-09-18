"""
FinOps Cloud Waste Hunter & Auto-Remediator
Simulated Cloud Infrastructure Scenarios (CloudWatch Telemetry & Resource States).
ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

from typing import List, Dict
from core.models import CloudResource, ResourceType

SCENARIOS: Dict[str, Dict] = {
    "enterprise": {
        "id": "enterprise",
        "name": "Enterprise Multi-Service (High Waste)",
        "description": "Realistic enterprise environment with oversized compute clusters, abandoned EBS storage, forgotten serverless Lambdas, and idle networking assets.",
        "resources": [
            {
                "id": "i-09f84a8123bc45e01",
                "name": "analytics-batch-worker-prod",
                "resource_type": "EC2",
                "region": "us-east-1",
                "state": "running",
                "specs": {
                    "instance_type": "c5.4xlarge",
                    "vcpus": 16,
                    "ram_gb": 32,
                    "platform": "Linux",
                    "lifecycle": "on-demand"
                },
                "tags": {
                    "Environment": "Production",
                    "Project": "DataAnalytics",
                    "Owner": "data-team",
                    "Terraform": "true"
                },
                "metrics": {
                    "cpu_utilization_avg": 3.4,
                    "cpu_utilization_max": 7.8,
                    "memory_utilization_avg": 14.2,
                    "network_in_mb_avg": 12.5,
                    "network_out_mb_avg": 8.1,
                    "evaluation_period_days": 30
                }
            },
            {
                "id": "i-0a7b1c3d9482ef512",
                "name": "internal-tooling-dashboard",
                "resource_type": "EC2",
                "region": "us-east-1",
                "state": "running",
                "specs": {
                    "instance_type": "m5.2xlarge",
                    "vcpus": 8,
                    "ram_gb": 32,
                    "platform": "Linux",
                    "lifecycle": "on-demand"
                },
                "tags": {
                    "Environment": "Internal",
                    "Owner": "devops",
                    "Terraform": "true"
                },
                "metrics": {
                    "cpu_utilization_avg": 4.1,
                    "cpu_utilization_max": 8.5,
                    "memory_utilization_avg": 18.0,
                    "network_in_mb_avg": 5.0,
                    "network_out_mb_avg": 4.2,
                    "evaluation_period_days": 30
                }
            },
            {
                "id": "vol-0e4b8893d5678a123",
                "name": "backup-volume-migration-temp",
                "resource_type": "EBS",
                "region": "us-east-1",
                "state": "available",
                "specs": {
                    "volume_type": "gp3",
                    "size_gb": 500,
                    "iops": 3000,
                    "throughput_mbps": 125,
                    "encrypted": True
                },
                "tags": {
                    "Environment": "Production",
                    "Purpose": "OldDatabaseMigration",
                    "Terraform": "true"
                },
                "metrics": {
                    "attachment_status": "unattached",
                    "days_unattached": 45,
                    "read_iops_avg": 0,
                    "write_iops_avg": 0
                }
            },
            {
                "id": "vol-033c44d55e66f7788",
                "name": "legacy-log-volume",
                "resource_type": "EBS",
                "region": "us-east-1",
                "state": "available",
                "specs": {
                    "volume_type": "gp2",
                    "size_gb": 250,
                    "iops": 750,
                    "throughput_mbps": 125,
                    "encrypted": False
                },
                "tags": {
                    "Environment": "Legacy",
                    "Terraform": "true"
                },
                "metrics": {
                    "attachment_status": "unattached",
                    "days_unattached": 62,
                    "read_iops_avg": 0,
                    "write_iops_avg": 0
                }
            },
            {
                "id": "arn:aws:lambda:us-east-1:123456789012:function:legacy-image-resizer",
                "name": "legacy-image-resizer",
                "resource_type": "LAMBDA",
                "region": "us-east-1",
                "state": "active",
                "specs": {
                    "runtime": "python3.9",
                    "memory_mb": 1024,
                    "timeout_seconds": 60,
                    "provisioned_concurrency": 2
                },
                "tags": {
                    "Environment": "Production",
                    "Deprecated": "true",
                    "Terraform": "true"
                },
                "metrics": {
                    "invocations_30d": 0,
                    "duration_ms_avg": 0,
                    "errors_30d": 0,
                    "throttles_30d": 0,
                    "last_invoked_days_ago": 94
                }
            },
            {
                "id": "arn:aws:lambda:us-east-1:123456789012:function:nightly-report-exporter-v1",
                "name": "nightly-report-exporter-v1",
                "resource_type": "LAMBDA",
                "region": "us-east-1",
                "state": "active",
                "specs": {
                    "runtime": "nodejs18.x",
                    "memory_mb": 512,
                    "timeout_seconds": 30,
                    "provisioned_concurrency": 0
                },
                "tags": {
                    "Environment": "Staging",
                    "Terraform": "true"
                },
                "metrics": {
                    "invocations_30d": 0,
                    "duration_ms_avg": 0,
                    "errors_30d": 0,
                    "throttles_30d": 0,
                    "last_invoked_days_ago": 41
                }
            },
            {
                "id": "eipalloc-0123456789abcdef0",
                "name": "unassociated-elastic-ip-1",
                "resource_type": "EIP",
                "region": "us-east-1",
                "state": "unassociated",
                "specs": {
                    "public_ip": "54.210.14.89",
                    "domain": "vpc"
                },
                "tags": {
                    "Environment": "Production",
                    "Terraform": "true"
                },
                "metrics": {
                    "associated_instance": None,
                    "days_unassociated": 38
                }
            },
            {
                "id": "nat-0987654321fedcba0",
                "name": "staging-legacy-nat-gateway",
                "resource_type": "NAT_GATEWAY",
                "region": "us-east-1",
                "state": "available",
                "specs": {
                    "vpc_id": "vpc-01a2b3c4d5e",
                    "subnet_id": "subnet-09f8e7d6c"
                },
                "tags": {
                    "Environment": "Staging",
                    "Terraform": "true"
                },
                "metrics": {
                    "bytes_processed_30d_mb": 4.2,
                    "active_connections_avg": 0.05
                }
            },
            {
                "id": "i-0healthy123456789",
                "name": "active-api-gateway-node",
                "resource_type": "EC2",
                "region": "us-east-1",
                "state": "running",
                "specs": {
                    "instance_type": "c5.xlarge",
                    "vcpus": 4,
                    "ram_gb": 8,
                    "platform": "Linux",
                    "lifecycle": "on-demand"
                },
                "tags": {
                    "Environment": "Production",
                    "Service": "CoreAPI"
                },
                "metrics": {
                    "cpu_utilization_avg": 68.4,
                    "cpu_utilization_max": 89.2,
                    "memory_utilization_avg": 74.0,
                    "network_in_mb_avg": 450.0,
                    "network_out_mb_avg": 820.0,
                    "evaluation_period_days": 30
                }
            }
        ]
    },
    "startup": {
        "id": "startup",
        "name": "Startup MVP (Medium Waste)",
        "description": "Fast-moving startup infrastructure with over-provisioned developer machines and leftover test disks.",
        "resources": [
            {
                "id": "i-0fedcba9876543210",
                "name": "dev-monolith-staging",
                "resource_type": "EC2",
                "region": "us-west-2",
                "state": "running",
                "specs": {
                    "instance_type": "t3.2xlarge",
                    "vcpus": 8,
                    "ram_gb": 32,
                    "platform": "Linux",
                    "lifecycle": "on-demand"
                },
                "tags": {
                    "Environment": "Staging",
                    "Team": "Backend",
                    "Terraform": "true"
                },
                "metrics": {
                    "cpu_utilization_avg": 2.1,
                    "cpu_utilization_max": 6.5,
                    "memory_utilization_avg": 12.0,
                    "network_in_mb_avg": 1.2,
                    "network_out_mb_avg": 1.5,
                    "evaluation_period_days": 14
                }
            },
            {
                "id": "vol-09988776655443322",
                "name": "temp-scratch-disk",
                "resource_type": "EBS",
                "region": "us-west-2",
                "state": "available",
                "specs": {
                    "volume_type": "gp2",
                    "size_gb": 120,
                    "iops": 360,
                    "throughput_mbps": 125,
                    "encrypted": False
                },
                "tags": {
                    "Environment": "Development",
                    "Terraform": "true"
                },
                "metrics": {
                    "attachment_status": "unattached",
                    "days_unattached": 21,
                    "read_iops_avg": 0,
                    "write_iops_avg": 0
                }
            },
            {
                "id": "arn:aws:lambda:us-west-2:123456789012:function:demo-webhook-handler",
                "name": "demo-webhook-handler",
                "resource_type": "LAMBDA",
                "region": "us-west-2",
                "state": "active",
                "specs": {
                    "runtime": "python3.11",
                    "memory_mb": 256,
                    "timeout_seconds": 15,
                    "provisioned_concurrency": 0
                },
                "tags": {
                    "Environment": "Dev",
                    "Terraform": "true"
                },
                "metrics": {
                    "invocations_30d": 0,
                    "duration_ms_avg": 0,
                    "errors_30d": 0,
                    "throttles_30d": 0,
                    "last_invoked_days_ago": 45
                }
            }
        ]
    },
    "clean": {
        "id": "clean",
        "name": "Well-Architected FinOps Baseline",
        "description": "Optimized cloud environment with high utilization, right-sized instances, and active lifecycle policies.",
        "resources": [
            {
                "id": "i-0optimal000000001",
                "name": "web-frontend-cluster",
                "resource_type": "EC2",
                "region": "us-east-1",
                "state": "running",
                "specs": {
                    "instance_type": "t3.medium",
                    "vcpus": 2,
                    "ram_gb": 4,
                    "platform": "Linux",
                    "lifecycle": "on-demand"
                },
                "tags": {
                    "Environment": "Production"
                },
                "metrics": {
                    "cpu_utilization_avg": 62.1,
                    "cpu_utilization_max": 81.3,
                    "memory_utilization_avg": 68.5,
                    "network_in_mb_avg": 120.0,
                    "network_out_mb_avg": 340.0,
                    "evaluation_period_days": 30
                }
            }
        ]
    }
}


def get_scenario_resources(scenario_id: str = "enterprise") -> List[CloudResource]:
    data = SCENARIOS.get(scenario_id, SCENARIOS["enterprise"])
    return [CloudResource(**res) for res in data["resources"]]
