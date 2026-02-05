#!/bin/bash
#
# zloth Installation Script
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/hampen2929/zloth/main/install.sh | bash
#
#   Or with options:
#   curl -fsSL https://raw.githubusercontent.com/hampen2929/zloth/main/install.sh | bash -s -- --dir ~/zloth
#
# Options:
#   --dir DIR         Installation directory (default: ./zloth)
#   --branch BRANCH   Git branch to checkout (default: main)
#   --tag TAG         Docker image tag to use (default: latest)
#   --build           Build images locally instead of pulling from registry
#   --api-port PORT   API server port (default: 8000)
#   --web-port PORT   Web UI port (default: 3000)
#   --no-start        Don't start services after installation
#   --upgrade         Upgrade existing installation
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
INSTALL_DIR="./zloth"
BRANCH="main"
API_PORT="8000"
WEB_PORT="3000"
START_SERVICES=true
UPGRADE_MODE=false
BUILD_LOCAL=false
IMAGE_TAG="latest"
REPO_URL="https://github.com/hampen2929/zloth.git"
IMAGE_REGISTRY="ghcr.io/hampen2929/zloth"

# Data paths (will be set in setup_directories)
WORKSPACES_PATH=""
DATA_PATH=""

# Print functions
print_banner() {
    echo -e "${BLUE}"
    echo "  ╔═══════════════════════════════════════════╗"
    echo "  ║              zloth installer              ║"
    echo "  ║   Multi-model Parallel Coding Agent       ║"
    echo "  ╚═══════════════════════════════════════════╝"
    echo -e "${NC}"
}

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
            --dir)
                INSTALL_DIR="$2"
                shift 2
                ;;
            --branch)
                BRANCH="$2"
                shift 2
                ;;
            --tag)
                IMAGE_TAG="$2"
                shift 2
                ;;
            --build)
                BUILD_LOCAL=true
                shift
                ;;
            --api-port)
                API_PORT="$2"
                shift 2
                ;;
            --web-port)
                WEB_PORT="$2"
                shift 2
                ;;
            --no-start)
                START_SERVICES=false
                shift
                ;;
            --upgrade)
                UPGRADE_MODE=true
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
    echo "Options:"
    echo "  --dir DIR         Installation directory (default: ./zloth)"
    echo "  --branch BRANCH   Git branch to checkout (default: main)"
    echo "  --tag TAG         Docker image tag to use (default: latest)"
    echo "  --build           Build images locally instead of pulling from registry"
    echo "  --api-port PORT   API server port (default: 8000)"
    echo "  --web-port PORT   Web UI port (default: 3000)"
    echo "  --no-start        Don't start services after installation"
    echo "  --upgrade         Upgrade existing installation"
    echo "  --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  # Install to default directory (pulls pre-built images)"
    echo "  curl -fsSL https://raw.githubusercontent.com/hampen2929/zloth/main/install.sh | bash"
    echo ""
    echo "  # Install with a specific version"
    echo "  curl -fsSL https://raw.githubusercontent.com/hampen2929/zloth/main/install.sh | bash -s -- --tag v1.0.0"
    echo ""
    echo "  # Build images locally instead of pulling"
    echo "  curl -fsSL https://raw.githubusercontent.com/hampen2929/zloth/main/install.sh | bash -s -- --build"
    echo ""
    echo "  # Install to custom directory"
    echo "  curl -fsSL https://raw.githubusercontent.com/hampen2929/zloth/main/install.sh | bash -s -- --dir ~/my-zloth"
    echo ""
    echo "  # Upgrade existing installation"
    echo "  cd zloth && curl -fsSL https://raw.githubusercontent.com/hampen2929/zloth/main/install.sh | bash -s -- --upgrade"
    echo ""
    echo "  # Use custom ports (if defaults are in use)"
    echo "  curl -fsSL https://raw.githubusercontent.com/hampen2929/zloth/main/install.sh | bash -s -- --api-port 8080 --web-port 3001"
}

# Check prerequisites
check_prerequisites() {
    print_step "Checking prerequisites..."

    local missing_deps=()

    # Check Docker
    if ! command -v docker &> /dev/null; then
        missing_deps+=("docker")
    else
        print_success "Docker found: $(docker --version)"
    fi

    # Check Docker Compose
    if docker compose version &> /dev/null; then
        print_success "Docker Compose found: $(docker compose version --short)"
    elif command -v docker-compose &> /dev/null; then
        print_success "Docker Compose (standalone) found: $(docker-compose --version)"
    else
        missing_deps+=("docker-compose")
    fi

    # Check Git
    if ! command -v git &> /dev/null; then
        missing_deps+=("git")
    else
        print_success "Git found: $(git --version)"
    fi

    # Check openssl (for key generation)
    if ! command -v openssl &> /dev/null; then
        print_warning "openssl not found. Will use alternative method for key generation."
    else
        print_success "OpenSSL found"
    fi

    # Check if Docker daemon is running
    if command -v docker &> /dev/null; then
        if ! docker info &> /dev/null; then
            print_error "Docker daemon is not running. Please start Docker and try again."
            exit 1
        fi
        print_success "Docker daemon is running"
    fi

    # Report missing dependencies
    if [ ${#missing_deps[@]} -ne 0 ]; then
        print_error "Missing required dependencies: ${missing_deps[*]}"
        echo ""
        echo "Please install the missing dependencies:"
        for dep in "${missing_deps[@]}"; do
            case $dep in
                docker)
                    echo "  Docker: https://docs.docker.com/get-docker/"
                    ;;
                docker-compose)
                    echo "  Docker Compose: https://docs.docker.com/compose/install/"
                    ;;
                git)
                    echo "  Git: https://git-scm.com/downloads"
                    ;;
            esac
        done
        exit 1
    fi

    echo ""
}

# Check if a port is available
check_port() {
    local port=$1
    if command -v ss &> /dev/null; then
        ! ss -tuln 2>/dev/null | grep -q ":${port} "
    elif command -v netstat &> /dev/null; then
        ! netstat -tuln 2>/dev/null | grep -q ":${port} "
    elif command -v lsof &> /dev/null; then
        ! lsof -i ":${port}" &>/dev/null
    else
        # If no tool available, assume port is free
        return 0
    fi
}

# Find next available port starting from given port
find_available_port() {
    local port=$1
    local max_attempts=10

    for ((i=0; i<max_attempts; i++)); do
        if check_port "$port"; then
            echo "$port"
            return 0
        fi
        ((port++))
    done

    # Return original if no free port found (will fail later with clear error)
    echo "$1"
    return 1
}

# Check and handle port conflicts
check_ports() {
    print_step "Checking port availability..."

    local api_available=true
    local web_available=true
    local suggested_api=""
    local suggested_web=""

    if ! check_port "$API_PORT"; then
        api_available=false
        print_warning "Port $API_PORT (API) is already in use"
        suggested_api=$(find_available_port "$((API_PORT + 1))")
    fi

    if ! check_port "$WEB_PORT"; then
        web_available=false
        print_warning "Port $WEB_PORT (Web) is already in use"
        suggested_web=$(find_available_port "$((WEB_PORT + 1))")
    fi

    if [ "$api_available" = false ] || [ "$web_available" = false ]; then
        echo ""
        print_warning "Some ports are already in use."
        echo ""

        # Show suggested ports
        if [ -n "$suggested_api" ]; then
            echo "  Suggested API port: $suggested_api"
        fi
        if [ -n "$suggested_web" ]; then
            echo "  Suggested Web port: $suggested_web"
        fi
        echo ""

        echo "Options:"
        echo "  [1] Use suggested ports automatically"
        echo "  [2] Cancel and specify ports manually"
        echo ""

        read -p "Choose option [1/2]: " -n 1 -r < /dev/tty
        echo

        case $REPLY in
            1)
                # Update ports to suggested values
                if [ -n "$suggested_api" ]; then
                    API_PORT="$suggested_api"
                    print_success "API port changed to $API_PORT"
                fi
                if [ -n "$suggested_web" ]; then
                    WEB_PORT="$suggested_web"
                    print_success "Web port changed to $WEB_PORT"
                fi
                ;;
            *)
                echo ""
                echo "To use custom ports, run:"
                echo "  $0 --api-port ${suggested_api:-8080} --web-port ${suggested_web:-3001}"
                echo ""
                print_error "Installation cancelled due to port conflicts."
                exit 1
                ;;
        esac
    else
        print_success "Ports $API_PORT (API) and $WEB_PORT (Web) are available"
    fi

    echo ""
}

# Generate encryption key
generate_encryption_key() {
    if command -v openssl &> /dev/null; then
        openssl rand -base64 32
    elif command -v python3 &> /dev/null; then
        python3 -c "import secrets; import base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
    elif command -v python &> /dev/null; then
        python -c "import secrets; import base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
    else
        # Fallback using /dev/urandom
        head -c 32 /dev/urandom | base64
    fi
}

# Clone or update repository
setup_repository() {
    if [ "$UPGRADE_MODE" = true ]; then
        print_step "Upgrading existing installation..."

        if [ ! -d ".git" ]; then
            print_error "Not a git repository. Cannot upgrade."
            exit 1
        fi

        # Stash any local changes
        if ! git diff --quiet; then
            print_warning "Local changes detected. Stashing..."
            git stash
        fi

        # Pull latest changes
        git fetch origin
        git checkout "$BRANCH"
        git pull origin "$BRANCH"

        print_success "Repository updated to latest $BRANCH"
    else
        print_step "Setting up repository..."

        if [ -d "$INSTALL_DIR" ]; then
            if [ -d "$INSTALL_DIR/.git" ]; then
                print_warning "Directory $INSTALL_DIR already exists."
                read -p "Update existing installation? [y/N] " -n 1 -r < /dev/tty
                echo
                if [[ $REPLY =~ ^[Yy]$ ]]; then
                    cd "$INSTALL_DIR"
                    UPGRADE_MODE=true
                    setup_repository
                    return
                else
                    print_error "Installation cancelled."
                    exit 1
                fi
            else
                print_error "Directory $INSTALL_DIR exists but is not a git repository."
                exit 1
            fi
        fi

        git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
        cd "$INSTALL_DIR"

        print_success "Repository cloned to $INSTALL_DIR"
    fi

    echo ""
}

# Replace a line in .env file safely (handles special characters in value)
# Usage: replace_env_var "VAR_NAME" "new_value"
replace_env_var() {
    local var_name="$1"
    local new_value="$2"
    local temp_file

    temp_file=$(mktemp)

    # Use awk to safely replace the line (avoids sed delimiter issues with base64)
    awk -v var="$var_name" -v val="$new_value" '
        BEGIN { FS=OFS="=" }
        $1 == var { print var, val; next }
        { print }
    ' .env > "$temp_file" && mv "$temp_file" .env
}

# Setup environment file
setup_environment() {
    print_step "Setting up environment configuration..."

    if [ -f ".env" ]; then
        print_warning ".env file already exists."

        # Check if encryption key is set
        if grep -q "^ZLOTH_ENCRYPTION_KEY=your-encryption-key-here" .env 2>/dev/null; then
            print_warning "Encryption key not configured. Generating new key..."
            local new_key
            new_key=$(generate_encryption_key)
            replace_env_var "ZLOTH_ENCRYPTION_KEY" "$new_key"
            print_success "Encryption key generated and saved"
        else
            print_success "Using existing .env configuration"
        fi
    else
        cp .env.example .env

        # Generate and set encryption key
        local encryption_key
        encryption_key=$(generate_encryption_key)

        # Replace placeholder with actual key (use awk to avoid sed delimiter issues)
        replace_env_var "ZLOTH_ENCRYPTION_KEY" "$encryption_key"

        print_success "Environment file created with encryption key"
    fi

    # Save custom ports to .env if they differ from defaults
    if [ "$API_PORT" != "8000" ] || [ "$WEB_PORT" != "3000" ]; then
        # Remove old port settings if they exist
        grep -v "^ZLOTH_API_PORT=" .env > .env.tmp && mv .env.tmp .env 2>/dev/null || true
        grep -v "^ZLOTH_WEB_PORT=" .env > .env.tmp && mv .env.tmp .env 2>/dev/null || true

        # Add new port settings
        echo "" >> .env
        echo "# Custom ports (set by installer)" >> .env
        echo "ZLOTH_API_PORT=$API_PORT" >> .env
        echo "ZLOTH_WEB_PORT=$WEB_PORT" >> .env

        print_success "Custom ports saved to .env (API: $API_PORT, Web: $WEB_PORT)"
    fi

    echo ""
}

# Ensure docker-compose.yml supports custom ports
patch_docker_compose() {
    # Check if docker-compose.yml already supports custom ports
    if grep -q 'ZLOTH_API_PORT' docker-compose.yml 2>/dev/null; then
        return 0
    fi

    print_step "Patching docker-compose.yml for custom port support..."

    # Backup original
    cp docker-compose.yml docker-compose.yml.bak

    # Patch the ports using sed
    # Replace "8000:8000" with "${ZLOTH_API_PORT:-8000}:8000"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' 's/"8000:8000"/"${ZLOTH_API_PORT:-8000}:8000"/' docker-compose.yml
        sed -i '' 's/"3000:3000"/"${ZLOTH_WEB_PORT:-3000}:3000"/' docker-compose.yml
    else
        sed -i 's/"8000:8000"/"${ZLOTH_API_PORT:-8000}:8000"/' docker-compose.yml
        sed -i 's/"3000:3000"/"${ZLOTH_WEB_PORT:-3000}:3000"/' docker-compose.yml
    fi

    print_success "docker-compose.yml patched for custom ports"
}

# Create required directories
setup_directories() {
    print_step "Setting up data directories..."

    local home_zloth="$HOME/.zloth"

    # Always use ~/.zloth for data persistence
    if [ -d "$home_zloth" ]; then
        print_success "Found existing ~/.zloth directory"
    else
        print_success "Creating ~/.zloth directory"
    fi

    # Ensure ~/.zloth and subdirectories exist
    mkdir -p "$home_zloth/workspaces"
    mkdir -p "$home_zloth/data"

    WORKSPACES_PATH="$home_zloth/workspaces"
    DATA_PATH="$home_zloth/data"

    print_success "Data directory: $home_zloth"

    echo ""
}

# Generate docker-compose.prod.yml for pre-built images
generate_compose_prod() {
    print_step "Configuring pre-built images from registry..."

    cat > docker-compose.prod.yml << EOF
# Auto-generated by install.sh
# This file configures zloth to use pre-built images from GitHub Container Registry
version: '3.8'

services:
  api:
    image: ${IMAGE_REGISTRY}/api:${IMAGE_TAG}
    ports:
      - "\${ZLOTH_API_PORT:-8000}:8000"
    volumes:
      - ${WORKSPACES_PATH}:/app/workspaces
      - ${DATA_PATH}:/app/data
    environment:
      - ZLOTH_HOST=0.0.0.0
      - ZLOTH_PORT=8000
      - ZLOTH_DEBUG=\${ZLOTH_DEBUG:-false}
      - ZLOTH_LOG_LEVEL=\${ZLOTH_LOG_LEVEL:-INFO}
      - ZLOTH_ENCRYPTION_KEY=\${ZLOTH_ENCRYPTION_KEY}
      - ZLOTH_GITHUB_APP_ID=\${ZLOTH_GITHUB_APP_ID:-}
      - ZLOTH_GITHUB_APP_PRIVATE_KEY=\${ZLOTH_GITHUB_APP_PRIVATE_KEY:-}
      - ZLOTH_GITHUB_APP_INSTALLATION_ID=\${ZLOTH_GITHUB_APP_INSTALLATION_ID:-}
      - ZLOTH_WORKSPACES_DIR=/app/workspaces
      - ZLOTH_DATA_DIR=/app/data
    restart: unless-stopped

  web:
    image: ${IMAGE_REGISTRY}/web:${IMAGE_TAG}
    ports:
      - "\${ZLOTH_WEB_PORT:-3000}:3000"
    environment:
      - API_URL=http://api:8000
    depends_on:
      - api
    restart: unless-stopped
EOF

    print_success "Data mounted from: ~/.zloth"
    print_success "Using images: ${IMAGE_REGISTRY}/api:${IMAGE_TAG}, ${IMAGE_REGISTRY}/web:${IMAGE_TAG}"
}

# Start services
start_services() {
    if [ "$START_SERVICES" = false ]; then
        print_step "Skipping service startup (--no-start specified)"
        return
    fi

    # Set port environment variables for docker-compose
    export ZLOTH_API_PORT="$API_PORT"
    export ZLOTH_WEB_PORT="$WEB_PORT"

    # Determine compose command
    local compose_cmd
    if docker compose version &> /dev/null; then
        compose_cmd="docker compose"
    else
        compose_cmd="docker-compose"
    fi

    if [ "$BUILD_LOCAL" = true ]; then
        print_step "Building and starting zloth services locally..."
        ZLOTH_API_PORT="$API_PORT" ZLOTH_WEB_PORT="$WEB_PORT" $compose_cmd up -d --build
    else
        # Generate compose file for pre-built images
        generate_compose_prod

        print_step "Pulling and starting zloth services..."
        ZLOTH_API_PORT="$API_PORT" ZLOTH_WEB_PORT="$WEB_PORT" $compose_cmd -f docker-compose.prod.yml pull
        ZLOTH_API_PORT="$API_PORT" ZLOTH_WEB_PORT="$WEB_PORT" $compose_cmd -f docker-compose.prod.yml up -d
    fi

    print_success "Services started"
    echo ""
}

# Wait for services to be ready
wait_for_services() {
    if [ "$START_SERVICES" = false ]; then
        return
    fi

    print_step "Waiting for services to be ready..."

    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -sf "http://localhost:${API_PORT}/health" > /dev/null 2>&1; then
            print_success "API server is ready"
            break
        fi

        if [ $attempt -eq $max_attempts ]; then
            print_warning "API server health check timed out. Services may still be starting."
            break
        fi

        echo -n "."
        sleep 2
        ((attempt++))
    done

    echo ""
}

# Print completion message
print_completion() {
    echo -e "${GREEN}"
    echo "  ╔═══════════════════════════════════════════╗"
    echo "  ║       zloth installation complete!        ║"
    echo "  ╚═══════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""

    if [ "$START_SERVICES" = true ]; then
        echo "  Access zloth at:"
        echo "    Web UI:  http://localhost:${WEB_PORT}"
        echo "    API:     http://localhost:${API_PORT}"
        echo ""
        if [ "$BUILD_LOCAL" = true ]; then
            echo "  Mode: Local build"
        else
            echo "  Mode: Pre-built images (${IMAGE_TAG})"
        fi
        echo ""
    fi

    echo "  Next steps:"
    echo "    1. Open http://localhost:${WEB_PORT} in your browser"
    echo "    2. Go to Settings and add your LLM API keys"
    echo "    3. (Optional) Configure GitHub App for PR operations"
    echo ""

    # Show appropriate compose commands based on mode
    if [ "$BUILD_LOCAL" = true ]; then
        echo "  Useful commands:"
        echo "    docker compose logs -f     # View logs"
        echo "    docker compose down        # Stop services"
        echo "    docker compose up -d       # Start services"
    else
        echo "  Useful commands:"
        echo "    docker compose -f docker-compose.prod.yml logs -f   # View logs"
        echo "    docker compose -f docker-compose.prod.yml down      # Stop services"
        echo "    docker compose -f docker-compose.prod.yml up -d     # Start services"
    fi
    echo ""
    echo "  Documentation: https://github.com/hampen2929/zloth"
    echo ""
}

# Main installation flow
main() {
    print_banner
    parse_args "$@"
    check_prerequisites

    # Check port availability before starting (only if services will be started)
    if [ "$START_SERVICES" = true ]; then
        check_ports
    fi

    if [ "$UPGRADE_MODE" = false ]; then
        setup_repository
    else
        # Already in the target directory for upgrade
        setup_repository
    fi

    setup_environment
    setup_directories

    # Patch docker-compose.yml if custom ports are used
    if [ "$API_PORT" != "8000" ] || [ "$WEB_PORT" != "3000" ]; then
        patch_docker_compose
    fi

    start_services
    wait_for_services
    print_completion
}

# Run main function
main "$@"
