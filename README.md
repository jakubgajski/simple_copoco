### Overview

Effortlessly transition from YAML configuration to Python object management with the Simple Config Powered Code package.

### Installation
```bash
pip install simple-copoco
```

### Why don't you just use OmegaConf + Hydra?  
OmegaConf + Hydra duet is fantastic and great (also literally). So there are some reasons to search for alternatives:  

1. Simplicity: The simple-copoco utility is designed to be lightweight and easy to use. If you have a project with straightforward configuration needs, simple-copoco provides an intuitive and easy to learn way to manage objects via configuration without the need for additional complexity.
2. Integration of  configuration with object registration: simple-copoco offers features for object registration, allowing you to register and manage classes dynamically. If your project involves dynamic class instantiation based on configuration, simple-copoco provides a convenient way to achieve this.
3. Grid Configurations: simple-copoco includes a GridManager for handling grids of YAML configurations, which can be useful for scenarios where you need to explore multiple configuration combinations in you experiments (whatever you do).

### Getting Started
**Handling YAML Configurations**  
Consider the following YAML configuration:
```yaml
berries:
  color: blue
  amount: 5
coconuts:
  amount: 1
```
In Python:

```python
from simple_copoco import ConfigManager

# config path
config_path = '~/path/to/config.yaml'
config_template_path = '~/path/to/template.yaml'  # optional, possibly wide, general config with many defaults

# Option 1: template will be updated with provided config
cfg_manager = ConfigManager(config_path, config_template_path)
# Option 2: template doesn't exist
cfg_manager = ConfigManager(config_path)

my_config = cfg_manager.cfg

# access config attributes
how_many_berries_to_buy = my_config.berries.amount
what_color_of_berries_to_buy = my_config.berries.color

# dump config
cfg_manager.save_to_disk('~/where/to/save.yaml')
```
**Managing Grids of YAML Configurations**  
Consider the following YAML grid:
```yaml
berries:
  color: [red, green, yellow]
  amount: [5, 10, 15]
coconuts:
  amount: [1, 3]
```
In Python:
```python
from simple_copoco import GridManager

# Specify paths
grid_path = '~/path/to/grid.yaml'
config_path = '~/path/to/config.yaml'
config_template_path = '~/path/to/template.yaml' # optional

# Grid manager will create all possible combinations of settings from grid.yaml
grid_manager = GridManager(grid_path, config_path, config_template_path)

# Grid manager is a generator
first_config_manager = grid_manager.next()
second_config_manager = grid_manager.next()

# Total number of config managers
total_of_config_managers = len(grid_manager)

first_config = first_config_manager.cfg
```
**Object Registration**
```python
from torch import nn
from simple_copoco import Register, register_as, RegistrableMixin

@register_as('utility_layer')
class CustomLayer(nn.Module):
    def __init__(self):
        super(CustomLayer, self).__init__()
    ...

register = Register(nn.Module, include_parent=False)
# register.buit_ins -> Dictionary of all classes inheriting directly or indirectly from nn.Module
# that weren't registered with @register_as.
# register.utility_layer -> Dictionary of classes inheriting from nn.Module registered as "utility_layer"

# another use case, when submodules of a package are not being imported
# with their parent. It happens, when the package has complex directory tree
# and uses blank __init__.py files.
from .. import custom_layers # custom_modules has some submodules

register = Register(nn.Module, custom_layers)

@register_as('classifier_head')
class CustomHead(nn.Module):
    def __init__(self):
        super(CustomHead, self).__init__()
    ...

# Update the register with the current namespace
register.update_register()
# register.classifier_head -> dict of all the classes in the namespace inheriting from nn.Module
# registered as "classifier_head"

# Add a class (that has been registered after Register initialisation) to the register manually
register.extend(CustomHead)

class AnyClass:
    ...

def some_func():
    ...

# Register anything
register.extend('other_classes', 'AnyClass', AnyClass)
register.extend('functions', 'some_function', some_func)  # name in the register doesn't need to the same
  
# Register hint :)  
register = Register(RegistrableMixin)  
# registers anything within the namespace that inherits from RegistrableMixin
# because @register_as() injects RegistrableMixin as a parent class (but this inheritance will be ignored in children
# if passes_on_children == False).
```
**Putting It All Together**  
Consider the following configuration:
```yaml
core:
  use: OtherModule
  params:
    a: 1
    b: 2
head:
  use: CustomHead
  params:
    x: 1
    y: 1
```
In Python:
```python
from torch.nn import Module
from simple_copoco import Register, register_as
from simple_copoco import ConfigManager


@register_as('core', passes_on_children=True)
class CustomModule(Module):
    ...

class OtherModule(CustomModule):
    ...

@register_as('head')
class CustomHead(Module):
    ...

register = Register(Module)
cfg_man = ConfigManager('path/to/some_config.yaml', 'path/to/config_template.yaml')
cfg = cfg_man.cfg

# Create dynamic code based on configuration.
# Attributes are accessible by dot notation, but you can use ** to unpack them, just like with dictionaries.
# It makes experimentation with different architectures and many sets of parameters a breeze.

class MemesClassifier(Module):
    
    def __init__(self, cfg, register):
        self.model_core = register.core[cfg.core.type](**cfg.core.params)
        self.classifier_head = register.head[cfg.head.type](**cfg.head.params)
        
    ...
```
