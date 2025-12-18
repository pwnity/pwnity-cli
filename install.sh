#!/bin/bash

#
# # Project: https://github.com/pwnity/pwnity-cli
# # Copyright 2025 pwnity
#

# --- pwnity Installer ---
# This script sets up the necessary virtual environment and installs dependencies.

set -e

# --- Style Definitions ---
BLUE='\033[0;94m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

# --- Helper Functions ---
print_header() {
    echo -e "\n${BLUE}██████╗ ██╗    ██╗███╗   ██╗██╗████████╗██╗   ██╗${NC}"
    echo -e "${BLUE}██╔══██╗██║    ██║████╗  ██║██║╚══██╔══╝╚██╗ ██╔╝${NC}"
    echo -e "${BLUE}██████╔╝██║ █╗ ██║██╔██╗ ██║██║   ██║    ╚████╔╝ ${NC}"
    echo -e "${BLUE}██╔═══╝ ██║███╗██║██║╚██╗██║██║   ██║     ╚██╔╝  ${NC}"
    echo -e "${BLUE}██║     ╚███╔███╔╝██║ ╚████║██║   ██║      ██║   ${NC}"
    echo -e "${BLUE}╚═╝      ╚══╝╚══╝ ╚═╝  ╚═══╝╚═╝   ╚═╝      ╚═╝   ${NC}"
    echo -e "${DIM}                             Installer${NC}\n"
}

print_info() {
    echo -e "${BLUE}[*]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[+]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[-]${NC} $1" >&2
    exit 1
}

# --- Main Installation Logic ---

VENV_DIR="venv"
REQUIREMENTS_FILE="requirements.txt"

print_header

print_info "Starting pwnity setup..."

# 1. Check for Python 3 and venv module
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed. Please install Python 3 and try again."
fi

if ! python3 -c "import venv" &> /dev/null; then
    print_error "The 'venv' module is not available. Please install the 'python3-venv' package (or equivalent for your OS)."
fi

# 2. Create Virtual Environment
if [ -d "$VENV_DIR" ]; then
    print_warning "Virtual environment '$VENV_DIR' already exists. Skipping creation."
else
    print_info "Creating Python virtual environment in './$VENV_DIR'..."
    python3 -m venv "$VENV_DIR"
    print_success "Virtual environment created."
fi

# 3. Install Dependencies
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    print_error "'$REQUIREMENTS_FILE' not found. Cannot install dependencies."
fi

print_info "Installing dependencies from '$REQUIREMENTS_FILE'..."
"$VENV_DIR/bin/pip" install -r "$REQUIREMENTS_FILE"
print_success "All dependencies installed successfully."

echo -e "\n${BOLD}🎉 Setup complete!${NC}\n"
echo -e "To activate the environment and run the CLI, use the following commands:"
echo -e "  ${YELLOW}source $VENV_DIR/bin/activate${NC}"
echo -e "  ${YELLOW}./pwnity${NC}\n"