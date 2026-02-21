#!/bin/bash
# KNX Easy Install - Run as root
set -e

echo "=== KNX Automation Installer ==="

# Install packages
echo "[1/5] Installing packages..."
dnf install -y python3 python3-pip firewalld p7zip p7zip-plugins 2>/dev/null || \
yum install -y python3 python3-pip p7zip p7zip-plugins 2>/dev/null || \
apt-get install -y python3 python3-pip python3-venv p7zip-full 2>/dev/null

# Create venv
echo "[2/5] Creating virtual environment..."
cd /opt/knx-automation
python3 -m venv venv
source venv/bin/activate

# Install Python packages
echo "[3/5] Installing Python packages..."
pip install --upgrade pip
pip install fastapi uvicorn xknx sqlalchemy aiosqlite python-dotenv pydantic pydantic-settings websockets python-multipart aiohttp pyzipper

# Create systemd service
echo "[4/5] Creating service..."
cat > /etc/systemd/system/knx-automation.service << 'EOF'
[Unit]
Description=KNX Automation System
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/knx-automation
ExecStart=/opt/knx-automation/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
echo "[5/5] Starting service..."
systemctl daemon-reload
systemctl enable knx-automation
systemctl restart knx-automation

# Firewall
firewall-cmd --add-port=8000/tcp --permanent 2>/dev/null || true
firewall-cmd --reload 2>/dev/null || true

echo ""
echo "=== Installation complete! ==="
echo "Dashboard: http://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo "Commands:"
echo "  Status:  systemctl status knx-automation"
echo "  Logs:    journalctl -u knx-automation -f"
echo "  Restart: systemctl restart knx-automation"
