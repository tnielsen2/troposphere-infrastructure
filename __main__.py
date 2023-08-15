import importlib
import os
import src.common.global_parameters as gp


def import_and_execute_functions(directory):
    """
    Crawl the passed directory recursively and execute the create_cfn_template function
    contained within each module, passing environment and region arguments.
    :param directory: Directory to crawl. Can pass relative or absolute path.
    :param cfn_environment: The environment argument to pass to create_cfn_template.
    :param cfn_region: The region argument to pass to create_cfn_template.
    :return:
    """
    for folder_name in os.listdir(directory):
        folder_path = os.path.join(directory, folder_name)
        if os.path.isdir(folder_path):
            for module_name in os.listdir(folder_path):
                if module_name.endswith(".py") and module_name != "__init__.py":
                    module_name = module_name[:-3]  # Remove .py extension
                    full_module_name = f"src.{folder_name}.{module_name}"
                    module = importlib.import_module(full_module_name)
                    if hasattr(module, "create_cfn_template") and callable(
                        module.create_cfn_template
                    ):
                        if hasattr(module, "stack_regions"):
                            stack_regions = module.stack_regions
                        else:
                            stack_regions = gp.global_regions
                        if hasattr(module, "stack_environments"):
                            stack_envs = module.stack_environments
                        else:
                            stack_envs = gp.global_environments
                        for cfn_region in stack_regions:
                            for cfn_environment in stack_envs:
                                module.create_cfn_template(cfn_environment, cfn_region)


if __name__ == "__main__":
    import_and_execute_functions("./src")
