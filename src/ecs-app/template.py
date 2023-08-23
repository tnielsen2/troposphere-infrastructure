#!/usr/bin/env python3
import json

from ..common.file_utils import save_to_file
from ..common.ec2 import sg_allow_from
import troposphere.ec2 as ec2
import troposphere.ecs as ecs
import troposphere.efs as efs
import troposphere.elasticloadbalancingv2 as elb
from troposphere.route53 import RecordSetType, AliasTarget
from troposphere import ImportValue, Template, Ref, GetAtt
from troposphere.s3 import *

#### Generation vars
stack_regions = ["us-west-2"]
stack_environments = ["dev-a"]

#### Stack vars
# Variable for Route53 resource creation https://docs.aws.amazon.com/general/latest/gr/elb.html
alb_hosted_zone_ids = {
    "us-east-2": "ZLMOA37VPKANP",
    "us-east-1": "Z26RNL4JYFTOTI",
    "us-west-2": "Z18D5FSROUN65G",
}
app_group = "ecs-app"

### VPC vars
cidr = "10.175.0.0/24"

### Security group vars
sg_ingress_rules = []
sg_ingress_rules += sg_allow_from({"public": "0.0.0.0/0"}, 2456, 2458, "udp")
sg_ingress_rules += sg_allow_from({"public": "0.0.0.0/0"}, 80, 80, "tcp")

app_domain = "pxg-sandbox-sre.yamww.cloud"

### ECS Vars
environment_variables = [
    ecs.Environment(Name="SERVER_NAME", Value="Desert-Dwellers"),
    ecs.Environment(Name="SERVER_PORT", Value="2456"),
    ecs.Environment(Name="WORLD_NAME", Value="DESERT-DWELLERS-WORLD"),
    ecs.Environment(Name="SERVER_PUBLIC", Value="true"),
    ecs.Environment(Name="UPDATE_INTERVAL", Value="900"),
    ecs.Environment(Name="BACKUPS_INTERVAL", Value="3600"),
    ecs.Environment(Name="BACKUPS_DIRECTORY", Value="/config/backups"),
    ecs.Environment(Name="BACKUPS_MAX_AGE", Value="3"),
    ecs.Environment(Name="BACKUPS_DIRECTORY_PERMISSIONS", Value="755"),
    ecs.Environment(Name="BACKUPS_FILE_PERMISSIONS", Value="644"),
    ecs.Environment(Name="CONFIG_DIRECTORY_PERMISSIONS", Value="755"),
    ecs.Environment(Name="WORLDS_DIRECTORY_PERMISSIONS", Value="755"),
    ecs.Environment(Name="WORLDS_FILE_PERMISSIONS", Value="644"),
    ecs.Environment(Name="DNS_1", Value="1.1.1.1"),
    ecs.Environment(Name="DNS_2", Value="8.8.8.8"),
    ecs.Environment(Name="STEAMCMD_ARGS", Value="validate"),
    ecs.Environment(Name="STATUS_HTTP", Value="true"),
    ecs.Environment(Name="STATUS_HTTP_PORT", Value="80"),
    ecs.Environment(Name="SERVER_PASS", Value="br0d0wn"),
    # Webhook url from variable declared above
    ecs.Environment(
        Name="PRE_START_HOOK",
        Value='curl -sfSL -X POST -H "Content-Type: application/json" -d "{"username":"Valheim","content":"Valheim server is starting up."}" "$DISCORD_WEBHOOK"',
    ),
    ecs.Environment(
        Name="POST_START_HOOK",
        Value='curl -sfSL -X POST -H "Content-Type: application/json" -d "{"username":"Valheim","content":"Valheim server has completed starting."}" "$DISCORD_WEBHOOK"',
    ),
    ecs.Environment(
        Name="VALHEIM_LOG_FILTER_CONTAINS_Spawned",
        Value="Got character ZDOID from",
    ),
    ecs.Environment(
        Name="ON_VALHEIM_LOG_FILTER_CONTAINS_Spawned",
        Value="""{ read l; l=${l//*ZDOID from /}; l=${l// :*/}; msg="Player $l spawned into the world"; curl -sfSL -X POST -H "Content-Type: application/json" -d "{\"username\":\"Valheim\",\"content\":\"$msg\"}" "$DISCORD_WEBHOOK"; }""",
    ),
]

# Declare EFS mounts here
efs_volumes = [
    {
        "efs_volume_config": {
            "filesystem_id": Ref("efsfilesystem"),
            "filesystem_path": "/",
        },
        "task_volume_config": {
            "task_volume_name": "data-vol",
            "container_path": "/config",
        },
    }
]

# Dynamic Variables
app_group_l = app_group.lower()
app_group_ansi = app_group_l.replace("-", "")


def create_cfn_template(environment, region):
    vpc_id = ImportValue(f"{environment}-{app_group_l}-vpc-id")
    subnets = [
        ImportValue(f"{environment}-{app_group_l}-privatesubnet1-ID"),
        ImportValue(f"{environment}-{app_group_l}-privatesubnet2-ID"),
        ImportValue(f"{environment}-{app_group_l}-privatesubnet3-ID"),
    ]
    az = f"{region}a"
    # Pull In Tags
    default_tags = (
        Tags(Business="LAB")
        + Tags(Service=app_group_l)
        + Tags(ExtendedName=f"{environment}-{region}-{app_group_l}")
    )

    # Prepare Template
    t = Template()
    t.set_description(f"{environment}: LAB - {app_group} Infrastructure")
    t.set_metadata(
        {
            "cfn-lint": {
                "config": {
                    # Do not alert for overly permissive rules, this has a dedicated VPC and no security risk
                    "ignore_checks": [
                        "W10001",
                        # Do not alert for hard coding AZs, this is fine for this use case
                        "W3010",
                    ]
                }
            }
        }
    )

    #### Start Security Group Resources
    # Provision the Public Security Group
    nlbPublicSecurityGroup = t.add_resource(
        ec2.SecurityGroup(
            "nlbPublicSecurityGroup",
            GroupDescription=f"{environment}: {app_group} Public Security Group",
            VpcId=vpc_id,
            SecurityGroupIngress=sg_ingress_rules,
            Tags=default_tags + Tags(Name=f"{environment}-{app_group_l}-sg"),
        )
    )

    # Provision self referencing rule for Private SG
    SelfReferencingRule = t.add_resource(
        ec2.SecurityGroupIngress(
            "SelfReferencingRule",
            GroupId=Ref(nlbPublicSecurityGroup),
            IpProtocol="-1",
            SourceSecurityGroupId=Ref("nlbPublicSecurityGroup"),
            FromPort="1",
            ToPort="65535",
            # DependsOn="SecurityGroup",
        )
    )
    #### End Security Group Resources

    #### Start EFS resources
    efsfilesystem = t.add_resource(
        efs.FileSystem("efsfilesystem", FileSystemTags=default_tags)
    )
    for efs_mount_subnet in subnets:
        index = str(subnets.index(efs_mount_subnet))
        efsmounttarget = t.add_resource(
            efs.MountTarget(
                f"{app_group_ansi}efsMountTarget{index}",
                FileSystemId=Ref(efsfilesystem),
                SecurityGroups=[Ref(nlbPublicSecurityGroup)],
                SubnetId=efs_mount_subnet,
            )
        )

    #### End EFS resources

    #### Start NLB resources
    networkloadbalancer = t.add_resource(
        elb.LoadBalancer(
            "networkloadbalancer",
            Type="network",
            Scheme="internet-facing",
            Subnets=subnets,
            Tags=default_tags + Tags(Component="Load-Balancer"),
        )
    )

    # Configure the app target group for udp 2456
    udp2456tg = t.add_resource(
        elb.TargetGroup(
            "udp2456tg",
            Port=2456,
            TargetType="ip",
            HealthCheckPort="80",
            HealthCheckProtocol="TCP",
            Protocol="UDP",
            VpcId=vpc_id,
            DependsOn="networkloadbalancer",
        )
    )

    udp2456listener = t.add_resource(
        elb.Listener(
            "udp2456listener",
            Port="2456",
            Protocol="UDP",
            LoadBalancerArn=Ref(networkloadbalancer),
            DefaultActions=[elb.Action(Type="forward", TargetGroupArn=Ref(udp2456tg))],
            # DependsOn="networkloadbalancer",
        )
    )

    # Configure the app target group for udp 2457
    udp2457tg = t.add_resource(
        elb.TargetGroup(
            "udp2457tg",
            Port=2457,
            TargetType="ip",
            Protocol="UDP",
            HealthCheckPort="80",
            HealthCheckProtocol="TCP",
            VpcId=vpc_id,
            DependsOn="networkloadbalancer",
        )
    )

    udp2457listener = t.add_resource(
        elb.Listener(
            "udp2457listener",
            Port="2457",
            Protocol="UDP",
            LoadBalancerArn=Ref(networkloadbalancer),
            DefaultActions=[elb.Action(Type="forward", TargetGroupArn=Ref(udp2457tg))],
            # DependsOn="networkloadbalancer",
        )
    )

    # Configure the app target group for udp 2457
    udp2458tg = t.add_resource(
        elb.TargetGroup(
            "udp2458tg",
            Port=2458,
            TargetType="ip",
            Protocol="UDP",
            HealthCheckPort="80",
            HealthCheckProtocol="TCP",
            VpcId=vpc_id,
            DependsOn="networkloadbalancer",
        )
    )

    udp2458listener = t.add_resource(
        elb.Listener(
            "udp2458listener",
            Port="2458",
            Protocol="UDP",
            LoadBalancerArn=Ref(networkloadbalancer),
            DefaultActions=[elb.Action(Type="forward", TargetGroupArn=Ref(udp2458tg))],
            # DependsOn="networkloadbalancer",
        )
    )

    # Configure the app target group for udp 2457
    tcp80tg = t.add_resource(
        elb.TargetGroup(
            "tcp80tg",
            Port=80,
            TargetType="ip",
            Protocol="TCP",
            VpcId=vpc_id,
            DependsOn="networkloadbalancer",
        )
    )

    tcp80listener = t.add_resource(
        elb.Listener(
            "tcp80listener",
            Port="80",
            Protocol="TCP",
            LoadBalancerArn=Ref(networkloadbalancer),
            DefaultActions=[elb.Action(Type="forward", TargetGroupArn=Ref(tcp80tg))],
            # DependsOn="networkloadbalancer",
        )
    )
    #### End NLB resources

    #### Start ECS resources
    cluster = t.add_resource(
        ecs.Cluster(
            "cluster",
            ClusterName=f"{environment}-{app_group_l}-cluster",
            Tags=default_tags + Tags(Component="ECS-Cluster"),
        )
    )
    #
    ## Loop through all declared volumes and present them to the task definition
    task_definition_volume_list = []
    container_mount_points = []
    for volume in efs_volumes:
        efs_volume_config = ecs.EFSVolumeConfiguration(
            FilesystemId=volume["efs_volume_config"]["filesystem_id"],
            RootDirectory=volume["efs_volume_config"]["filesystem_path"],
        )
        efs_volume = ecs.Volume(
            EFSVolumeConfiguration=efs_volume_config,
            Name=volume["task_volume_config"]["task_volume_name"],
        )
        task_definition_volume_list.append(efs_volume)
        # Create mount points for the container being deployed
        container_mount_points.append(
            ecs.MountPoint(
                ContainerPath=volume["task_volume_config"]["container_path"],
                SourceVolume=volume["task_volume_config"]["task_volume_name"],
            )
        )

    # Define the application task(s)
    containerdefinition = [
        ecs.ContainerDefinition(
            Name=f"{environment}-{app_group_l}",
            Environment=environment_variables,
            Image="lloesche/valheim-server",
            MountPoints=container_mount_points,
            Cpu=2048,
            Memory=4096,
            Essential=True,
            PortMappings=[
                ecs.PortMapping(ContainerPort=2456, Protocol="udp"),
                ecs.PortMapping(ContainerPort=2457, Protocol="udp"),
                ecs.PortMapping(ContainerPort=2458, Protocol="udp"),
                ecs.PortMapping(ContainerPort=80, Protocol="tcp"),
            ],
        )
    ]

    # Configure the ECS Task Definition
    task_definition = t.add_resource(
        ecs.TaskDefinition(
            "TaskDefinition",
            Cpu="2048",
            Memory="4096",
            NetworkMode="awsvpc",
            Family=f"{environment}-{app_group_l}",
            # ExecutionRoleArn=Ref(ecs_role),
            RequiresCompatibilities=["FARGATE"],
            ContainerDefinitions=containerdefinition,
            Tags=default_tags + Tags(Component="ECS"),
        )
    )

    # Present the volumes to the task definition if declared
    if task_definition_volume_list:
        task_definition.Volumes = []
        for volume in task_definition_volume_list:
            task_definition.Volumes.append(volume)

    # Configure the ECS Service
    service = t.add_resource(
        ecs.Service(
            "service",
            Cluster=Ref(cluster),
            PlatformVersion="1.4.0",
            DesiredCount=1,
            TaskDefinition=Ref(task_definition),
            LaunchType="FARGATE",
            SchedulingStrategy="REPLICA",
            NetworkConfiguration=ecs.NetworkConfiguration(
                AwsvpcConfiguration=ecs.AwsvpcConfiguration(
                    AssignPublicIp="ENABLED",
                    Subnets=subnets,
                    SecurityGroups=[Ref(nlbPublicSecurityGroup)],
                )
            ),
            LoadBalancers=[
                ecs.LoadBalancer(
                    ContainerName=f"{environment}-{app_group_l}",
                    ContainerPort=int(2456),
                    TargetGroupArn=Ref(udp2456tg),
                ),
                ecs.LoadBalancer(
                    ContainerName=f"{environment}-{app_group_l}",
                    ContainerPort=int(2457),
                    TargetGroupArn=Ref(udp2457tg),
                ),
                ecs.LoadBalancer(
                    ContainerName=f"{environment}-{app_group_l}",
                    ContainerPort=int(2458),
                    TargetGroupArn=Ref(udp2458tg),
                ),
            ],
            Tags=default_tags + Tags(Component="ECS"),
            PropagateTags="TASK_DEFINITION",
        )
    )

    #### End ECS resources

    #### Start Route53 resources
    dnsRecord = t.add_resource(
        RecordSetType(
            "dnsRecord",
            HostedZoneName=f"{app_domain}.",
            Comment=f"{environment}-{region}-{app_group_l} domain record",
            Name=f"vh.{app_domain}",
            Type="A",
            AliasTarget=AliasTarget(
                HostedZoneId=alb_hosted_zone_ids[region],
                DNSName=GetAtt("networkloadbalancer", "DNSName"),
            ),
        )
    )
    #### End Route53 resources

    # Load the Troposphere object into a JSON object
    json_data = json.loads(t.to_json())

    # Save the file to disk
    save_to_file(json_data, environment, region, app_group_l)
