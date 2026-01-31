#!/bin/bash
#
# zloth Uninstallation Script
#
# Usage:
#   ./uninstall.sh [OPTIONS]
#
# Options:
#   --keep-data       Keep workspaces and data directories
#   --yes             Skip confirmation prompts
#   --help            Show this help message
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
KEEP_DATA=false
SKIP_CONFIRM=false

# Print functions
print_step() {
    echo -e "${BLUE}==>${NC} $1"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Parse arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --keep-data)
                KEEP_DATA=true
                shift
                ;;
            --yes|-y)
                SKIP_CONFIRM=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Uninstall zloth and optionally remove all data."
    echo ""
    echo "Options:"
    echo "  --keep-data       Keep workspaces and data directories"
    echo "  --yes, -y         Skip confirmation prompts"
    echo "  --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  # Uninstall with confirmation"
    echo "  ./uninstall.sh"
    echo ""
    echo "  # Uninstall but keep data"
    echo "  ./uninstall.sh --keep-data"
    echo ""
    echo "  # Uninstall without prompts"
    echo "  ./uninstall.sh --yes"
}

# Check if we're in zloth directory
check_directory() {
    if [ ! -f "docker-compose.yml" ] || [ ! -d "apps/api" ]; then
        print_error "This script must be run from the zloth installation directory."
        exit 1
    fi
}

# Confirm uninstallation
confirm_uninstall() {
    if [ "$SKIP_CONFIRM" = true ]; then
        return 0
    fi

    echo ""
    print_warning "This will:"
    echo "  - Stop all zloth Docker containers"
    echo "  - Remove Docker images built for zloth"
    if [ "$KEEP_DATA" = false ]; then
        echo "  - Delete workspaces/ directory (cloned repositories)"
        echo "  - Delete data/ directory (SQLite database)"
    else
        echo "  - Keep workspaces/ and data/ directories"
    fi
    echo ""

    read -p "Are you sure you want to continue? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Uninstallation cancelled."
        exit 0
    fi
}

# Stop Docker containers
stop_containers() {
    print_step "Stopping Docker containers..."

    # Try all compose files
    local compose_files=("docker-compose.yml" "docker-compose.worker.yml" "docker-compose.prod.yml")

    for compose_file in "${compose_files[@]}"; do
        if [ -f "$compose_file" ]; then
            if docker compose -f "$compose_file" ps -q 2>/dev/null | grep -q .; then
                docker compose -f "$compose_file" down --remove-orphans 2>/dev/null || true
            fi
        fi
    done

    print_success "Containers stopped"
}

# Remove Docker images
remove_images() {
    print_step "Removing Docker images..."

    # Get project name from directory
    local project_name
    project_name=$(basename "$(pwd)" | tr '[:upper:]' '[:lower:]' | tr -d '.-')

    # Remove images with project prefix
    local images
    images=$(docker images --filter "reference=${project_name}*" -q 2>/dev/null)

    if [ -n "$images" ]; then
        echo "$images" | xargs docker rmi -f 2>/dev/null || true
        print_success "Docker images removed"
    else
        print_success "No Docker images to remove"
    fi
}

# Remove Docker volumes
remove_volumes() {
    print_step "Removing Docker volumes..."

    local project_name
    project_name=$(basename "$(pwd)" | tr '[:upper:]' '[:lower:]' | tr -d '.-')

    # Remove volumes with project prefix
    local volumes
    volumes=$(docker volume ls --filter "name=${project_name}" -q 2>/dev/null)

    if [ -n "$volumes" ]; then
        echo "$volumes" | xargs docker volume rm -f 2>/dev/null || true
        print_success "Docker volumes removed"
    else
        print_success "No Docker volumes to remove"
    fi
}

# Remove data directories
remove_data() {
    if [ "$KEEP_DATA" = true ]; then
        print_step "Keeping data directories (--keep-data specified)"
        return
    fi

    print_step "Removing data directories..."

    if [ -d "workspaces" ]; then
        rm -rf workspaces
        print_success "Removed workspaces/"
    fi

    if [ -d "data" ]; then
        rm -rf data
        print_success "Removed data/"
    fi
}

# Remove .env file
remove_env() {
    if [ -f ".env" ]; then
        if [ "$SKIP_CONFIRM" = true ]; then
            rm -f .env
            print_success "Removed .env"
        else
            read -p "Remove .env file (contains encryption key)? [y/N] " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                rm -f .env
                print_success "Removed .env"
            else
                print_warning "Kept .env file"
            fi
        fi
    fi
}

# Print completion message
print_completion() {
    echo ""
    echo -e "${GREEN}zloth has been uninstalled.${NC}"
    echo ""

    if [ "$KEEP_DATA" = true ]; then
        echo "Data directories were preserved:"
        [ -d "workspaces" ] && echo "  - workspaces/"
        [ -d "data" ] && echo "  - data/"
        echo ""
    fi

    echo "To completely remove zloth, delete this directory:"
    echo "  rm -rf $(pwd)"
    echo ""
}

# Main uninstallation flow
main() {
    echo -e "${BLUE}zloth Uninstaller${NC}"
    echo ""

    parse_args "$@"
    check_directory
    confirm_uninstall
    stop_containers
    remove_images
    remove_volumes
    remove_data
    remove_env
    print_completion
}

# Run main function
main "$@"
