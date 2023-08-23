import os
import json


def save_to_file(template, environment, region, stack_name):
    """
    :param stack_name: Name of the stack
    :param template: Troposphere template object
    :param environment: string, the environment name
    :param region: AWS region, i.e. us-west-2
    :return:
    """
    settings_dir = f'./cfn/{environment}/{region}'
    os.makedirs(
        settings_dir, exist_ok=True
    )  # Recursively create directories if they don't exist

    settings_file_path = os.path.join(settings_dir, f'{stack_name}.json')
    with open(settings_file_path, 'w+') as outfile:
        json.dump(template, outfile, indent=2)
