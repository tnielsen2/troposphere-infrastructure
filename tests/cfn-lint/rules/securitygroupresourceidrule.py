import re

from cfnlint.rules import CloudFormationLintRule, RuleMatch


class SecurityGroupResourceIdRule(CloudFormationLintRule):
    """
    Rule that enforces security group resource ID names.
    https://yamww.atlassian.net/wiki/spaces/AWS/pages/34392976/AWS+EC2+Security+Group+Architecture#Resource-Names
    Example usage to test this from the root of an infrastructure repo
    cfn-lint cloudformation/**/*.json -a pathtomodules/tests/cfn-lint/rules/
    """

    id = "W11001"
    shortdesc = "Invalid security group resource ID."
    description = "Security Group resource ID does not match approved format."
    source_url = "https://yamww.atlassian.net/wiki/spaces/AWS/pages/34392976/AWS+EC2+Security+Group+Architecture#Resource-Names"
    tags = ["ec2", "security-group", "regex"]

    def match(self, cfn):
        matches = []

        # Define the approved resource name regex patterns
        # Admin security groups can be any string before the string "AdminSecurityGroup" These are created with a
        #   function and are consistent when invoked via cf-modules.
        #   Example: bianalyticsdbfivetranrrmysqlAdminSecurityGroup
        # Default security groups are strict.
        #   Example: defaultSecurityGroup
        # 'defaultRestore' security groups are strict. This is created when a stack is restored from backup.
        #   Example: defaultRestoreSecurityGroup
        # Exclude security groups generated by RDS module for dumping DBs to S3.
        #   Example: starshiprdsdumpSecurityGroup
        # Exemption security groups have any string before the string "exemptionSecurityGroup. These are created with
        #   a function and are consistent when invoked via cf-modules.
        #   Example: sre7736exemptionSecurityGroup.
        # Stack security groups must have a public or private string in them to identify what kind of IP traffic it
        #   serves with the type of resource. Approved resource_types are declared in the below `resource_types` variable.
        #   Example: ec2PublicSecurityGroup, ecsPrivateSecurityGroup
        #   Conditionally, some security groups might use a prefix list that takes up more rule assignments that require
        #   their own dedicated security group. These are denoted with the term "Prefix" in them.
        #   Exammple: albPublicPrefixSecurityGroup, albPrivatePrefixSecurityGroup
        desired_match_re = "(.*Admin|default|defaultRestore|.*Dump|.*exemption|(resource_type)Public|(resource_type)PublicPrefix|(resource_type)Private|(resource_type)PrivatePrefix)(SecurityGroup)"
        resource_types = [
            "alb",  # Application load balancer
            "asg",  # Autoscaling group
            "cache",  # Elasticache instance
            "default",  # Default security group used for apps requiring overly permissive access. Ex. ICMP
            "ec2",  # EC2 instances
            "ecs",  # ECS services
            "efs",  # EFS instances
            "glue",  # Glue connections/resources
            "lambda",  # Lambda functions
            "privateLinkEndpoint",  # AWS PrivateLink endpoints
            "r53",  # R53 Resolver endpoints
            "rds",  # RDS instances
            "rdsProxy",  # RDS Proxy instances
            "rdsProxyEndpoint",  # RDS Proxy VPC endpoints
            "redshift",  # Redshift instances
            "mwaa",  # Managed Workflows for Apache Airflow
            "nlb",  # Network load balancer
            "vpn",
        ]  # SSLVPN endpoints
        # replace 'resource_type' string in desired_match_re for readability of resource_types
        regex_pattern = desired_match_re.replace(
            "resource_type", "(?:" + "|".join(resource_types) + ")"
        )

        # Loop through all SecurityGroup resources in the CloudFormation template
        for resource_name, resource in cfn.get_resources(
            "AWS::EC2::SecurityGroup"
        ).items():
            if not re.match(regex_pattern, resource_name):
                message = f"SecurityGroup '{resource_name}' resource ID does not match approved formatting."
                matches.append(RuleMatch(["Resources", resource_name], message))

        return matches