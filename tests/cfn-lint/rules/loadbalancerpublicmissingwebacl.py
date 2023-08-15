from cfnlint.rules import CloudFormationLintRule, RuleMatch


class LoadbalancerPublicMissingWebAcl(CloudFormationLintRule):
    """
    Rule that warns when a public facing loadbalancer does not have a wabacl attached.
    cfn-lint cloudformation/**/*.json -a pathtomodules/tests/cfn-lint/rules/
    """

    id = "W10003"
    shortdesc = "Public Loadbalancer Missing WebAcl"
    description = "Asserts that public loadbalancers have a webacl attached."
    source_url = ""
    tags = ["loadbalancer", "wafv2"]

    def match(self, cfn):
        matches = []
        webacl_associated_resources = []
        open_security_groups = []
        # Get all webacl associated loadbalancers
        for webacl_resource_name, webacl_resource_values in cfn.get_resources(
            "AWS::WAFv2::WebACLAssociation"
        ).items():
            resource = (
                webacl_resource_values["Properties"]
                .get("ResourceArn", {})
                .get("Ref", "")
            )
            if resource:
                webacl_associated_resources.append(resource)
        # Get a list of security groups that allow unrestricted internet access
        for security_group_name, security_group_values in cfn.get_resources(
            "AWS::EC2::SecurityGroup"
        ).items():
            sg = security_group_values["Properties"].get("SecurityGroupIngress", [])
            if any(entry.get("CidrIp", "") == "0.0.0.0/0" for entry in sg):
                open_security_groups.append(security_group_name)

        # Loop through all load balancer resources
        for resource_name, resource_values in cfn.get_resources(
            "AWS::ElasticLoadBalancingV2::LoadBalancer"
        ).items():
            # Limit check to internet-facing load balancers
            if resource_values["Properties"].get("Scheme", "") == "internet-facing":
                # Check if webacl association exists, add warning if not
                if resource_name not in webacl_associated_resources:
                    # Collect ALB security groups and compare to open security groups
                    alb_security_groups = set(
                        sg_entry.get("Ref", "")
                        for sg_entry in resource_values["Properties"].get(
                            "SecurityGroups", []
                        )
                    )
                    if any(alb_security_groups.intersection(set(open_security_groups))):
                        message = f"LoadBalancer '{resource_name}': Publicly exposed loadbalancer without attached webacl detected. Exclude this stack from this rule if webacl cannot be attached."
                        matches.append(RuleMatch(["Resources", resource_name], message))

        return matches
