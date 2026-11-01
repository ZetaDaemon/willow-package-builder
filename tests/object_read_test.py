from willow_package_builder.objects import reader
from pathlib import Path

folder_path = Path("example uc/ExamplePackage/Objects")


declarations = reader.walk_objects_directory(folder_path)
for declaration in declarations:
    print(type(declaration).__name__, reader.object_path(declaration))
