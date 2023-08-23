import sys
import ipaddress
import math
from troposphere import GetAZs
from troposphere import Select

vpc_settings = {
    'us-west-2': {
        'dev-a': {
            'vpc_type': 'private',
            'cidr': '10.0.0.0/21',
            'subnet_count': 3,
        },
    },
    'us-east-2': {
        'dev-a': {
            'vpc_type': 'private',
            'cidr': '10.0.8.0/21',
            'subnet_count': 3,
        }
    },
    'us-east-1': {
        'dev-a': {
            'vpc_type': 'public',
            'cidr': '10.0.16.0/21',
            'subnet_count': 3,
        }
    },
}

availability_zones = {
    'us-east-1': [
        Select(1, GetAZs('')),
        Select(2, GetAZs('')),
        Select(3, GetAZs('')),
    ],
    'us-west-1': [
        Select(0, GetAZs('')),
        Select(2, GetAZs('')),
    ],
    'us-west-2': [
        Select(0, GetAZs('')),
        Select(1, GetAZs('')),
        Select(2, GetAZs('')),
    ],
    'ap-south-1': [
        Select(0, GetAZs('')),
        Select(1, GetAZs('')),
    ],
    'ap-southeast-1': [
        Select(0, GetAZs('')),
        Select(1, GetAZs('')),
    ],
    'ap-southeast-2': [
        Select(0, GetAZs('')),
        Select(1, GetAZs('')),
        Select(2, GetAZs('')),
    ],
    'ap-northeast-1': [
        Select(1, GetAZs('')),
        Select(2, GetAZs('')),
    ],
    'ap-northeast-2': [
        Select(0, GetAZs('')),
        Select(1, GetAZs('')),
    ],
    'ap-northeast-3': [
        Select(0, GetAZs('')),
        Select(1, GetAZs('')),
    ],
    'eu-central-1': [
        Select(0, GetAZs('')),
        Select(1, GetAZs('')),
    ],
    'eu-west-1': [
        Select(0, GetAZs('')),
        Select(1, GetAZs('')),
        Select(2, GetAZs('')),
    ],
    'eu-west-2': [
        Select(0, GetAZs('')),
        Select(1, GetAZs('')),
        Select(2, GetAZs('')),
    ],
    'eu-west-3': [
        Select(0, GetAZs('')),
        Select(1, GetAZs('')),
        Select(2, GetAZs('')),
    ],
    'eu-north-1': [
        Select(0, GetAZs('')),
        Select(1, GetAZs('')),
    ],
    'sa-east-1': [
        Select(0, GetAZs('')),
        Select(1, GetAZs('')),
        Select(2, GetAZs('')),
    ],
    'us-east-2': [
        Select(0, GetAZs('')),
        Select(1, GetAZs('')),
        Select(2, GetAZs('')),
    ],
    'ca-central-1': [
        Select(0, GetAZs('')),
        Select(1, GetAZs('')),
    ],
}


def add_cidr_mapping(
    template,
    region,
    region_cidr,
    region_vpc_type,
    az_count,
):
    """

    :param template: troposphere template object
    :param region: string. Ex; us-west-2
    :param region_cidr: string. Ex; 10.0.4.0/21
    :param region_vpc_type: string. public | private
    :param az_count: Integer
    :return:
    """
    az_subnets_formatted = []
    region_cidr_netmask = str(region_cidr.split('/', 1)[1])
    if region_vpc_type == 'public':
        converted_netmask = int(region_cidr_netmask) + int(
            math.ceil(math.log(az_count, 2))
        )
    elif region_vpc_type == 'private':
        subnet_count = az_count * 2
        converted_netmask = int(region_cidr_netmask) + int(
            math.ceil(math.log(subnet_count, 2))
        )
    else:
        subnet_count = 0
        converted_netmask = 0
    if region_cidr != 'undefined':
        reformat_cidr = ipaddress.IPv4Network(region_cidr)
        az_subnets = list(reformat_cidr.subnets(new_prefix=converted_netmask))
        for ip in az_subnets:
            az_subnets_formatted.append(str(ip))
    mapping = {}
    r = region
    mapping[r] = {}
    mapping[r]['vpc'] = region_cidr
    if region_vpc_type == 'public':
        for index, subnet in enumerate(az_subnets_formatted):
            mapping[r]['publicsubnet{}'.format(index + 1)] = subnet
        template.add_mapping('CidrAllocations', mapping)
    elif region_vpc_type == 'private':
        length = len(az_subnets_formatted)
        middle_index = length // 2
        first_half = az_subnets_formatted[:middle_index]
        second_half = az_subnets_formatted[middle_index:]
        for index, subnet in enumerate(first_half):
            mapping[r]['publicsubnet{}'.format(index + 1)] = subnet
        for index, subnet in enumerate(second_half):
            mapping[r]['privatesubnet{}'.format(index + 1)] = subnet
        template.add_mapping('CidrAllocations', mapping)
    # Create subnet mapping for user type VPCs.
    elif region_vpc_type == 'user':
        # Call function to return list of allocated subnets from cidr
        public_list, private_list = generate_user_subnet_allocations(
            cidr=region_cidr, number_of_az=az_count
        )
        # Set looping index before loop
        index = 0
        # Loop through public subnets and create CF mapping into a dict
        for subnet in public_list:
            mapping[r]['publicsubnet{}'.format(index + 1)] = str(subnet)
            index = index + 1
        # Set looping index again to 0
        index = 0
        # Loop through private subnets and create CF mapping into a dict
        for subnet in private_list:
            mapping[r]['privatesubnet{}'.format(index + 1)] = str(subnet)
            index = index + 1
        # Pass dict into mapping object in our template
        template.add_mapping('CidrAllocations', mapping)


def generate_user_subnet_allocations(cidr, number_of_az):
    """
    Function that returns a list of subnet IP allocations for public and private subnets for user VPC types.
    User VPC types are used for VDI or user forced tunnel vpn termination for public IP whitelisting.
    `number_of_az` should be using `az_count` var from cf_main.
    Example usage:
    public_list, private_list = generate_user_subnet_allocations(cidr=region_cidr, number_of_az=az_count)
    """
    # Format cidr string to ipaddress object
    cidr_formatted = ipaddress.IPv4Network(cidr)
    if cidr_formatted.prefixlen >= 22:
        private_new_prefix = 24
        public_new_prefix = 26
    else:
        private_new_prefix = 24
        public_new_prefix = 25
    # Chop up the cidr into smaller subnets for public NAT gateway subnets. Depending on the prefix size depends on
    # how big we make our public subnet
    public_cidr_chopped = list(
        cidr_formatted.subnets(new_prefix=public_new_prefix)
    )
    # Use the first available small subnets and allocated as many as there are for AZs declared in the region
    public_cidrs = public_cidr_chopped[:number_of_az]
    # Allocate the VPC cidr into /24 subnets into a variable for comparison
    private_cidr_chopped = list(
        cidr_formatted.subnets(new_prefix=private_new_prefix)
    )
    # Create variable for popping indexes off of when an overlapping public subnet is found
    usable_private_cidrs = private_cidr_chopped
    # Loop through and compare public and private subnets and ensure there is no overlap.
    for public_cidr in public_cidrs:
        for private_cidr in private_cidr_chopped:
            # If the public CIDR overlaps with the private subnets, then remove it as a usable cidr
            if public_cidr.overlaps(private_cidr):
                usable_private_cidrs.remove(private_cidr)
    # Attempt to summarize the usable private subnets into larger subnets for maximum allocation
    summarized_cidrs = []
    # # Build list of summarized cidrs of all remaining subnets, but only of usable ones that do not overlap with public
    for public_cidr in public_cidrs:
        for private_cidr in usable_private_cidrs:
            if not public_cidr.overlaps(private_cidr.supernet()):
                if private_cidr.supernet() not in summarized_cidrs:
                    summarized_cidrs.append(private_cidr.supernet())
    # if the remaining usable subnet split is even to the amount of az, then use the summarized cidrs
    if len(summarized_cidrs) == number_of_az:
        private_cidrs = summarized_cidrs
    # Otherwise if divisible by the amount of azs, then double the summary routes for better allocation
    elif len(summarized_cidrs) % number_of_az == 0:
        prefix_diff = 1
        new_list = []
        for public_cidr in public_cidrs:
            for cidr in usable_private_cidrs:
                if public_cidr.overlaps(cidr):
                    usable_private_cidrs.remove(cidr)
                elif cidr.supernet(prefixlen_diff=prefix_diff) not in new_list:
                    new_list.append(cidr.supernet(prefixlen_diff=prefix_diff))
        private_cidrs = new_list[:number_of_az]
    # if not equal or divisible by the number_of_az, then assign a /24 per subnet
    else:
        private_cidrs = usable_private_cidrs[:number_of_az]
    # If the amount of cidr allocations per AZ do not match with the same count (3x for public, 3x for private for
    # example), then error with a message of supported az counts and allocations.
    if not len(private_cidrs) >= len(public_cidrs):
        print(
            f"""
        User CIDR {cidr} cannot be allocated with the amount of availability zones declared in cf_availability_zones \
        ({number_of_az}).
        The following AZ counts and subnet sizes are supported for this VPC type (user):
        /22 2 azs, 3 azs
        /21 2 azs, 3 azs, 4 azs, 5 azs

        Be sure to allocate the proper subnet and AZ count prior to deploying your VPC. 
        """
        )
        sys.exit(1)
    # Assign these to their own value because if we don't the list type is not properly returned.
    public_cidrs_list = list(public_cidrs)
    private_cidrs_list = list(private_cidrs)
    # Return a list of cidr allocations in a string readable format
    return public_cidrs_list, private_cidrs_list
