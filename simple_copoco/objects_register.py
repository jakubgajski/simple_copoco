import importlib
import pkgutil
from functools import wraps
from types import ModuleType

import multipledispatch
from collections import defaultdict
from collections.abc import Callable
from typing import Optional


def register_as(register_section: str = 'default', passes_on_children: bool = False):
    """
    Decorator for preparing classes to be registered as objects of given kind.
    If auto_import == False, you have to import decorated class explicitly.

    Parameters
    ----------
    register_section : str
        An attribute of the register to hold this kind of object.
    passes_on_children: bool
        If True, all the descendants of the decorated class will be registered as well, in the same Register attribute.
    """

    def decorator(cls: type):
        @wraps(cls)
        def wrapper():
            def init_subclass(cls, /, **kwargs):
                """
                Prevent subclass from being initialized with inheritance of RegistrableMixin.

                Parameters
                ----------
                cls: type
                    The new subclass.
                kwargs
                """

                super(cls).__init_subclass__(**kwargs)

                if hasattr(cls, "register_section"):
                    setattr(cls, "register_section", None)

            new_cls = type(
                cls.__name__,
                (cls, RegistrableMixin),
                {
                    "register_section": register_section,
                    "__init_subclass__": init_subclass if not passes_on_children else lambda _: ...
                }
            )
            new_cls.__module__ = cls.__module__

            return new_cls

        return wrapper()

    return decorator


def clarify_register_sections(subclasses: dict[str, type]) -> dict[str, dict[str, type]]:
    """
    Makes a nested dictionary out of a flat subclasses dictionary.

    Parameters
    ----------
    subclasses : dict[str, type]
        Dictionary of subclasses of the form {'ClassName': <class 'ClassName'>}

    Returns
    -------
    dict[str, dict[str, type]]
        {'ClassName_register_section': {'ClassName': <class 'ClassName'>}}
    """
    if not subclasses:
        raise TypeError("Passed argument has no entries")

    clarified = defaultdict(dict, {"built_ins": {}})

    for k, v in subclasses.items():

        match getattr(v, "register_section", False):
            case None:
                continue

            case False:
                clarified["built_ins"][k] = v

            case _:
                clarified[v.register_section][k] = v

    return dict(clarified)


def create_subclasses_dict(cls: type, include_parent: bool = True) -> dict[str, type]:
    """
    Helper function to handle subclasses identification.
    Recursively identifies all descendants of the input class that have been directly or indirectly
    decorated with @register_as.

    Parameters
    ----------
    cls: type
        An uninitialized class to derive all the descendants from.
    include_parent: bool
        If True, the input class will be registered as well.

    Returns
    -------
    dict[str, type]
    """

    def validate_strictness(other_cls: type) -> bool:
        """
        Checks whether other_cls shall be included in cls subclasses.

        Parameters
        ----------
        other_cls: type

        Returns
        -------
        bool
        """
        match hasattr(cls, "register_section"), getattr(other_cls, "register_section", False) not in (None, False):
            case True, True:
                return True
            case False, _:
                return True
            case True, False:
                return False

    subclasses = {sub_cls.__name__: sub_cls for sub_cls in cls.__subclasses__() if validate_strictness(sub_cls)}
    another_subclasses = {cls.__name__: cls} if validate_strictness(cls) and include_parent else {}

    for subclass in subclasses.values():
        another_subclasses.update(create_subclasses_dict(subclass))

    return {**subclasses, **another_subclasses}


class RegistrableMixin:
    """
    Mixin used to simplify class registration with Register and @register_as() decorator.
    All classes influenced by @register_as() are inheriting from this mixin.

    register = Register(RegistrableMixin, include_parent=False) includes all decorated classes available in the
    namespace (locally written or imported).
    """
    register_section = None


class Register:
    """
    Utility class for managing object registration.

    Various types can be accessed through Register attributes,
    and the complete register can be retrieved using the register() property.
    """

    def __init__(self,
                 parent_cls: type = RegistrableMixin,
                 include_parent: bool = False,
                 package: Optional[str | ModuleType] = None):
        """
        Initialize the Register instance.

        Parameters
        ----------
        parent_cls : type
            The class type to be registered. Default: RegistrableMixin. But can be anything.
            E.g. nn.Module to register all subclasses of nn.Module that have register_section attribute assigned.
        include_parent: bool
            If True, the input class will be registered as well.
        package : str, optional
            The package to import submodules from, recursively.
        """
        if package is not None:
            self.import_submodules(package)

        self.other_cls = parent_cls
        self._flat_dict = create_subclasses_dict(parent_cls, include_parent)
        self._register = clarify_register_sections(self._flat_dict)
        self.package = package

        for register_section, v in self._register.items():
            setattr(self, register_section, v)

    def import_submodules(self, package: str | ModuleType):
        """
        Import all submodules of a package via walk_packages.

        Parameters
        ----------
        package: str | ModuleType
            Imported package (or it's name) to be processed.
        """
        # If we added new modules during the program is running
        importlib.invalidate_caches()

        if isinstance(package, str):
            package = importlib.import_module(package)

        for _, name, ispkg in pkgutil.walk_packages(package.__path__):

            full_name = package.__name__ + "." + name
            importlib.import_module(full_name)

            if ispkg:
                self.import_submodules(full_name)

    @property
    def register(self) -> dict[str, dict[str, type]]:
        """
        Get the complete register as a dictionary.

        Returns
        -------
        dict[str, dict[str, type]]
        """
        return self._register

    @multipledispatch.dispatch(type)
    def extend(self, obj: type):
        """
        Add an object to the register.

        Parameters
        ----------
        obj : type
            The object to be added to the register.
        """
        if not hasattr(obj, "register_section"):
            raise AttributeError((
                f'Passed {obj} does not have "register_section" attribute. You can provide it '
                "explicitly passing:\nregister_section: str, name: str, obj: type | Callable"
            ))
        self.extend(obj.register_section, obj.__name__, obj)

    @multipledispatch.dispatch(str, str, (type, Callable))
    def extend(self, register_section: str, name: str, obj: type | Callable):
        """
        Manually add an object to the register.

        Parameters
        ----------
        register_section : str
            An attribute of the register to hold this kind of object.
        name : str
            A name to use in config files.
        obj : type | Callable
            Uninitialized class or callable.
        """
        if getattr(self, register_section, None) is not None:
            assert isinstance(
                getattr(self, register_section), dict
            ), f"register_section must be a dict an is {getattr(self, register_section)}"
            self._register[register_section].update({name: obj})
            setattr(self, register_section, {**getattr(self, register_section), name: obj})
        else:
            self._register[register_section] = {name: obj}
            setattr(self, register_section, {name: obj})

    def update_register(self, other_cls: Optional[type] = None):
        """
        Update register with new classes that are currently absent in it.

        Parameters
        ----------
        other_cls: type
            The other class type to be registered.

        Returns
        -------
        None
        """
        if self.package is not None:
            self.import_submodules(self.package)

        all_classes = create_subclasses_dict(
            self.other_cls if other_cls is None else other_cls
        )

        new_classes_names = [
            name for name in all_classes.keys() if name not in self._flat_dict.keys()
        ]

        for name in new_classes_names:

            match all_classes.get(name):

                case None:
                    continue

                case cls if not hasattr(cls, "register_section"):
                    self.extend("built_ins", name, all_classes.get(name))

                case cls if cls.register_section is None:
                    continue

                case _:
                    self.extend(
                        all_classes.get(name).register_section, name, all_classes.get(name)
                    )
