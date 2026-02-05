#!/bin/bash
# II-Telegram-Agent Setup Script for Small PCs
# Tested on: Intel NUC, Raspberry Pi 5, Mini PCs, Ubuntu Server

set -e

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║        II-Telegram-Agent - Small PC Setup Script          ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}Please don't run as root. The script will use sudo when needed.${NC}"
    exit 1
fi

# Check OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
    VER=$VERSION_ID
else
    echo -e "${RED}Cannot determine OS. This script supports Ubuntu/Debian.${NC}"
    exit 1
fi

echo -e "${GREEN}Detected OS:${NC} $OS $VER"
echo ""

# Step 1: Update system
echo -e "${YELLOW}Step 1: Updating system packages...${NC}"
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

# Step 2: Install Docker
echo -e "${YELLOW}Step 2: Installing Docker...${NC}"
if command -v docker &> /dev/null; then
    echo -e "${GREEN}Docker already installed.${NC}"
else
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo -e "${GREEN}Docker installed. You may need to log out and back in.${NC}"
fi

# Step 3: Install Docker Compose
echo -e "${YELLOW}Step 3: Checking Docker Compose...${NC}"
if docker compose version &> /dev/null; then
    echo -e "${GREEN}Docker Compose available.${NC}"
else
    echo -e "${RED}Docker Compose not available. Installing...${NC}"
    sudo apt-get install -y docker-compose-plugin
fi

# Step 4: Clone or update repository
echo -e "${YELLOW}Step 4: Setting up II-Telegram-Agent...${NC}"
INSTALL_DIR="$HOME/ii-telegram-agent"

if [ -d "$INSTALL_DIR" ]; then
    echo "Directory exists. Updating..."
    cd "$INSTALL_DIR"
    git pull
else
    echo "Cloning repository..."
    cd "$HOME"
    # For local setup, just copy files
    if [ -d "/workspace/ii-telegram-agent" ]; then
        cp -r /workspace/ii-telegram-agent "$INSTALL_DIR"
    else
        git clone https://github.com/Jack-Batman/ii-telegram-agent.git "$INSTALL_DIR"
    fi
    cd "$INSTALL_DIR"
fi

# Step 5: Create .env if not exists
echo -e "${YELLOW}Step 5: Configuring environment...${NC}"
if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${YELLOW}Created .env file. Please edit it with your settings:${NC}"
    echo "  nano $INSTALL_DIR/.env"
    echo ""
    echo "Required settings:"
    echo "  - TELEGRAM_BOT_TOKEN (from @BotFather)"
    echo "  - ANTHROPIC_API_KEY or OPENAI_API_KEY"
else
    echo -e "${GREEN}.env file exists.${NC}"
fi

# Step 6: Create data directory
mkdir -p data

# Step 7: Create systemd service
echo -e "${YELLOW}Step 6: Creating systemd service...${NC}"
SERVICE_FILE="/etc/systemd/system/ii-telegram-agent.service"

sudo tee $SERVICE_FILE > /dev/null << EOF
[Unit]
Description=II-Telegram-Agent
Requires=docker.service
After=docker.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/docker compose up
ExecStop=/usr/bin/docker compose down
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
echo -e "${GREEN}Systemd service created.${NC}"

# Step 8: Optional - Install Tailscale
echo ""
read -p "Do you want to install Tailscale for remote access? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Installing Tailscale...${NC}"
    curl -fsSL https://tailscale.com/install.sh | sh
    echo -e "${GREEN}Tailscale installed. Run 'sudo tailscale up' to configure.${NC}"
fi

# Done
echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                    Setup Complete!                        ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo ""
echo "1. Edit your configuration:"
echo "   nano $INSTALL_DIR/.env"
echo ""
echo "2. Start the bot:"
echo "   cd $INSTALL_DIR && docker compose up -d"
echo ""
echo "3. View logs:"
echo "   docker compose logs -f"
echo ""
echo "4. Enable auto-start on boot:"
echo "   sudo systemctl enable ii-telegram-agent"
echo ""
echo "5. Access the dashboard:"
echo "   http://localhost:8080"
echo ""
echo -e "${YELLOW}Note: If this is a fresh Docker install, log out and back in first.${NC}"