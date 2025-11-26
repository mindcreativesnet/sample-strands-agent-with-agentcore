"""
Report Writer MCP Server on AWS Bedrock AgentCore Runtime
CDK Stack Definition
"""
from aws_cdk import (
    Stack,
    CfnOutput,
    RemovalPolicy,
    Duration,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_ssm as ssm,
    aws_logs as logs,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_codebuild as codebuild,
    custom_resources as cr,
    aws_lambda as lambda_,
    aws_bedrockagentcore as bedrockagentcore,
)
from constructs import Construct
import os


class ReportWriterAgentCoreStack(Stack):
    """
    CDK Stack for deploying Report Writer MCP Server on Bedrock AgentCore Runtime

    This stack creates:
    - ECR repository for Docker images
    - S3 bucket for final report storage
    - IAM roles with necessary permissions
    - Bedrock AgentCore Runtime with container configuration
    - SSM parameter for endpoint storage
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        region = self.region
        project_name = "report-writer-a2a"

        # ==================== ECR Repository ====================
        # Use existing repository if USE_EXISTING_ECR=true
        use_existing_ecr = os.environ.get('USE_EXISTING_ECR', 'false') == 'true'
        if use_existing_ecr:
            ecr_repository = ecr.Repository.from_repository_name(
                self,
                "ReportWriterA2aRepository",
                repository_name=f"{project_name}-repository"
            )
        else:
            ecr_repository = ecr.Repository(
                self,
                "ReportWriterA2aRepository",
                repository_name=f"{project_name}-repository",
                removal_policy=RemovalPolicy.RETAIN,
                image_scan_on_push=True,
                lifecycle_rules=[
                    ecr.LifecycleRule(
                        description="Keep last 10 images",
                        max_image_count=10
                    )
                ]
            )

        # ==================== S3 Bucket for Report Storage ====================
        # Create standard S3 bucket for final reports
        report_bucket = s3.Bucket(
            self,
            "ReportStorageBucket",
            bucket_name=f"report-writer-bucket-{self.account}".lower()[:63],
            removal_policy=RemovalPolicy.DESTROY,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        # ==================== Code Interpreter (Shared Resource) ====================
        # Code Interpreter is created in AgentCore Runtime Stack (Option 1 deployment)
        # and shared across all agents. Retrieve the ID from SSM Parameter Store.
        code_interpreter_id_param = ssm.StringParameter.from_string_parameter_name(
            self,
            "CodeInterpreterIdParam",
            string_parameter_name="/strands-agent-chatbot/dev/agentcore/code-interpreter-id"
        )
        code_interpreter_id = code_interpreter_id_param.string_value

        # ==================== CodeBuild for Container Image ====================
        # Step 1: S3 Bucket for CodeBuild Source
        source_bucket = s3.Bucket(
            self,
            "SourceBucket",
            bucket_name=f"{project_name}-sources-{self.account}-{region}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(7),
                    id="DeleteOldSources"
                )
            ]
        )

        # Step 2: CodeBuild Project
        codebuild_role = iam.Role(
            self,
            "CodeBuildRole",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
            description="Build role for Report Writer container image"
        )

        # ECR Token Access
        codebuild_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ecr:GetAuthorizationToken"],
                resources=["*"]
            )
        )

        # ECR Image Operations
        codebuild_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:PutImage",
                    "ecr:InitiateLayerUpload",
                    "ecr:UploadLayerPart",
                    "ecr:CompleteLayerUpload"
                ],
                resources=[
                    f"arn:aws:ecr:{region}:{self.account}:repository/{ecr_repository.repository_name}"
                ]
            )
        )

        # CloudWatch Logs
        codebuild_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[f"arn:aws:logs:{region}:{self.account}:log-group:/aws/codebuild/{project_name}-*"]
            )
        )

        # S3 Access
        codebuild_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
                resources=[source_bucket.bucket_arn, f"{source_bucket.bucket_arn}/*"],
                conditions={
                    "StringEquals": {
                        "s3:ResourceAccount": self.account
                    }
                }
            )
        )

        build_project = codebuild.Project(
            self,
            "BuildProject",
            project_name=f"{project_name}-builder",
            description="Builds AMD64 container image for Report Writer A2A Agent",
            role=codebuild_role,
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.AMAZON_LINUX_2_5,
                compute_type=codebuild.ComputeType.SMALL,
                privileged=True
            ),
            source=codebuild.Source.s3(
                bucket=source_bucket,
                path="source.zip"
            ),
            build_spec=codebuild.BuildSpec.from_object({
                "version": "0.2",
                "phases": {
                    "pre_build": {
                        "commands": [
                            "echo Logging in to Amazon ECR...",
                            f"aws ecr get-login-password --region {region} | docker login --username AWS --password-stdin {self.account}.dkr.ecr.{region}.amazonaws.com",
                            "IMAGE_TAG=latest",
                            f"IMAGE_URI={ecr_repository.repository_uri}:$IMAGE_TAG"
                        ]
                    },
                    "build": {
                        "commands": [
                            "echo Building Docker image...",
                            "cd src",
                            "docker build --platform linux/amd64 -t $IMAGE_URI -f Dockerfile ."
                        ]
                    },
                    "post_build": {
                        "commands": [
                            "echo Pushing Docker image to ECR...",
                            "docker push $IMAGE_URI",
                            "echo Build completed on `date`"
                        ]
                    }
                }
            })
        )

        # Step 3: Upload source to S3
        s3deploy.BucketDeployment(
            self,
            "SourceDeployment",
            sources=[s3deploy.Source.asset("../src")],
            destination_bucket=source_bucket,
            destination_key_prefix="",
            prune=False
        )

        # Step 4: Trigger CodeBuild
        build_trigger = cr.AwsCustomResource(
            self,
            "TriggerCodeBuild",
            on_create=cr.AwsSdkCall(
                service="CodeBuild",
                action="startBuild",
                parameters={"projectName": build_project.project_name},
                physical_resource_id=cr.PhysicalResourceId.of(f"{project_name}-build-trigger")
            ),
            on_update=cr.AwsSdkCall(
                service="CodeBuild",
                action="startBuild",
                parameters={"projectName": build_project.project_name},
                physical_resource_id=cr.PhysicalResourceId.of(f"{project_name}-build-trigger")
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=["codebuild:StartBuild", "codebuild:BatchGetBuilds"],
                    resources=[build_project.project_arn]
                )
            ])
        )

        build_trigger.node.add_dependency(build_project)
        build_trigger.node.add_dependency(source_bucket)

        # ==================== IAM Role for AgentCore Runtime ====================
        runtime_role = iam.Role(
            self,
            "AgentCoreRuntimeRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("bedrock-agentcore.amazonaws.com",
                    conditions={
                        "StringEquals": {
                            "aws:SourceAccount": self.account
                        },
                        "ArnLike": {
                            "aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{self.account}:*"
                        }
                    }
                )
            ),
            description="IAM role for Report Writer AgentCore Runtime"
        )

        # Add S3 bucket permissions for report storage
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:PutObject",
                    "s3:GetObject",
                    "s3:DeleteObject",
                    "s3:ListBucket"
                ],
                resources=[
                    report_bucket.bucket_arn,
                    f"{report_bucket.bucket_arn}/*"
                ]
            )
        )

        # Add ECR permissions for pulling images
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                sid="ECRImageAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchCheckLayerAvailability"
                ],
                resources=[f"arn:aws:ecr:{region}:{self.account}:repository/*"]
            )
        )

        runtime_role.add_to_policy(
            iam.PolicyStatement(
                sid="ECRTokenAccess",
                effect=iam.Effect.ALLOW,
                actions=["ecr:GetAuthorizationToken"],
                resources=["*"]
            )
        )

        # Add CloudWatch Logs permissions
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:DescribeLogStreams",
                    "logs:CreateLogGroup"
                ],
                resources=[f"arn:aws:logs:{region}:{self.account}:log-group:/aws/bedrock-agentcore/runtimes/*"]
            )
        )

        runtime_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:DescribeLogGroups"],
                resources=[f"arn:aws:logs:{region}:{self.account}:log-group:*"]
            )
        )

        runtime_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=[f"arn:aws:logs:{region}:{self.account}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"]
            )
        )

        # Add X-Ray permissions
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets"
                ],
                resources=["*"]
            )
        )

        # Add CloudWatch metrics permissions
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
                conditions={
                    "StringEquals": {
                        "cloudwatch:namespace": "bedrock-agentcore"
                    }
                }
            )
        )

        # Add workload identity permissions
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                sid="GetAgentAccessToken",
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:GetWorkloadAccessToken",
                    "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                    "bedrock-agentcore:GetWorkloadAccessTokenForUserId"
                ],
                resources=[
                    f"arn:aws:bedrock-agentcore:{region}:{self.account}:workload-identity-directory/default",
                    f"arn:aws:bedrock-agentcore:{region}:{self.account}:workload-identity-directory/default/workload-identity/agentName-*"
                ]
            )
        )

        # Add Bedrock model invocation permissions
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                sid="BedrockModelInvocation",
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                resources=[
                    "arn:aws:bedrock:*::foundation-model/*",
                    f"arn:aws:bedrock:{region}:{self.account}:*"
                ]
            )
        )

        # Add AgentCore Code Interpreter permissions (shared resource)
        # Code Interpreter is created in AgentCore Runtime Stack and shared
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                sid="SharedCodeInterpreterAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:StartCodeInterpreterSession",
                    "bedrock-agentcore:InvokeCodeInterpreter",
                    "bedrock-agentcore:StopCodeInterpreterSession",
                    "bedrock-agentcore:GetCodeInterpreter",
                    "bedrock-agentcore:GetCodeInterpreterSession",
                    "bedrock-agentcore:ListCodeInterpreterSessions"
                ],
                resources=[
                    f"arn:aws:bedrock-agentcore:{region}:{self.account}:code-interpreter/*"
                ]
            )
        )

        # Add SSM parameter read permission to retrieve Code Interpreter ID
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ssm:GetParameter"],
                resources=[
                    f"arn:aws:ssm:{region}:{self.account}:parameter/strands-agent-chatbot/dev/agentcore/code-interpreter-id"
                ]
            )
        )

        # ==================== CloudWatch Log Group ====================
        log_group = logs.LogGroup(
            self,
            "AgentCoreRuntimeLogGroup",
            log_group_name=f"/aws/bedrockagentcore/{construct_id}",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_WEEK
        )

        # ==================== Bedrock AgentCore Runtime ====================
        runtime = bedrockagentcore.CfnRuntime(
            self,
            "ReportWriterRuntime",
            agent_runtime_artifact=bedrockagentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=bedrockagentcore.CfnRuntime.ContainerConfigurationProperty(
                    container_uri=f"{ecr_repository.repository_uri}:latest"
                )
            ),
            agent_runtime_name=f"report_writer_a2a_agent",
            network_configuration=bedrockagentcore.CfnRuntime.NetworkConfigurationProperty(
                network_mode="PUBLIC"
            ),
            role_arn=runtime_role.role_arn,
            description="Report Writer A2A Agent Runtime",
            # Environment variables passed at CfnRuntime level
            environment_variables={
                "DOCUMENT_BUCKET_NAME": report_bucket.bucket_name,
                "AWS_REGION": region,
                "PORT": "9000",  # A2A protocol uses port 9000
                "LOG_LEVEL": "info",
                "PYTHONUNBUFFERED": "1",
                "PYTHONDONTWRITEBYTECODE": "1"
            },
            protocol_configuration="A2A",  # Changed from MCP to A2A
        )

        # Add dependency to ensure ECR repository is created first
        runtime.node.add_dependency(ecr_repository)
        runtime.node.add_dependency(runtime_role)

        # ==================== Bedrock AgentCore Runtime Endpoint ====================
        # Endpoint name must match pattern ^[a-zA-Z][a-zA-Z0-9_]{0,47}$ (no hyphens allowed)
        endpoint_name = construct_id.replace("-", "_") + "_endpoint"

        runtime_endpoint = bedrockagentcore.CfnRuntimeEndpoint(
            self,
            "ReportWriterRuntimeEndpoint",
            agent_runtime_id=runtime.attr_agent_runtime_id,
            name=endpoint_name,
            description="Report Writer A2A Agent Endpoint"
        )
        runtime_endpoint.node.add_dependency(runtime)

        # ==================== SSM Parameter for Endpoint ====================
        ssm_parameter = ssm.StringParameter(
            self,
            "RuntimeEndpointParameter",
            parameter_name=f"/a2a/endpoints/agentcore/report-writer",
            string_value=runtime_endpoint.attr_agent_runtime_endpoint_arn,
            description="AgentCore Runtime endpoint for Report Writer A2A Agent",
            tier=ssm.ParameterTier.STANDARD
        )

        # ==================== CloudFormation Outputs ====================
        CfnOutput(
            self,
            "EcrRepositoryUri",
            value=ecr_repository.repository_uri,
            description="ECR Repository URI for Docker images",
            export_name=f"{construct_id}-ecr-uri"
        )

        CfnOutput(
            self,
            "EcrRepositoryName",
            value=ecr_repository.repository_name,
            description="ECR Repository Name",
            export_name=f"{construct_id}-ecr-name"
        )

        CfnOutput(
            self,
            "ReportBucketName",
            value=report_bucket.bucket_name,
            description="S3 bucket name for report storage",
            export_name=f"{construct_id}-report-bucket-name"
        )

        CfnOutput(
            self,
            "ReportBucketArn",
            value=report_bucket.bucket_arn,
            description="S3 bucket ARN",
            export_name=f"{construct_id}-report-bucket-arn"
        )

        CfnOutput(
            self,
            "RuntimeEndpoint",
            value=runtime_endpoint.attr_agent_runtime_endpoint_arn,
            description="AgentCore Runtime Endpoint ARN",
            export_name=f"{construct_id}-runtime-endpoint"
        )

        CfnOutput(
            self,
            "RuntimeArn",
            value=runtime.attr_agent_runtime_arn,
            description="AgentCore Runtime ARN",
            export_name=f"{construct_id}-runtime-arn"
        )

        CfnOutput(
            self,
            "RuntimeRoleArn",
            value=runtime_role.role_arn,
            description="IAM Role ARN for AgentCore Runtime",
            export_name=f"{construct_id}-role-arn"
        )

        CfnOutput(
            self,
            "SsmParameterName",
            value=ssm_parameter.parameter_name,
            description="SSM Parameter storing the runtime endpoint",
            export_name=f"{construct_id}-ssm-param"
        )

        CfnOutput(
            self,
            "LogGroupName",
            value=log_group.log_group_name,
            description="CloudWatch Log Group name",
            export_name=f"{construct_id}-log-group"
        )
