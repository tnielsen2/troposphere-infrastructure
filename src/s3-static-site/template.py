#!/usr/bin/env python3
import json

import troposphere.cloudfront as cf
import troposphere.s3 as s3
from troposphere import GetAtt, Join, Output, Ref, Select, Split, Template
from troposphere.apigateway import Deployment, Integration, IntegrationResponse, Method, MethodResponse, Resource, \
    RestApi, Stage
from troposphere.awslambda import Code, Function
from troposphere.certificatemanager import Certificate, DomainValidationOption
from troposphere.dynamodb import AttributeDefinition, KeySchema, ProvisionedThroughput, Table
from troposphere.iam import Policy, Role
from troposphere.route53 import AliasTarget, RecordSetType
from troposphere.s3 import *

from ..common.file_utils import save_to_file

stack_regions = ['us-east-1']
stack_environments = ['dev-a']

app_group = "s3-static-site"
app_group_l = app_group.lower()
app_group_ansi = app_group_l.replace("-", "")
cfront_zone_id = 'Z2FDTNDATAQYW2'

# Create Default Tags
DefaultTags = Tags(Business='YIT') + \
              Tags(Lab='True')

# Set template variables
stage_name = 'v1'

##### Dynamo Variables
readunits = 5
writeunits = 5
# The name of the table
hashkeyname = 'counters'
# Table data type (N is for number/integer)
hashkeytype = 'N'

dns_domain = 'trentnielsen.me'


def create_cfn_template(environment, region):
    # Prepare Template
    t = Template()
    t.set_description(f'YIT: {app_group}')

    ################################################################################################################
    # CloudFront and S3 for static hosting
    ################################################################################################################

    redirect_domains = {
        'resume.trentnielsen.me': {
            'zone_name': 'trentnielsen.me',
            'redirect_target': 'resume.trentnielsen.me',
            'alt_sub': 'www',
        },
    }

    for src_domain, domain_info in redirect_domains.items():

        bucketResourceName = f"{app_group_ansi}0{src_domain.replace('.', '0')}0Bucket"

        redirectBucket = t.add_resource(Bucket(
            bucketResourceName,
            BucketName=f'{src_domain}',
            Tags=DefaultTags + Tags(Component=f'{src_domain}'),
            WebsiteConfiguration=(s3.WebsiteConfiguration(
                IndexDocument='index.html'
            ))
        ))

        # Set some cdn based values and defaults
        dns_domain = domain_info['zone_name']
        cdn_domain = f'{src_domain}'
        max_ttl = 31536000,
        default_ttl = 86400,

        # If an alt_sub domain is not specified use empty string
        if domain_info['alt_sub'] != '':
            alternate_name = f"{domain_info['alt_sub']}.{src_domain}"
        else:
            alternate_name = ''

        # Provision certificate for CDN
        cdnCertificate = t.add_resource(Certificate(
            f"cdnCertificate{src_domain.replace('.', '0')}",
            DomainName=cdn_domain,
            DependsOn=redirectBucket,
            SubjectAlternativeNames=[alternate_name],
            DomainValidationOptions=[DomainValidationOption(
                DomainName=cdn_domain,
                ValidationDomain=dns_domain
            )],
            ValidationMethod='DNS',
            Tags=DefaultTags + Tags(Name=f'{environment}-{app_group_l}')
        ))

        # Provision the CDN Origin
        cdnOrigin = cf.Origin(
            Id=f'{environment}-{app_group_l}-{src_domain}',
            DomainName=Select(1, Split('//', GetAtt(redirectBucket, 'WebsiteURL'))),
            CustomOriginConfig=cf.CustomOriginConfig(
                HTTPPort=80,
                HTTPSPort=443,
                OriginProtocolPolicy='http-only',
                OriginSSLProtocols=['TLSv1.2'],
            )
        )

        # Provision the CDN Distribution
        cdnDistribution = t.add_resource(cf.Distribution(
            f"cdnDistribution{src_domain.replace('.', '0')}",
            DependsOn=f"cdnCertificate{src_domain.replace('.', '0')}",
            DistributionConfig=cf.DistributionConfig(
                Comment=f'{environment} - {cdn_domain}',
                Enabled=True,
                PriceClass='PriceClass_All',
                HttpVersion='http2',
                Origins=[
                    cdnOrigin,
                ],
                Aliases=[cdn_domain, alternate_name],
                ViewerCertificate=cf.ViewerCertificate(
                    AcmCertificateArn=Ref(cdnCertificate),
                    SslSupportMethod='sni-only',
                    MinimumProtocolVersion='TLSv1.2_2018',
                ),
                DefaultCacheBehavior=cf.DefaultCacheBehavior(
                    AllowedMethods=['GET', 'HEAD', 'OPTIONS'],
                    CachedMethods=['GET', 'HEAD'],
                    ViewerProtocolPolicy='redirect-to-https',
                    TargetOriginId=f'{environment}-{app_group_l}-{src_domain}',
                    ForwardedValues=cf.ForwardedValues(
                        Headers=[
                            "Accept-Encoding"
                        ],
                        QueryString=True,
                    ),
                    MinTTL=0,
                    MaxTTL=int(max_ttl[0]),
                    DefaultTTL=int(default_ttl[0]),
                    SmoothStreaming=False,
                    Compress=True
                ),
                CustomErrorResponses=[
                    cf.CustomErrorResponse(
                        ErrorCachingMinTTL='0',
                        ErrorCode='403',
                    ),
                    cf.CustomErrorResponse(
                        ErrorCachingMinTTL='0',
                        ErrorCode='404',
                    ),
                    cf.CustomErrorResponse(
                        ErrorCachingMinTTL='0',
                        ErrorCode='500',
                    ),
                    cf.CustomErrorResponse(
                        ErrorCachingMinTTL='0',
                        ErrorCode='501',
                    ),
                    cf.CustomErrorResponse(
                        ErrorCachingMinTTL='0',
                        ErrorCode='502',
                    ),
                    cf.CustomErrorResponse(
                        ErrorCachingMinTTL='0',
                        ErrorCode='503',
                    ),
                    cf.CustomErrorResponse(
                        ErrorCachingMinTTL='0',
                        ErrorCode='504',
                    ),
                ],
            ),
            Tags=DefaultTags
        ))

        cdnARecord = t.add_resource(RecordSetType(
            f"{app_group_ansi}{src_domain.replace('.', '0')}Adns",
            HostedZoneName=f'{dns_domain}.',
            Comment=f"{cdn_domain} domain record",
            Name=f'{cdn_domain}',
            Type="A",
            AliasTarget=AliasTarget(
                HostedZoneId=cfront_zone_id,
                DNSName=GetAtt(cdnDistribution, "DomainName")
            )
        ))

        cdnAAAARecord = t.add_resource(RecordSetType(
            f"{app_group_ansi}{src_domain.replace('.', '0')}AAAAdns",
            HostedZoneName=f'{dns_domain}.',
            Comment=f"{cdn_domain} domain record",
            Name=f'{cdn_domain}',
            Type="AAAA",
            AliasTarget=AliasTarget(
                HostedZoneId=cfront_zone_id,
                DNSName=GetAtt(cdnDistribution, "DomainName")
            )
        ))

        if domain_info['alt_sub'] != '':
            cdnAlternativeARecord = t.add_resource(RecordSetType(
                f"{app_group_ansi}{src_domain.replace('.', '0')}AlternativeAdns",
                HostedZoneName=f'{dns_domain}.',
                Comment=f"{alternate_name} domain record",
                Name=f'{alternate_name}',
                Type="A",
                AliasTarget=AliasTarget(
                    HostedZoneId=cfront_zone_id,
                    DNSName=GetAtt(cdnDistribution, "DomainName")
                )
            ))

            cdnAlternativeAAAARecord = t.add_resource(RecordSetType(
                f"{app_group_ansi}{src_domain.replace('.', '0')}AlternativeAAAAdns",
                HostedZoneName=f'{dns_domain}.',
                Comment=f"{alternate_name} domain record",
                Name=f'{alternate_name}',
                Type="AAAA",
                AliasTarget=AliasTarget(
                    HostedZoneId=cfront_zone_id,
                    DNSName=GetAtt(cdnDistribution, "DomainName")
                )
            ))

            # Redirect outputs
            t.add_output([
                Output(
                    f"CDNDomainOutput{src_domain.replace('.', '0')}",
                    Description="Domain for CDN",
                    Value=GetAtt(cdnDistribution, 'DomainName'),
                )
            ])

    #####################################################################################################################
    # API Gateway
    #####################################################################################################################
    rest_api = t.add_resource(RestApi(
        "api",
        Name=f"{environment}-{app_group_l}"
    ))

    #####################################################################################################################
    # DynamoDB table
    #####################################################################################################################
    myDynamoDB = t.add_resource(Table(
        "myDynamoDBTable",
        TableName='counters',
        AttributeDefinitions=[
            AttributeDefinition(
                AttributeName='website',
                AttributeType='S'
            )
        ],
        KeySchema=[
            KeySchema(
                AttributeName='website',
                KeyType='HASH'
            )
        ],
        ProvisionedThroughput=ProvisionedThroughput(
            ReadCapacityUnits=readunits,
            WriteCapacityUnits=writeunits
        )
    ))

    #####################################################################################################################
    # Lambda
    #####################################################################################################################
    # Create a Lambda function that will be mapped
    code = [
        "var response = require('cfn-response');",
        "exports.handler = function(event, context) {",
        "   context.succeed('foobar!');",
        "   return 'foobar!';",
        "};",
    ]

    # Create a role for the lambda function
    t.add_resource(Role(
        "LambdaExecutionRole",
        Path="/",
        Policies=[Policy(
            PolicyName="root",
            PolicyDocument={
                "Version": "2012-10-17",
                "Statement": [{
                    "Action": ["logs:*"],
                    "Resource": "arn:aws:logs:*:*:*",
                    "Effect": "Allow"
                },
                    {
                        "Action": ["lambda:*"],
                        "Resource": "*",
                        "Effect": "Allow"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "dynamodb:BatchGetItem",
                            "dynamodb:GetItem",
                            "dynamodb:Query",
                            "dynamodb:Scan",
                            "dynamodb:BatchWriteItem",
                            "dynamodb:PutItem",
                            "dynamodb:UpdateItem"
                        ],
                        "Resource": GetAtt('myDynamoDBTable', 'Arn')
                    }]
            })],
        AssumeRolePolicyDocument={"Version": "2012-10-17", "Statement": [
            {
                "Action": ["sts:AssumeRole"],
                "Effect": "Allow",
                "Principal": {
                    "Service": [
                        "lambda.amazonaws.com",
                        "apigateway.amazonaws.com"
                    ]
                }
            }
        ]},
    ))

    function = t.add_resource(Function(
        "function",
        Code=Code(
            ZipFile=Join("", code)
        ),
        Handler="index.handler",
        Role=GetAtt("LambdaExecutionRole", "Arn"),
        Runtime="python3.7",
    ))

    # Create a resource to map the lambda function to
    resource = t.add_resource(Resource(
        "resource",
        RestApiId=Ref(rest_api),
        PathPart="dynamo",
        ParentId=GetAtt("api", "RootResourceId"),
    ))

    # Create a get method that integrates into Lambda
    getmethod = t.add_resource(Method(
        "getmethod",
        RestApiId=Ref(rest_api),
        AuthorizationType="NONE",
        ResourceId=Ref(resource),
        HttpMethod="GET",
        MethodResponses=[
            MethodResponse(
                "CatResponse",
                StatusCode='200',
                ResponseModels={
                    'application/json': 'Empty'
                }
            )
        ],
        Integration=Integration(
            Credentials=GetAtt("LambdaExecutionRole", "Arn"),
            PassthroughBehavior='WHEN_NO_MATCH',
            Type="AWS",
            IntegrationHttpMethod='POST',
            IntegrationResponses=[
                IntegrationResponse(
                    StatusCode='200',
                    ResponseTemplates={
                        'application/json': ''
                    },
                )
            ],
            Uri=Join("", [
                f"arn:aws:apigateway:{region}:lambda:path/2015-03-31/functions/",
                GetAtt("function", "Arn"),
                "/invocations"
            ]),

            RequestTemplates={
                'application/json': '{"statusCode": 200}'
            },
        ),
    ))

    deployment = t.add_resource(Deployment(
        f"{stage_name}Deployment",
        DependsOn="optionsmethod",
        RestApiId=Ref(rest_api),
    ))

    stage = t.add_resource(Stage(
        f'{stage_name}Stage',
        StageName=stage_name,
        RestApiId=Ref(rest_api),
        DeploymentId=Ref(deployment)
    ))

    # Create cname record for all mount points
    apiCname = t.add_resource(RecordSetType(
        'apiCname',
        HostedZoneName=f'{dns_domain}.',
        Comment=f"{app_group_l} API gateway domain record",
        Name=f"api.{dns_domain}",
        Type="CNAME",
        TTL="900",
        ResourceRecords=[Join("", [
            Ref(rest_api),
            f".execute-api.{region}.amazonaws.com"
        ])]
    ))

    #####################################################################################################################
    # Output
    #####################################################################################################################

    # API gateway outputs
    t.add_output([
        Output(
            "ApiEndpoint",
            Value=Join("", [
                "https://",
                Ref(rest_api),
                f".execute-api.{region}.amazonaws.com/",
                stage_name
            ]),
            Description="Endpoint for this stage of the api"
        ),
    ])
    # DynamoDB outputs
    t.add_output(Output(
        "TableName",
        Value=Ref(myDynamoDB),
        Description="Table name of the newly create DynamoDB table",
    ))

    # Load the data into a json object
    json_data = json.loads(t.to_json())

    # Save the file to disk
    save_to_file(json_data, environment, region, app_group_l)
