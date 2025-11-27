# CloudWatch Transaction Search Setup

This guide explains how to enable CloudWatch Transaction Search for the AgentCore Runtime to enhance observability and tracing capabilities.

## Overview

CloudWatch Transaction Search provides:
- **Cost-effective span ingestion** through CloudWatch Logs
- **Full end-to-end trace visibility** for all ingested spans
- **Free 1% span indexing** for trace summary analysis
- **Enhanced observability** with Application Signals integration

## Prerequisites

The IAM permissions required for Transaction Search have been added to the AgentCore Runtime execution role in the CDK stack. These include:

- **X-Ray permissions**: Get/Update trace segment destination and indexing rules
- **CloudWatch Logs permissions**: Create log groups/streams for spans
- **Application Signals permissions**: Start discovery for enhanced monitoring
- **Service-linked roles**: Create and manage Application Signals service roles

## Deployment

### 1. Deploy the Updated IAM Permissions

The Transaction Search prerequisites have been added to the runtime stack. Deploy the changes:

```bash
cd agent-blueprint
./deploy.sh --runtime
```

Or deploy all stacks:

```bash
./deploy.sh
```

### 2. Enable Transaction Search

After the stack is deployed, run the enablement script:

```bash
cd agent-blueprint
./enable-transaction-search.sh
```

**With custom options:**

```bash
# Use specific AWS profile
./enable-transaction-search.sh --profile my-profile

# Use specific region
./enable-transaction-search.sh --region us-west-2

# Set custom sampling percentage (default is 1%)
./enable-transaction-search.sh --sampling 5

# Combine options
./enable-transaction-search.sh --profile dna-sandbox --region us-east-1 --sampling 2
```

### 3. Verify Configuration

The script will automatically verify the configuration and display:
- Current destination status (should be "ACTIVE")
- Sampling percentage
- Resource policy status

**Manual verification:**

```bash
# Check trace segment destination
aws xray get-trace-segment-destination

# Expected output:
# {
#     "Destination": "CloudWatchLogs",
#     "Status": "ACTIVE"
# }
```

## What the Script Does

The `enable-transaction-search.sh` script performs the following steps:

### Step 1: Create CloudWatch Logs Resource Policy
Creates a resource-based policy that allows X-Ray to write spans to CloudWatch Logs:
- Log group: `aws/spans`
- Log group: `/aws/application-signals/data`

### Step 2: Configure Trace Segment Destination
Updates X-Ray to send trace segments to CloudWatch Logs instead of X-Ray's native storage.

### Step 3: Configure Indexing Rules
Sets the sampling percentage for span indexing (default: 1%, which is free).

### Step 4: Verify Configuration
Checks the destination status and confirms everything is working.

## Using Transaction Search

### Access the Console

1. **Transaction Search**:
   ```
   https://console.aws.amazon.com/cloudwatch/home?region=<region>#application-signals:transaction-search
   ```

2. **Application Signals Dashboard**:
   ```
   https://console.aws.amazon.com/cloudwatch/home?region=<region>#application-signals
   ```

3. **Spans Log Group**:
   ```
   https://console.aws.amazon.com/cloudwatch/home?region=<region>#logsV2:log-groups/log-group/aws$252Fspans
   ```

### Query Spans

Transaction Search allows you to:
- Search spans by service, operation, or custom attributes
- Filter by time range, status code, or latency
- Visualize trace topology and dependencies
- Analyze performance bottlenecks

**Note**: It can take up to 10 minutes for spans to appear after enabling Transaction Search.

## Cost Considerations

- **Span Ingestion**: Charged via CloudWatch Logs ingestion pricing
- **Span Indexing**: 1% indexing is free; additional indexing incurs charges
- **Log Storage**: Standard CloudWatch Logs storage pricing applies

To manage costs:
- Keep sampling at 1% unless you need more detailed analysis
- Set appropriate retention policies on log groups
- Use CloudWatch Logs Insights for ad-hoc queries

## Troubleshooting

### Status shows "PENDING" or "UPDATING"

Wait a few minutes and check again. The transition can take time.

### No spans appearing

1. Verify your application is sending traces to X-Ray
2. Check CloudWatch Logs for the `aws/spans` log group
3. Ensure the AgentCore Runtime has been redeployed with updated permissions
4. Verify the runtime is generating telemetry data

### Permission Errors

If you see permission errors:
1. Ensure the CDK stack has been deployed with the updated IAM permissions
2. Verify your AWS CLI credentials have sufficient permissions
3. Check that the service-linked roles were created successfully

### Disable Transaction Search

To disable Transaction Search and return to X-Ray native storage:

```bash
aws xray update-trace-segment-destination --destination XRay
```

## Sampling Percentage Guidelines

- **1% (default)**: Sufficient for most use cases; provides good overview at no extra cost
- **5-10%**: Better for detailed analysis during development or troubleshooting
- **>10%**: Only for specific use cases; significantly increases costs

## Integration with Existing Observability

Transaction Search complements the existing observability setup:

- **Local Development**: Uses console exporters (configured in `setup-observability.sh`)
- **Production**: X-Ray traces → CloudWatch Logs → Transaction Search
- **OpenTelemetry**: Compatible with OTEL instrumentation
- **Application Signals**: Provides enhanced service-level insights

## Additional Resources

- [AWS Transaction Search Documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Enable-TransactionSearch.html)
- [CloudWatch Application Signals](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Application-Signals.html)
- [X-Ray Developer Guide](https://docs.aws.amazon.com/xray/latest/devguide/)
- [AgentCore Observability Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-get-started.html)

## Summary

With Transaction Search enabled, you get:
✅ Cost-effective span ingestion  
✅ Full trace visibility  
✅ Enhanced Application Signals integration  
✅ Better debugging and performance analysis  
✅ Free 1% span indexing for trace summaries  

The prerequisite IAM permissions are now part of your CDK infrastructure and will be automatically deployed with future updates.
