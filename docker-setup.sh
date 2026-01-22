#!/bin/bash
# Quick Docker Setup Script for BunTool
# This script automates Docker setup and deployment

set -e

echo "========================================="
echo "BunTool Docker Setup Script"
echo "========================================="

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Docker is not installed. Please install Docker first.${NC}"
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

echo -e "${GREEN}✓ Docker found${NC}"

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}Docker Compose is not installed. Please install Docker Compose.${NC}"
    echo "Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "${GREEN}✓ Docker Compose found${NC}"

# Get current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${BLUE}Working directory: $SCRIPT_DIR${NC}"

# Build the Docker image
echo -e "${BLUE}Building Docker image...${NC}"
docker build -t buntool:latest .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Image built successfully${NC}"
else
    echo -e "${YELLOW}✗ Image build failed${NC}"
    exit 1
fi

# Get user input for action
echo ""
echo "What would you like to do?"
echo "1) Start container with Docker Compose"
echo "2) Start container with Docker CLI"
echo "3) Just build image (no startup)"
echo ""
read -p "Enter choice (1-3): " choice

case $choice in
    1)
        echo -e "${BLUE}Starting with Docker Compose...${NC}"
        docker-compose up -d
        sleep 3
        if docker ps | grep -q buntool; then
            echo -e "${GREEN}✓ Container started successfully${NC}"
            echo ""
            echo "Application is running at:"
            echo -e "${BLUE}http://localhost:7001/bookmark_tool${NC}"
            echo ""
            echo "To stop: docker-compose down"
            echo "To view logs: docker-compose logs -f"
        else
            echo -e "${YELLOW}✗ Container failed to start${NC}"
            docker logs buntool-test 2>/dev/null || true
        fi
        ;;
    2)
        echo -e "${BLUE}Starting with Docker CLI...${NC}"
        docker run -d \
            --name buntool \
            -p 7001:7001 \
            -v buntool_tempfiles:/app/tempfiles \
            -v buntool_logs:/app/logs \
            buntool:latest
        
        sleep 3
        if docker ps | grep -q buntool; then
            echo -e "${GREEN}✓ Container started successfully${NC}"
            echo ""
            echo "Application is running at:"
            echo -e "${BLUE}http://localhost:7001/bookmark_tool${NC}"
            echo ""
            echo "To stop: docker stop buntool"
            echo "To view logs: docker logs -f buntool"
        else
            echo -e "${YELLOW}✗ Container failed to start${NC}"
            docker logs buntool 2>/dev/null || true
        fi
        ;;
    3)
        echo -e "${GREEN}✓ Image build complete${NC}"
        echo "To start the container, run:"
        echo "  docker-compose up -d"
        echo "or"
        echo "  docker run -d -p 7001:7001 buntool:latest"
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "========================================="
echo "Setup complete!"
echo "========================================="
