#!/bin/bash
# Diagnostic script to test MediaMTX API endpoints

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

API="http://127.0.0.1:9997"
echo -e "${BLUE}=== MediaMTX API Diagnostic ===${NC}\n"

# Test connectivity
echo -e "${YELLOW}1. Testing API connectivity...${NC}"
if curl -s -f "$API/v3/config/global/get" > /dev/null; then
    echo -e "${GREEN}✓ API is reachable${NC}\n"
else
    echo -e "${RED}✗ API is not reachable at $API${NC}"
    exit 1
fi

# List paths
echo -e "${YELLOW}2. Listing paths:${NC}"
curl -s "$API/v3/paths/list" | jq . || echo "No paths or error"
echo

# List recordings
echo -e "${YELLOW}3. Listing recordings:${NC}"
curl -s "$API/v3/recordings/list?itemsPerPage=100" | jq .
echo

# Try to get details for each recording
echo -e "${YELLOW}4. Recording details:${NC}"
RECORDINGS=$(curl -s "$API/v3/recordings/list?itemsPerPage=100" | jq -r '.items[].name' 2>/dev/null || echo "")
if [ -z "$RECORDINGS" ]; then
    echo "No recordings found"
else
    echo "$RECORDINGS" | while read -r name; do
        echo -e "\n${BLUE}Recording: $name${NC}"
        curl -s "$API/v3/recordings/get/$name" | jq '.'
    done
fi

echo -e "\n${BLUE}=== Diagnostic Complete ===${NC}"
