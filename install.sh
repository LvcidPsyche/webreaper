#!/bin/bash
# WebReaper Installation & Setup Script
# One-command setup for complete scraping workflow

set -e

echo "🕷️  WebReaper Installation Script"
echo "=================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_status() {
    echo -e "${BLUE}[*]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check Python version
print_status "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" = "$REQUIRED_VERSION" ]; then 
    print_success "Python $PYTHON_VERSION found (>= $REQUIRED_VERSION required)"
else
    print_error "Python >= $REQUIRED_VERSION required, found $PYTHON_VERSION"
    exit 1
fi

# Check for pip
if ! command -v pip3 &> /dev/null; then
    print_error "pip3 not found. Please install pip."
    exit 1
fi

# Installation directory
INSTALL_DIR="${HOME}/.local/share/webreaper"
CONFIG_DIR="${HOME}/.config/webreaper"
FEEDS_DIR="${HOME}/.local/share/blogwatcher/feeds"

print_status "Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"
mkdir -p "$FEEDS_DIR"
print_success "Directories created"

# Copy files
print_status "Installing WebReaper..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -r "$SCRIPT_DIR/webreaper" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/webreaper.py" "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR/config" "$CONFIG_DIR/"
print_success "Files installed to $INSTALL_DIR"

# Install Python dependencies
print_status "Installing Python dependencies..."
cd "$INSTALL_DIR"
pip3 install --user -q -r requirements.txt
print_success "Dependencies installed"

# Create symlinks
print_status "Creating command shortcuts..."
BIN_DIR="${HOME}/.local/bin"
mkdir -p "$BIN_DIR"

ln -sf "$INSTALL_DIR/webreaper.py" "$BIN_DIR/webreaper"
ln -sf "$INSTALL_DIR/webreaper/hooks/blogwatcher-hook.sh" "$BIN_DIR/webreaper-hook"

# Add to PATH if needed
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    print_warning "Adding $BIN_DIR to PATH"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    export PATH="$HOME/.local/bin:$PATH"
fi

print_success "Command shortcuts created"

# Install Playwright browsers
print_status "Installing Playwright browsers (this may take a while)..."
python3 -m playwright install chromium
print_success "Browsers installed"

# Create default config
print_status "Creating default configuration..."
cp "$CONFIG_DIR/config/webreaper.yaml" "$CONFIG_DIR/config.yaml"
print_success "Configuration created at $CONFIG_DIR/config.yaml"

# Set up blogwatcher integration
print_status "Setting up blogwatcher integration..."
if command -v blogwatcher &> /dev/null; then
    # Add hook to blogwatcher
    BLOGWATCHER_CONFIG="${HOME}/.config/blogwatcher/config.yaml"
    if [ -f "$BLOGWATCHER_CONFIG" ]; then
        echo "scraper_hook: webreaper-hook" >> "$BLOGWATCHER_CONFIG"
        print_success "Blogwatcher hook configured"
    else
        print_warning "blogwatcher config not found. Manual setup required."
    fi
else
    print_warning "blogwatcher not found. Install separately for full integration."
fi

# Create systemd service (optional)
read -p "Create systemd service for automatic scraping? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "Creating systemd service..."
    
    SERVICE_FILE="$HOME/.config/systemd/user/webreaper.service"
    mkdir -p "$(dirname "$SERVICE_FILE")"
    
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=WebReaper Scraper Service
After=network.target

[Service]
Type=simple
ExecStart=%h/.local/bin/webreaper dashboard
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
EOF
    
    systemctl --user daemon-reload
    print_success "Service created. Start with: systemctl --user start webreaper"
fi

# Final summary
echo ""
echo "=================================="
echo -e "${GREEN}✓ Installation Complete!${NC}"
echo "=================================="
echo ""
echo "Quick Start:"
echo "  webreaper crawl https://example.com              # Basic crawl"
echo "  webreaper crawl https://example.com --stealth    # Stealth mode"
echo "  webreaper dashboard                               # Launch UI"
echo "  webreaper security https://example.com           # Security scan"
echo "  webreaper blogwatcher https://blog.example.com   # RSS generator"
echo ""
echo "Configuration: ~/.config/webreaper/config.yaml"
echo "Output: ~/.local/share/webreaper/output/"
echo "Feeds: ~/.local/share/blogwatcher/feeds/"
echo ""
echo "Documentation: tools/webreaper/README.md"
echo ""
print_success "Happy scraping! 🕷️"
