import ipaddress

from troposphere_infrastructure.src.common.vpc import vpc_settings


#####
##### Test file for validating that we are not assigning overlapping or duplicated ranges in cf_environments.
#####


# Loop through cf environments and pull down all cidrs into a flat key/value dictionary
def get_network_dict():
    # Declare an empty list for ipaddress objects representing each network for comparison
    network_objects = {}
    # Loop through all cidrs and convert from string type to ipaddress type
    for region in vpc_settings:
        for environment in vpc_settings[region]:
            network_objects[f"{environment}.{region}"] = vpc_settings[region][
                environment
            ]["cidr"]
    return network_objects


# Validate the address of a subnet is valid
def validate_ip_network(address):
    retval = True
    try:
        ip = ipaddress.ip_network(address)
    except ValueError:
        retval = False
    return retval


# Test all environments to ensure we dont have overlaps or duplicates
def test_environments():
    cidrs = get_network_dict()
    ipcheck = True
    assert_error = ""
    for k in cidrs:
        if validate_ip_network(cidrs[k]):
            # Compare to all defined networks
            for i in cidrs:
                # Skip compare to self
                if k != i:
                    if validate_ip_network(cidrs[i]):
                        if ipaddress.ip_network(cidrs[k]).overlaps(
                            ipaddress.ip_network(cidrs[i])
                        ):
                            assert_error += "\n{} ({}) overlaps {} ({})".format(
                                cidrs[i], i, cidrs[k], k
                            )
                            ipcheck = False

        else:
            ipcheck = False
            assert_error += "\n{} ({}) is not a valid ip network".format(cidrs[k], k)

    assert ipcheck is True, assert_error
