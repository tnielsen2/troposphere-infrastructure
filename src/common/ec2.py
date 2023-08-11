from troposphere import ec2


def sg_allow_from(ip_dictionary, startportrange, endportrange, protocol):
    """
    Function that returns a list of SecurityGroupRule objects that can be used within a SecurityGroup.
    :param ip_dictionary: Key/value object containing a name and IP address.
    :param startportrange: Integer, the start port range.
    :param endportrange: Integer, the end port range.
    :param protocol: String, the protocol to use. TCP | UDP
    :return:
    """
    rules = []
    for key, value in sorted(iter(ip_dictionary.items())):
        rules.append(
            ec2.SecurityGroupRule(IpProtocol=protocol, FromPort=startportrange, ToPort=endportrange, CidrIp=str(value),
                                  Description=str(f"{key}")))
    return rules
