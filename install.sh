#!/bin/bash
# KNX Automation Dashboard - Installation Script
# Run as root: sudo ./install.sh
set -e

echo "=============================================="
echo "  KNX Automation Dashboard - Installation"
echo "=============================================="
echo ""

# Install packages based on distro
echo "[1/5] Installing system packages..."
if command -v dnf &> /dev/null; then
    dnf install -y python3 python3-pip firewalld p7zip p7zip-plugins
elif command -v yum &> /dev/null; then
    yum install -y python3 python3-pip p7zip p7zip-plugins
elif command -v apt-get &> /dev/null; then
    apt-get update
    apt-get install -y python3 python3-pip python3-venv p7zip-full sqlite3
else
    echo "❌ Unbekannter Paketmanager"
    exit 1
fi

# Create install directory
echo "[2/5] Creating installation directory..."
mkdir -p /opt/knx-automation
mkdir -p /opt/knx-automation/data
mkdir -p /opt/knx-automation/static/vse
cd /opt/knx-automation

# Create venv
echo "[3/5] Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python packages
echo "[4/5] Installing Python packages..."
pip install --upgrade pip
pip install \
    fastapi \
    uvicorn[standard] \
    xknx \
    sqlalchemy \
    aiosqlite \
    python-dotenv \
    pydantic \
    pydantic-settings \
    websockets \
    python-multipart \
    aiohttp \
    pyzipper

# Create systemd service
echo "[5/5] Creating systemd service..."
cat > /etc/systemd/system/knx-automation.service << 'EOF'
[Unit]
Description=KNX Automation Dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/knx-automation
ExecStart=/opt/knx-automation/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Enable service
systemctl daemon-reload
systemctl enable knx-automation

# Firewall (optional)
if command -v firewall-cmd &> /dev/null; then
    firewall-cmd --add-port=8000/tcp --permanent 2>/dev/null || true
    firewall-cmd --reload 2>/dev/null || true
fi

echo ""
echo "=============================================="
echo "  ✅ Installation abgeschlossen!"
echo "=============================================="
echo ""
echo "Nächste Schritte:"
echo ""
echo "1. Dashboard-Paket entpacken:"
echo "   cd /opt/knx-automation"
echo "   tar -xzf /pfad/zu/knx-automation-v3.0.x.tar.gz --strip-components=1"
echo ""
echo "2. Service starten:"
echo "   systemctl start knx-automation"
echo ""
echo "3. Dashboard öffnen:"
echo "   http://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo "Service-Befehle:"
echo "   Status:   systemctl status knx-automation"
echo "   Logs:     journalctl -u knx-automation -f"
echo "   Neustart: systemctl restart knx-automation"
echo ""
