#!/usr/bin/env python3
import json
import sys

import troposphere.ec2 as ec2
from troposphere import Export, FindInMap, GetAtt, Output, Ref, Template
from troposphere.s3 import *

from ..common.file_utils import save_to_file
from ..common.vpc import availability_zones, vpc_settings, add_cidr_mapping

#### Generation vars
stack_regions = ["us-west-2"]
stack_environments = ["dev-a"]

# Configuration Variables
app_group = "VPC"
app_group_l = app_group.lower()
ansible_app_group_l = app_group_l.replace("-", "_")


def create_cfn_template(environment, region):
    vpc_type = vpc_settings[region][environment]["vpc_type"]
    vpc_cidr = vpc_settings[region][environment]["cidr"]
    az_count = vpc_settings[region][environment]["subnet_count"]

    # Prepare Template
    t = Template()
    t.set_description(f"{environment}: LAB - {app_group} Infrastructure")
    t.set_metadata(
        {
            "cfn-lint": {
                "config": {
                    # Do not warn or error on Security group names
                    "ignore_checks": ["E11001", "W11001", "W10001", "W10002"]
                }
            }
        }
    )

    # Pull In Tags
    default_tags = (
        Tags(Business="LAB")
        + Tags(Service=app_group_l)
        + Tags(ExtendedName=f"{environment}-{region}-{app_group_l}")
    )

    # Create subnet mappings
    add_cidr_mapping(t, region, vpc_cidr, vpc_type, az_count)
    vpc = t.add_resource(
        ec2.VPC(
            "VPC",
            CidrBlock=vpc_cidr,
            EnableDnsHostnames="true",
            Tags=default_tags + Tags(Name=f"{environment}-vpc"),
        )
    )

    # Allow ICMP from all. http://shouldiblockicmp.com/
    defaultSecurityGroup = t.add_resource(
        ec2.SecurityGroup(
            "defaultSecurityGroup",
            GroupDescription=f"{environment} ICMP security group",
            SecurityGroupIngress=[
                ec2.SecurityGroupRule(
                    IpProtocol="icmp",
                    FromPort=str(-1),
                    ToPort=str(-1),
                    CidrIp="10.0.0.0/8",
                )
            ],
            VpcId=Ref(vpc),
            Tags=default_tags,
        )
    )
    t.add_output(
        [
            Output(
                "defaultSecurityGroupIdOutput",
                Description=f"{environment} core default security group ID",
                Value=Ref(defaultSecurityGroup),
                Export=Export(f"{environment}-core-defaultSecurityGroup-ID"),
            )
        ]
    )

    network_acl = t.add_resource(
        ec2.NetworkAcl(
            "NetworkAcl",
            VpcId=Ref(vpc),
            Tags=default_tags + Tags(Name=f"{environment}-network-acl"),
        )
    )

    inbound_acl = t.add_resource(
        ec2.NetworkAclEntry(
            "InboundNetworkAcl",
            NetworkAclId=Ref(network_acl),
            RuleNumber="100",
            Protocol="-1",
            Egress="false",
            RuleAction="allow",
            CidrBlock="0.0.0.0/0",
        )
    )

    outbound_acl = t.add_resource(
        ec2.NetworkAclEntry(
            "OutboundNetworkAcl",
            NetworkAclId=Ref(network_acl),
            RuleNumber="100",
            Protocol="-1",
            Egress="true",
            RuleAction="allow",
            CidrBlock="0.0.0.0/0",
        )
    )

    # If the subnet type is public, then make all the necessary resources for a public subnet
    if vpc_type.lower() == "public":
        internet_gateway = t.add_resource(
            ec2.InternetGateway(
                "InternetGateway",
                Tags=default_tags + Tags(Name=f"{environment}-igw"),
            )
        )

        gateway_attachment = t.add_resource(
            ec2.VPCGatewayAttachment(
                "AttachGateway",
                VpcId=Ref(vpc),
                InternetGatewayId=Ref(internet_gateway),
            )
        )

        publicroutetable = t.add_resource(
            ec2.RouteTable(
                "RouteTable",
                VpcId=Ref(vpc),
                Tags=default_tags + Tags(Name=f"{environment}-public-rtb"),
            )
        )

        route = t.add_resource(
            ec2.Route(
                "Route",
                DependsOn="AttachGateway",
                GatewayId=Ref(internet_gateway),
                DestinationCidrBlock="0.0.0.0/0",
                RouteTableId=Ref(publicroutetable),
            )
        )

        # S3 End point for speed and security
        t.add_resource(
            ec2.VPCEndpoint(
                "S3VPCEndpoint",
                RouteTableIds=[Ref(publicroutetable)],
                ServiceName=f"com.amazonaws.{region}.s3",
                VpcId=Ref(vpc),
            )
        )

        # Create the subnets
        for index, az in enumerate(availability_zones[region]):
            i = index + 1  # Dont want zero-indexed names
            cidr = FindInMap("CidrAllocations", region, f"publicsubnet{i}")
            subnet = t.add_resource(
                ec2.Subnet(
                    f"subnet{i}",
                    CidrBlock=cidr,
                    VpcId=Ref(vpc),
                    MapPublicIpOnLaunch="true",
                    AvailabilityZone=az,
                    Tags=default_tags + Tags(Name=f"{environment}-subnet-{i}"),
                )
            )
            subnet_route = t.add_resource(
                ec2.SubnetRouteTableAssociation(
                    f"subnet{i}route",
                    SubnetId=Ref(subnet),
                    RouteTableId=Ref(publicroutetable),
                )
            )
            subnet_acl = t.add_resource(
                ec2.SubnetNetworkAclAssociation(
                    f"subnet{i}networkacl",
                    SubnetId=Ref(subnet),
                    NetworkAclId=Ref(network_acl),
                )
            )
            t.add_output(
                [
                    Output(
                        f"Subnet{i}",
                        Description=f"{environment} Subnet {i} ID",
                        Value=Ref(subnet),
                        Export=Export(
                            f"{environment}-{app_group_l}-publicsubnet{i}-ID"
                        ),
                    )
                ]
            )

    # If the subnets are private, do this instead
    elif vpc_type.lower() == "private":
        internet_gateway = t.add_resource(
            ec2.InternetGateway(
                "InternetGateway",
                Tags=default_tags + Tags(Name=f"{environment}-igw"),
            )
        )

        gateway_attachment = t.add_resource(
            ec2.VPCGatewayAttachment(
                "AttachGateway",
                VpcId=Ref(vpc),
                InternetGatewayId=Ref(internet_gateway),
            )
        )

        # Create the public route table
        publicroutetable = t.add_resource(
            ec2.RouteTable(
                "publicroutetable",
                VpcId=Ref(vpc),
                Tags=default_tags + Tags(Name=f"{environment}-public-rtb"),
            )
        )

        route = t.add_resource(
            ec2.Route(
                "Route",
                DependsOn="AttachGateway",
                GatewayId=Ref(internet_gateway),
                DestinationCidrBlock="0.0.0.0/0",
                RouteTableId=Ref(publicroutetable),
            )
        )
        # Create empty list to assign to s3 endpoint for route table association
        private_route_tableids = []
        # Create the subnets
        for index, az in enumerate(availability_zones[region]):
            i = index + 1  # Dont want zero-indexed names
            publiccidr = FindInMap("CidrAllocations", region, f"publicsubnet{i}")
            privatecidr = FindInMap("CidrAllocations", region, f"privatesubnet{i}")

            # Create an EIP
            natgatewayeip = t.add_resource(
                ec2.EIP(
                    f"natgatewayeip{i}",
                )
            )

            publicsubnet = t.add_resource(
                ec2.Subnet(
                    f"publicsubnet{i}",
                    CidrBlock=publiccidr,
                    VpcId=Ref(vpc),
                    MapPublicIpOnLaunch="true",
                    AvailabilityZone=az,
                    Tags=default_tags + Tags(Name=f"{environment}-public-subnet-{i}"),
                )
            )

            privatesubnet = t.add_resource(
                ec2.Subnet(
                    f"privatesubnet{i}",
                    CidrBlock=privatecidr,
                    VpcId=Ref(vpc),
                    MapPublicIpOnLaunch="false",
                    AvailabilityZone=az,
                    Tags=default_tags + Tags(Name=f"{environment}-private-subnet-{i}"),
                )
            )

            # Assign it to the nat gateway
            natgateway = t.add_resource(
                ec2.NatGateway(
                    f"natgateway{i}",
                    AllocationId=GetAtt(f"natgatewayeip{i}", "AllocationId"),
                    SubnetId=Ref(f"publicsubnet{i}"),
                    Tags=default_tags + Tags(Name=f"{environment}-natgw{i}"),
                )
            )

            public_subnet_route_association = t.add_resource(
                ec2.SubnetRouteTableAssociation(
                    f"publicsubnet{i}routeassociation",
                    SubnetId=Ref(f"publicsubnet{i}"),
                    RouteTableId=Ref(publicroutetable),
                )
            )

            # Create the private route table
            privatesubnetroutetable = t.add_resource(
                ec2.RouteTable(
                    f"privatesubnet{i}routetable",
                    VpcId=Ref(vpc),
                    Tags=default_tags + Tags(Name=f"{environment}-private{i}-rtb"),
                )
            )

            # Append the s3 endpoint route tables to the endpoint
            private_route_tableids.append(Ref(f"privatesubnet{i}routetable"))

            privatesubnetroute = t.add_resource(
                ec2.Route(
                    f"privatesubnet{i}route",
                    RouteTableId=Ref(f"privatesubnet{i}routetable"),
                    DestinationCidrBlock="0.0.0.0/0",
                    NatGatewayId=Ref(f"natgateway{i}"),
                )
            )

            private_subnet_route_association = t.add_resource(
                ec2.SubnetRouteTableAssociation(
                    f"privatesubnet{i}routeassociation",
                    SubnetId=Ref(f"privatesubnet{i}"),
                    RouteTableId=Ref(f"privatesubnet{i}routetable"),
                )
            )

            public_subnet_acl = t.add_resource(
                ec2.SubnetNetworkAclAssociation(
                    f"publicsubnet{i}networkacl",
                    SubnetId=Ref(f"publicsubnet{i}"),
                    NetworkAclId=Ref(network_acl),
                )
            )

            private_subnet_acl = t.add_resource(
                ec2.SubnetNetworkAclAssociation(
                    f"privatesubnet{i}networkacl",
                    SubnetId=Ref(f"privatesubnet{i}"),
                    NetworkAclId=Ref(network_acl),
                )
            )

            t.add_output(
                [
                    Output(
                        f"PublicSubnet{i}",
                        Description=f"{environment} Public Subnet {i} ID",
                        Value=Ref(f"publicsubnet{i}"),
                        Export=Export(
                            f"{environment}-{app_group_l}-publicsubnet{i}-ID"
                        ),
                    ),
                    Output(
                        f"PrivateSubnet{i}",
                        Description=f"{environment} Private Subnet {i} ID",
                        Value=Ref(f"privatesubnet{i}"),
                        Export=Export(
                            f"{environment}-{app_group_l}-privatesubnet{i}-ID"
                        ),
                    ),
                ]
            )
        # Create S3 endpoint and associated with all the subnet specific routes
        S3VPCEndpoint = t.add_resource(
            ec2.VPCEndpoint(
                "S3VPCEndpoint",
                RouteTableIds=[],
                ServiceName=f"com.amazonaws.{region}.s3",
                VpcId=Ref(vpc),
            )
        )
    else:
        sys.exit("Invalid subnet type defined in src/common/vpc.py")

    t.add_output(
        [
            Output(
                "VPCID",
                Description=f"{environment} VPC ID",
                Export=Export(f"{environment}-{app_group_l}-vpc-id"),
                Value=Ref(vpc),
            )
        ]
    )
    # Load the data into a json object
    json_data = json.loads(t.to_json())
    # Save the file to disk
    save_to_file(json_data, environment, region, app_group_l)
