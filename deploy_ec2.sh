#!/usr/bin/env bash
# ==============================================================================
# Cloud Waste Hunter - EC2 Free Tier Deployment Script (Ubuntu 22.04 / 24.04)
# ==============================================================================
# Usage:
#   chmod +x deploy_ec2.sh
#   sudo ./deploy_ec2.sh
# ==============================================================================

set -e

echo "=== [1/5] Updating system packages ==="
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv git curl unzip wget gnupg software-properties-common

echo "=== [2/5] Installing HashiCorp Terraform CLI ==="
if ! command -v terraform &> /dev/null; then
    wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg --yes
    echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
    sudo apt-get update -y
    sudo apt-get install -y terraform
else
    echo "Terraform is already installed: $(terraform version | head -n 1)"
fi

echo "=== [3/5] Setting up Python Virtual Environment ==="
PROJECT_DIR="$(pwd)"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "=== [4/5] Creating systemd service ==="
CURRENT_USER="$(whoami)"
SERVICE_FILE="/etc/systemd/system/cloud-waste-hunter.service"

sudo bash -c "cat > ${SERVICE_FILE}" <<EOF
[Unit]
Description=Cloud Waste Hunter & Auto-Remediator Web Service
After=network.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${PROJECT_DIR}
Environment="PATH=${PROJECT_DIR}/venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=-${PROJECT_DIR}/.env
ExecStart=${PROJECT_DIR}/venv/bin/python -m uvicorn app.server:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable cloud-waste-hunter.service

echo "=== [5/5] Deployment Preparation Complete! ==="
echo ""
echo "Next steps:"
echo "1. If you use Google Gemini, add your API key to .env:"
echo "   echo 'GEMINI_API_KEY=your_key_here' >> .env"
echo "2. Start the service:"
echo "   sudo systemctl start cloud-waste-hunter"
echo "3. Check service status:"
echo "   sudo systemctl status cloud-waste-hunter"
echo "4. Access the web dashboard at:"
echo "   http://<YOUR_EC2_PUBLIC_IP>:8000"
echo "=============================================================================="
