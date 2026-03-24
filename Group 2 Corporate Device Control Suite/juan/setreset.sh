#!/bin/bash
# Setup and reset script for client

# Configure variables below
EMPLOYEE_PASSWORD="employee123"

if [[ $EUID -ne 0 ]]; then
   echo "ERROR: Script must be run with sudo"
   exit 1
fi

# Get the username who started this script
REAL_USER=$(logname 2>/dev/null || echo $SUDO_USER)

# Root vault setup

VAULT_ROOT="/root/cdcs"
CURRENT_DIR="$(cd "$(dirname "$0")" && pwd)"

# If script is not run from /root
if [ "$CURRENT_DIR" != "$VAULT_ROOT/juan" ]; then
    echo "Moving project into the protected /root vault..."
    mkdir -p "$VAULT_ROOT"
    cp -r "$CURRENT_DIR/.."/* "$VAULT_ROOT/"
    # Restart the script from within root
    chmod +x "$VAULT_ROOT/juan/setreset.sh"
    exec "$VAULT_ROOT/juan/setreset.sh" "$@"
fi

# Set working directory
cd "$(dirname "$0")"
# Exit the script immediately if any command fails
set -e

# Install NVM for root

install_node_for_root() {
    export NVM_DIR="/root/.nvm"
    if [ ! -s "$NVM_DIR/nvm.sh" ]; then
        echo "Installing NVM for root..."
        # NOTE: Update with latest NVM release script
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.4/install.sh | bash
    fi

    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm install --lts
    nvm use --lts
    nvm alias default 'lts/*'

    echo "Node installed at: $(which node)"
    echo "Node version: $(node --version)"
}

# Setup function

setup_all() {
    # PHASE 0: Status check. Check if setup has been completed before.
    
    echo "Status check in progress..."
    if systemctl is-active --quiet cdcs.service && [ -d "$VAULT_ROOT" ]; then
        echo "ALERT: Setup is already complete"
        read -p "Re-run setup? (y/N): " confirm
        if [[ $confirm != [yY] ]]; then
            echo "Exiting setup"
            exit 0
        fi
    fi

    # PHASE 1: Repo setup. Add apt repositories for various software tools.

    echo "Setting up software..."
    # Install Git
    if ! command -v git &>/dev/null; then
        apt-get update && apt-get install -y git
    fi

    # Setup MongoDB repo
    if ! command -v google-chrome &>/dev/null; then
        wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/trusted.gpg.d/google-chrome.gpg
        echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list
        apt-get update
    fi

    # Setup Google Chrome repo
    if ! command -v mongod &>/dev/null; then
        curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
        echo "deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" > /etc/apt/sources.list.d/mongodb-org-7.0.list
        apt-get update
    fi

    # Setup VS Code repo
    if ! command -v code &>/dev/null; then
        wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /usr/share/keyrings/microsoft.gpg
        cat > /etc/apt/sources.list.d/vscode.sources <<EOF
Types: deb
URIs: https://packages.microsoft.com/repos/code
Suites: stable
Components: main
Architectures: amd64,arm64,armhf
Signed-By: /usr/share/keyrings/microsoft.gpg
EOF
        apt-get update
    fi

    # PHASE 2: User provisioning. Set perms for current and employee user.
    
    echo "Promoting '$REAL_USER' to admin..."
    usermod -aG sudo "$REAL_USER"
    echo "${REAL_USER}:admin123" | chpasswd
    echo "NOTE: Admin '$REAL_USER' password set to admin123"

    if ! id "cdcs_employee" &>/dev/null; then
        useradd -m -s /bin/bash cdcs_employee
        echo "User 'cdcs_employee' created."
    fi
    echo "cdcs_employee:$EMPLOYEE_PASSWORD" | chpasswd
    echo "NOTE: 'cdcs_employee' password set to $EMPLOYEE_PASSWORD"

    # PHASE 3: Security. Setup firewall.
    
    # Setup fail2ban
    apt-get install -y ufw fail2ban
    ufw allow ssh
    ufw --force enable
    systemctl enable fail2ban && systemctl start fail2ban

    # PHASE 4: Install Node.js via NVM
    
    # Call NVM install function
    install_node_for_root

    export NVM_DIR="/root/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

    # PHASE 5: Dependency installation for client
    
    echo "Installing client backend dependencies..."
    npm install --prefix "$VAULT_ROOT/deril" --silent

    if [ -d "$VAULT_ROOT/evana/client_frontend" ]; then
        echo "Installing client frontend dependencies..."
        npm install --prefix "$VAULT_ROOT/evana/client_frontend" --silent
    fi

    # PHASE 6: Setup runner script. Starts frontend and backend.

    # Create script called by SystemD service
    RUNNER_SCRIPT="$VAULT_ROOT/run_cdcs.sh"

    tee "$RUNNER_SCRIPT" > /dev/null <<'EOF'
#!/bin/bash

export NVM_DIR="/root/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

VAULT_ROOT="/root/cdcs"

# Start frontend in background
cd "$VAULT_ROOT/evana/client_frontend"
npm install --silent
nohup npm run dev > "$VAULT_ROOT/frontend.log" 2>&1 &

# Wait for port 5173
while ! ss -tulwn | grep -q 5173; do sleep 1; done

# Start backend
cd "$VAULT_ROOT/deril"
exec node client.js
EOF

    chmod +x "$RUNNER_SCRIPT"

    # PHASE 7: Setup background service. Ensures client is always running.
    
    # Create SystemD service
    tee /etc/systemd/system/cdcs.service > /dev/null <<EOF
[Unit]
Description=CDCS Client Service
After=network.target

[Service]
User=root
WorkingDirectory=$VAULT_ROOT
ExecStart=$RUNNER_SCRIPT
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable cdcs.service
    systemctl restart cdcs.service

    # PHASE 8: Create desktop launcher. Acccess frontend via .desktop file.

    DESKTOP_DIR="/home/cdcs_employee/Desktop"
    mkdir -p "$DESKTOP_DIR"

    tee "$DESKTOP_DIR/cdcs-portal.desktop" > /dev/null <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=CDCS Client Portal
Exec=firefox http://localhost:5173
Icon=firefox
Terminal=false
Categories=Office;
EOF

    chmod +x "$DESKTOP_DIR/cdcs-portal.desktop"
    chown cdcs_employee:cdcs_employee "$DESKTOP_DIR/cdcs-portal.desktop"
    sudo -u cdcs_employee gio set "$DESKTOP_DIR/cdcs-portal.desktop" metadata::trusted true || true

    # PHASE 9: Lockdown vault permissions

    chown root:root -R "$VAULT_ROOT"
    chmod 700 "$VAULT_ROOT"

    echo "ALERT: Setup has completed successfully"
}

# =================================================================
# RESET FUNCTION
# =================================================================
reset_all() {
    echo "--- INITIATING SYSTEM RESET ---"

    echo "[1/4] Terminating 'cdcs' user processes..."
    pkill -u cdcs || true
    sleep 2

    echo "[2/4] Sanitizing 'cdcs' workspace..."
    find /home/cdcs -mindepth 1 -not -path '*/.nvm*' -delete
    mkdir -p /home/cdcs/{Desktop,Documents,Downloads,Pictures}
    chown -R cdcs:cdcs /home/cdcs

    echo "[3/4] Resetting 'cdcs' credentials..."
    echo "cdcs:employee123" | chpasswd

    echo "[4/4] Restarting Governance Agent..."
    systemctl restart cdcs.service
    echo "* RESET COMPLETE: GOLDEN BASELINE RESTORED *"
}

case "$1" in
    setup) setup_all ;;
    reset) reset_all ;;
    *) echo "ERROR: Script must be run as 'sudo ./setreset.sh {setup|reset}'" ;;
esac
