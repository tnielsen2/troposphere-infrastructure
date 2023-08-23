import ipaddress
from cfnlint.rules import CloudFormationLintRule, RuleMatch


class SecurityGroupOverlyPermissiveRule(CloudFormationLintRule):
    """
    Rule that enforces rule types, public or private.
    This rule ensures that the IP address type is assigned to match the resource type Public vs Private.
    Asserts RFC1918 rules and SG sourced rules are applied to SGs labeled with the word 'private', and only public
    IP addresses are applied to SGs labeled with the word 'public'
    Example usage to test this from the root of an infrastructure repo
    cfn-lint cloudformation/**/*.json -a pathtomodules/tests/cfn-lint/rules/
    """

    id = "W10001"
    shortdesc = "Overly permissive ingress rule"
    description = (
        "Asserts security groups are not overly permissive. "
        "Anything requiring overly permissive access must be excluded."
    )
    tags = ["ec2", "security-group", "regex"]

    def match(self, cfn):
        # Define the RFC1918 private address space ranges
        overly_permissive_subnets = [
            ipaddress.ip_network("10.0.0.0/8"),
            ipaddress.ip_network("172.16.0.0/12"),
            ipaddress.ip_network("0.0.0.0/0"),
        ]
        matches = []
        # Loop through all the AWS::EC2::SecurityGroup resources
        for resource_name, resource_values in cfn.get_resources(
            "AWS::EC2::SecurityGroup"
        ).items():
            # Skip default security group rules
            if resource_name == "defaultSecurityGroup":
                continue
            for prop_name, prop_value in resource_values["Properties"].items():
                if prop_name == "SecurityGroupIngress":
                    for ingress in prop_value:
                        # Check if the ingress rule contains a CIDR IP
                        if "CidrIp" in ingress:
                            ingress_cidr = ipaddress.ip_network(ingress["CidrIp"])
                            for permissive_cidr in overly_permissive_subnets:
                                if ingress_cidr == permissive_cidr:
                                    message = f"SecurityGroup '{resource_name}': Overly permissive rule {ingress_cidr} detected. Exclude this stack from this rule if overly permissive rules are required."
                                    matches.append(
                                        RuleMatch(
                                            [
                                                "Resources",
                                                resource_name,
                                                "Properties",
                                                prop_name,
                                            ],
                                            message,
                                        )
                                    )

        return matches
