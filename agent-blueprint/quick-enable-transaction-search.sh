#!/bin/bash

################################################################################
# Quick Start: Enable Transaction Search
#
# This script automates the deployment of Transaction Search prerequisites
# and enables the feature.
#
# Usage:
#   ./quick-enable-transaction-search.sh [--profile PROFILE] [--region REGION]
################################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Parse arguments
AWS_PROFILE="${AWS_PROFILE:-}"
AWS_REGION="${AWS_REGION:-us-east-1}"

while [[ $# -gt 0 ]]; do
  case $1 in
    --profile)
      AWS_PROFILE="$2"
      shift 2
      ;;
    --region)
      AWS_REGION="$2"
      shift 2
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      exit 1
      ;;
  esac
done

echo -e "${BLUE}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Transaction Search Quick Setup                      ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# Step 1: Deploy Runtime Stack with updated IAM permissions
echo -e "${YELLOW}→ Step 1: Deploying Runtime Stack with Transaction Search prerequisites...${NC}"
echo ""

cd "$(dirname "$0")"

DEPLOY_CMD="./deploy.sh --runtime"
if [[ -n "$AWS_PROFILE" ]]; then
  export AWS_PROFILE
fi

echo -e "${BLUE}Running: $DEPLOY_CMD${NC}"
echo ""

if ! $DEPLOY_CMD; then
  echo -e "${RED}✗ Deployment failed${NC}"
  exit 1
fi

echo ""
echo -e "${GREEN}✓ Runtime Stack deployed successfully${NC}"
echo ""

# Step 2: Enable Transaction Search
echo -e "${YELLOW}→ Step 2: Enabling Transaction Search...${NC}"
echo ""

ENABLE_CMD="./enable-transaction-search.sh --region $AWS_REGION"
if [[ -n "$AWS_PROFILE" ]]; then
  ENABLE_CMD="$ENABLE_CMD --profile $AWS_PROFILE"
fi

echo -e "${BLUE}Running: $ENABLE_CMD${NC}"
echo ""

if ! $ENABLE_CMD; then
  echo -e "${RED}✗ Transaction Search enablement failed${NC}"
  exit 1
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Transaction Search Setup Complete! ✓                ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}View Transaction Search in the CloudWatch console:${NC}"
echo -e "${BLUE}https://console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#application-signals:transaction-search${NC}"
echo ""
