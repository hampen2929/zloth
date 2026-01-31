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
START_SERVICES=true
UPGRADE_MODE=false
REPO_URL="https://github.com/hampen2929/zloth.git"

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
    echo "  --no-start        Don't start services after installation"
    echo "  --upgrade         Upgrade existing installation"
    echo "  --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  # Install to default directory"
    echo "  curl -fsSL https://raw.githubusercontent.com/hampen2929/zloth/main/install.sh | bash"
    echo ""
    echo "  # Install to custom directory"
    echo "  curl -fsSL https://raw.githubusercontent.com/hampen2929/zloth/main/install.sh | bash -s -- --dir ~/my-zloth"
    echo ""
    echo "  # Upgrade existing installation"
    echo "  cd zloth && curl -fsSL https://raw.githubusercontent.com/hampen2929/zloth/main/install.sh | bash -s -- --upgrade"
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
                read -p "Update existing installation? [y/N] " -n 1 -r
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

    echo ""
}

# Create required directories
setup_directories() {
    print_step "Creating required directories..."

    mkdir -p workspaces
    mkdir -p data

    print_success "Directories created: workspaces/, data/"
    echo ""
}

# Start services
start_services() {
    if [ "$START_SERVICES" = false ]; then
        print_step "Skipping service startup (--no-start specified)"
        return
    fi

    print_step "Starting zloth services..."

    # Use docker compose (v2) or docker-compose (v1)
    if docker compose version &> /dev/null; then
        docker compose up -d --build
    else
        docker-compose up -d --build
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
        if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
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
        echo "    Web UI:  http://localhost:3000"
        echo "    API:     http://localhost:8000"
        echo ""
    fi

    echo "  Next steps:"
    echo "    1. Open http://localhost:3000 in your browser"
    echo "    2. Go to Settings and add your LLM API keys"
    echo "    3. (Optional) Configure GitHub App for PR operations"
    echo ""
    echo "  Useful commands:"
    echo "    docker compose logs -f     # View logs"
    echo "    docker compose down        # Stop services"
    echo "    docker compose up -d       # Start services"
    echo ""
    echo "  Documentation: https://github.com/hampen2929/zloth"
    echo ""
}

# Main installation flow
main() {
    print_banner
    parse_args "$@"
    check_prerequisites

    if [ "$UPGRADE_MODE" = false ]; then
        setup_repository
    else
        # Already in the target directory for upgrade
        setup_repository
    fi

    setup_environment
    setup_directories
    start_services
    wait_for_services
    print_completion
}

# Run main function
main "$@"
