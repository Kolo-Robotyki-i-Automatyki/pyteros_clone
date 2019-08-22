import importlib


def create_obj_from_path(class_path: str, *args, **kwargs):
    module_name, class_name = class_path.rsplit('.', 1)
    imported_module = importlib.import_module(module_name)
    class_obj = getattr(imported_module, class_name)
    return class_obj(*args, **kwargs)
