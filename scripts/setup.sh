#!/bin/bash

# Expense Management System Setup Script
# This script sets up the complete system for development or production

set -e

echo "🚀 Setting up Expense Management System..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    print_success "Docker and Docker Compose are installed"
}

# Check if .env file exists
setup_environment() {
    if [ ! -f .env ]; then
        print_warning ".env file not found. Creating from template..."
        cp env.example .env
        print_warning "Please edit .env file with your configuration before continuing."
        print_warning "Required settings:"
        print_warning "  - SMTP_USERNAME and SMTP_PASSWORD for email notifications"
        print_warning "  - EMAIL_FROM for sender address"
        print_warning "  - SECRET_KEY for JWT tokens (change in production!)"
        
        read -p "Press Enter to continue after editing .env file..."
    else
        print_success ".env file found"
    fi
}

# Create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    
    mkdir -p backend/uploads
    mkdir -p nginx/ssl
    mkdir -p logs
    
    print_success "Directories created"
}

# Pull Docker images
pull_images() {
    print_status "Pulling Docker images..."
    docker-compose pull
    print_success "Docker images pulled"
}

# Build custom images
build_images() {
    print_status "Building custom images..."
    docker-compose build
    print_success "Custom images built"
}

# Start services
start_services() {
    print_status "Starting services..."
    docker-compose up -d
    
    print_status "Waiting for services to be ready..."
    sleep 10
    
    # Check if services are healthy
    if docker-compose ps | grep -q "unhealthy"; then
        print_warning "Some services are not healthy. Checking logs..."
        docker-compose logs --tail=50
    else
        print_success "All services are running"
    fi
}

# Run database migrations
run_migrations() {
    print_status "Running database migrations..."
    docker-compose exec backend alembic upgrade head
    print_success "Database migrations completed"
}

# Create initial data
create_initial_data() {
    print_status "Creating initial data..."
    
    # Create default currencies
    docker-compose exec postgres psql -U expense_user -d expense_management -c "
        INSERT INTO currency_rates (from_currency, to_currency, rate, rate_date) VALUES
        ('USD', 'USD', 1.000000, CURRENT_DATE),
        ('EUR', 'USD', 1.050000, CURRENT_DATE),
        ('GBP', 'USD', 1.250000, CURRENT_DATE),
        ('JPY', 'USD', 0.007500, CURRENT_DATE),
        ('CAD', 'USD', 0.750000, CURRENT_DATE),
        ('AUD', 'USD', 0.650000, CURRENT_DATE),
        ('CHF', 'USD', 1.100000, CURRENT_DATE),
        ('CNY', 'USD', 0.140000, CURRENT_DATE),
        ('INR', 'USD', 0.012000, CURRENT_DATE),
        ('BRL', 'USD', 0.200000, CURRENT_DATE)
        ON CONFLICT (from_currency, to_currency, rate_date) DO NOTHING;
    "
    
    print_success "Initial data created"
}

# Display system information
display_info() {
    echo ""
    echo "🎉 Expense Management System Setup Complete!"
    echo ""
    echo "📋 System Information:"
    echo "  Frontend:     http://localhost:3000"
    echo "  Backend API:  http://localhost:8000"
    echo "  API Docs:     http://localhost:8000/docs"
    echo "  Database:     localhost:5432"
    echo "  Redis:        localhost:6379"
    echo ""
    echo "🔧 Management Commands:"
    echo "  View logs:    docker-compose logs -f"
    echo "  Stop system:  docker-compose down"
    echo "  Restart:      docker-compose restart"
    echo "  Update:       docker-compose pull && docker-compose up -d"
    echo ""
    echo "📚 Next Steps:"
    echo "  1. Access the frontend at http://localhost:3000"
    echo "  2. Create your first company (admin user)"
    echo "  3. Set up expense categories"
    echo "  4. Configure approval rules"
    echo "  5. Invite users to the system"
    echo ""
    print_warning "Remember to:"
    print_warning "  - Change the SECRET_KEY in production"
    print_warning "  - Configure proper SMTP settings for email notifications"
    print_warning "  - Set up SSL certificates for production deployment"
    echo ""
}

# Main setup function
main() {
    echo "Starting Expense Management System setup..."
    echo ""
    
    check_docker
    setup_environment
    create_directories
    pull_images
    build_images
    start_services
    run_migrations
    create_initial_data
    display_info
    
    print_success "Setup completed successfully!"
}

# Handle script arguments
case "${1:-}" in
    "dev")
        print_status "Setting up for development..."
        export COMPOSE_FILE=docker-compose.yml:docker-compose.dev.yml
        main
        ;;
    "prod")
        print_status "Setting up for production..."
        export COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml
        main
        ;;
    "stop")
        print_status "Stopping all services..."
        docker-compose down
        print_success "Services stopped"
        ;;
    "restart")
        print_status "Restarting all services..."
        docker-compose restart
        print_success "Services restarted"
        ;;
    "logs")
        docker-compose logs -f
        ;;
    "update")
        print_status "Updating system..."
        docker-compose pull
        docker-compose up -d
        print_success "System updated"
        ;;
    "clean")
        print_warning "Cleaning up system (this will remove all data)..."
        read -p "Are you sure? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker-compose down -v
            docker system prune -f
            print_success "System cleaned"
        else
            print_status "Cleanup cancelled"
        fi
        ;;
    *)
        print_status "Setting up for development..."
        main
        ;;
esac

