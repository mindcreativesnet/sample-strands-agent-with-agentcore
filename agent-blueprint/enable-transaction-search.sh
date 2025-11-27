#!/bin/bash

################################################################################
# Enable CloudWatch Transaction Search for AgentCore Runtime
# 
# This script enables Transaction Search by:
# 1. Creating a CloudWatch Logs resource policy for X-Ray
# 2. Configuring trace segment destination to CloudWatch Logs
# 3. Setting indexing rules for span sampling
# 4. Verifying the configuration
#
# Prerequisites:
# - AWS CLI configured with appropriate credentials
# - Transaction Search IAM permissions already deployed via CDK
# - AWS profile set (via AWS_PROFILE or --profile flag)
#
# Usage:
#   ./enable-transaction-search.sh [OPTIONS]
#
# Options:
#   --region REGION          AWS region (default: us-east-1)
#   --sampling PERCENTAGE    Percentage of spans to index (default: 1)
#   --profile PROFILE        AWS CLI profile to use
#   --help                   Show this help message
################################################################################

set -e

# Default values
AWS_REGION="${AWS_REGION:-us-east-1}"
SAMPLING_PERCENTAGE=1
AWS_PROFILE="${AWS_PROFILE:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --region)
      AWS_REGION="$2"
      shift 2
      ;;
    --sampling)
      SAMPLING_PERCENTAGE="$2"
      shift 2
      ;;
    --profile)
      AWS_PROFILE="$2"
      shift 2
      ;;
    --help)
      grep "^#" "$0" | grep -v "#!/bin/bash" | sed 's/^# \?//'
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

# Build AWS CLI command prefix
AWS_CMD="aws"
if [[ -n "$AWS_PROFILE" ]]; then
  AWS_CMD="aws --profile $AWS_PROFILE"
fi

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Enable CloudWatch Transaction Search for AgentCore Runtime  ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Get AWS Account ID
echo -e "${YELLOW}→ Getting AWS Account ID...${NC}"
ACCOUNT_ID=$($AWS_CMD sts get-caller-identity --query Account --output text --region "$AWS_REGION")
echo -e "${GREEN}✓ Account ID: $ACCOUNT_ID${NC}"
echo ""

################################################################################
# Step 1: Create CloudWatch Logs Resource Policy
################################################################################

echo -e "${YELLOW}→ Step 1: Creating CloudWatch Logs resource policy for X-Ray...${NC}"

POLICY_NAME="TransactionSearchXRayAccess"
POLICY_DOCUMENT=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "TransactionSearchXRayAccess",
      "Effect": "Allow",
      "Principal": {
        "Service": "xray.amazonaws.com"
      },
      "Action": "logs:PutLogEvents",
      "Resource": [
        "arn:aws:logs:${AWS_REGION}:${ACCOUNT_ID}:log-group:aws/spans:*",
        "arn:aws:logs:${AWS_REGION}:${ACCOUNT_ID}:log-group:/aws/application-signals/data:*"
      ],
      "Condition": {
        "ArnLike": {
          "aws:SourceArn": "arn:aws:xray:${AWS_REGION}:${ACCOUNT_ID}:*"
        },
        "StringEquals": {
          "aws:SourceAccount": "${ACCOUNT_ID}"
        }
      }
    }
  ]
}
EOF
)

# Check if policy already exists
EXISTING_POLICIES=$($AWS_CMD logs describe-resource-policies --region "$AWS_REGION" --query "resourcePolicies[?policyName=='$POLICY_NAME'].policyName" --output text 2>/dev/null || echo "")

if [[ -n "$EXISTING_POLICIES" ]]; then
  echo -e "${YELLOW}  Policy '$POLICY_NAME' already exists. Updating...${NC}"
fi

$AWS_CMD logs put-resource-policy \
  --policy-name "$POLICY_NAME" \
  --policy-document "$POLICY_DOCUMENT" \
  --region "$AWS_REGION" > /dev/null

echo -e "${GREEN}✓ CloudWatch Logs resource policy created/updated${NC}"
echo ""

################################################################################
# Step 2: Configure Trace Segment Destination
################################################################################

echo -e "${YELLOW}→ Step 2: Configuring trace segment destination to CloudWatch Logs...${NC}"

# Check current destination
CURRENT_DEST=$($AWS_CMD xray get-trace-segment-destination --region "$AWS_REGION" --query "Destination" --output text 2>/dev/null || echo "XRay")

if [[ "$CURRENT_DEST" == "CloudWatchLogs" ]]; then
  echo -e "${YELLOW}  Trace segment destination is already set to CloudWatch Logs${NC}"
else
  $AWS_CMD xray update-trace-segment-destination \
    --destination CloudWatchLogs \
    --region "$AWS_REGION" > /dev/null
  echo -e "${GREEN}✓ Trace segment destination updated to CloudWatch Logs${NC}"
fi
echo ""

################################################################################
# Step 3: Configure Indexing Rules (Sampling Percentage)
################################################################################

echo -e "${YELLOW}→ Step 3: Configuring indexing rules (sampling: ${SAMPLING_PERCENTAGE}%)...${NC}"

# Update the default indexing rule
$AWS_CMD xray update-indexing-rule \
  --name "Default" \
  --rule "{\"Probabilistic\": {\"DesiredSamplingPercentage\": ${SAMPLING_PERCENTAGE}}}" \
  --region "$AWS_REGION" > /dev/null

echo -e "${GREEN}✓ Indexing rule configured (${SAMPLING_PERCENTAGE}% sampling)${NC}"
echo ""

################################################################################
# Step 4: Verify Configuration
################################################################################

echo -e "${YELLOW}→ Step 4: Verifying Transaction Search configuration...${NC}"

# Get trace segment destination
DEST_STATUS=$($AWS_CMD xray get-trace-segment-destination --region "$AWS_REGION" --output json 2>/dev/null || echo "{}")
DESTINATION=$(echo "$DEST_STATUS" | grep -o '"Destination": "[^"]*"' | cut -d'"' -f4)
STATUS=$(echo "$DEST_STATUS" | grep -o '"Status": "[^"]*"' | cut -d'"' -f4)

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Transaction Search Configuration:${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "  Region:              ${GREEN}$AWS_REGION${NC}"
echo -e "  Account ID:          ${GREEN}$ACCOUNT_ID${NC}"
echo -e "  Destination:         ${GREEN}$DESTINATION${NC}"
echo -e "  Status:              ${GREEN}$STATUS${NC}"
echo -e "  Sampling:            ${GREEN}${SAMPLING_PERCENTAGE}%${NC}"
echo -e "  Resource Policy:     ${GREEN}$POLICY_NAME${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

if [[ "$STATUS" == "ACTIVE" ]]; then
  echo -e "${GREEN}✓ Transaction Search is ACTIVE!${NC}"
  echo ""
  echo -e "${YELLOW}Note: It can take up to 10 minutes for spans to become available${NC}"
  echo -e "${YELLOW}      for search and analysis in the CloudWatch console.${NC}"
else
  echo -e "${YELLOW}⚠ Status is '$STATUS'. Waiting for ACTIVE status...${NC}"
  echo -e "${YELLOW}  This may take a few minutes.${NC}"
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Next Steps:${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "  1. View Transaction Search in CloudWatch console:"
echo -e "     ${BLUE}https://console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#application-signals:transaction-search${NC}"
echo ""
echo -e "  2. View Application Signals dashboard:"
echo -e "     ${BLUE}https://console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#application-signals${NC}"
echo ""
echo -e "  3. Monitor spans ingestion:"
echo -e "     ${BLUE}https://console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#logsV2:log-groups/log-group/aws\$252Fspans${NC}"
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}✓ Transaction Search enabled successfully!${NC}"
echo ""
