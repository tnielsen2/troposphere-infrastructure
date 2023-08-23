import ipaddress
from cfnlint.rules import CloudFormationLintRule, RuleMatch


class SecurityGroupTypeRule(CloudFormationLintRule):
    """
    Rule that enforces rule types, public or private.
    This rule ensures that the IP address type is assigned to match the resource type Public vs Private.
    Asserts RFC1918 rules and SG sourced rules are applied to SGs labeled with the word 'private', and only public
    IP addresses are applied to SGs labeled with the word 'public'
    Example usage to test this from the root of an infrastructure repo
    cfn-lint cloudformation/**/*.json -a pathtomodules/tests/cfn-lint/rules/
    """

    id = 'W10002'
    shortdesc = 'Invalid ruleset with security group type.'
    description = (
        'Asserts security groups have rulesets that match the named type'
    )
    tags = ['ec2', 'security-group', 'regex']

    def match(self, cfn):
        # Define the RFC1918 private address space ranges
        rfc_1918_10x = ipaddress.ip_network('10.0.0.0/8')
        rfc_1918_172x = ipaddress.ip_network('172.16.0.0/12')
        matches = []
        # Loop through all the AWS::EC2::SecurityGroup resources
        for resource_name, resource_values in cfn.get_resources(
            'AWS::EC2::SecurityGroup'
        ).items():
            # Check if the resource name contains the word 'private'
            if 'private' in resource_name.lower():
                # Loop through the SecurityGroupIngress properties
                for prop_name, prop_value in resource_values[
                    'Properties'
                ].items():
                    if prop_name == 'SecurityGroupIngress':
                        for ingress in prop_value:
                            # Check if the ingress rule contains a SG source rule
                            if 'SourceSecurityGroupId' in ingress:
                                continue
                            # Check if the ingress rule contains a CIDR IP
                            elif 'CidrIp' in ingress:
                                cidr_network = ipaddress.ip_network(
                                    ingress['CidrIp']
                                )
                                # Check if the CIDR IP is not a subset of the RFC1918 private address space
                                if not (
                                    cidr_network.subnet_of(rfc_1918_10x)
                                    or cidr_network.subnet_of(rfc_1918_172x)
                                ):
                                    # If the CIDR IP is not a subset of the RFC1918 private address space, add a match
                                    message = f"SecurityGroup '{resource_name}': Private resource should allow only RFC1918 space and other security group ingress rules."
                                    matches.append(
                                        RuleMatch(
                                            [
                                                'Resources',
                                                resource_name,
                                                'Properties',
                                                prop_name,
                                            ],
                                            message,
                                        )
                                    )
            # Check if the resource name contains the word 'public'
            elif 'public' in resource_name.lower():
                # Loop through the SecurityGroupIngress properties
                for prop_name, prop_value in resource_values[
                    'Properties'
                ].items():
                    if prop_name == 'SecurityGroupIngress':
                        for ingress in prop_value:
                            # If the ingress rule is a source security group, add a match
                            if 'SourceSecurityGroupId' in ingress:
                                matches.append(
                                    RuleMatch(
                                        [
                                            'Resources',
                                            resource_name,
                                            'Properties',
                                            prop_name,
                                        ],
                                        'Public resource should allow only public IP ingress rules and not SG ingress rules',
                                    )
                                )
                            # Check if the ingress rule contains a CIDR IP
                            elif 'CidrIp' in ingress:
                                cidr_network = ipaddress.ip_network(
                                    ingress['CidrIp']
                                )
                                # Check if the CIDR IP is a subset of the RFC1918 private address space
                                if cidr_network.subnet_of(
                                    rfc_1918_10x
                                ) or cidr_network.subnet_of(rfc_1918_172x):
                                    # If the CIDR IP is a subset of the RFC1918 private address space, add a match
                                    message = f"SecurityGroup '{resource_name}': Public resource should allow only public IP space CIDRs and not RFC1918 subnets."
                                    matches.append(
                                        RuleMatch(
                                            [
                                                'Resources',
                                                resource_name,
                                                'Properties',
                                                prop_name,
                                            ],
                                            message,
                                        )
                                    )

        return matches
