#!/bin/sh
set -e

INSTALL_DIR="/opt/kai"
BIN_LINK="/usr/local/bin/kai"
REPO_URL="https://github.com/KairoPackage/kairo-repo.git"

echo "Installing Kai..."

if [ "$(id -u)" -eq 0 ]; then
    SUDO=""
else
    SUDO="sudo"
fi

$SUDO mkdir -p "$INSTALL_DIR"

$SUDO cp kai.py "$INSTALL_DIR/kai.py"
$SUDO chmod +x "$INSTALL_DIR/kai.py"

$SUDO ln -sfn "$INSTALL_DIR/kai.py" "$BIN_LINK"

$SUDO mkdir -p "$INSTALL_DIR/recipes"
$SUDO mkdir -p "$INSTALL_DIR/build"
$SUDO mkdir -p "$INSTALL_DIR/database"

echo "repo=$REPO_URL" | $SUDO tee "$INSTALL_DIR/kai.conf" >/dev/null

echo
echo "Kai installed successfully."
echo
echo "Run:"
echo "  kai sync"
echo "  kai available"
