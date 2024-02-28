import builtins
import os
import types
import warnings
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import asdict, make_dataclass, is_dataclass
from itertools import product
from os import PathLike
from pathlib import PurePath
from typing import Any, Optional, Protocol, runtime_checkable

from yaml import Dumper, Loader, dump, load

CONFIG_EXTENSIONS = (".yml", ".yaml")


def merge_dicts(*args: dict) -> dict:
    """
    Merge passed dicts, recursively.
    Fist dictionary will be used as a base (template) for merging.
    Every other passed will overwrite the result of merging previous.

    Parameters
    ----------
    args: dict

    Returns
    -------
    dict
    """
    dicts = [deepcopy(elem) for elem in args]

    if dicts[0] is None:
        raise TypeError("None type can't be used as a base for merging!")

    if any([elem is None for elem in dicts]):
        warnings.warn("None type detected in passed sequence of dicts! All None types will be skipped from "
                      "merging.", RuntimeWarning)

    merged = dicts[0]
    for i in range(1, len(dicts)):

        if dicts[i] is None:
            continue

        for k, v in dicts[i].items():

            if isinstance(v, dict) and isinstance(merged.get(k), dict):
                merged[k] = merge_dicts(merged.get(k), v)
            else:
                merged[k] = v

    return merged


@runtime_checkable
class DataClass(Protocol):
    """
    typing.Protocol for dataclass type hint.
    """

    __dataclass_fields__: dict


class MergableMixin(ABC):
    """
    A mixin foran extended dataclass that enables merging with 'or' (== |) with other dataclass.
    """

    def __new__(cls, *args, **kwargs):
        new_class = super().__new__(cls)

        if not is_dataclass(new_class):
            raise TypeError(f"{new_class.__class__.__name__} must be a dataclass.")

        return new_class

    def __init__(self, *args, **kwargs):
        super().__init__()

    @abstractmethod
    def _dataclass_from_nested_dict(self, data: dict, name: str, **kwargs):
        """
        An extended dataclass shall have this implemented, e.g. through inheritance from ConfigUtilsMixin.
        """
        ...

    def __or__(self, *other: DataClass) -> DataClass:
        if not all([is_dataclass(elem) for elem in other]):
            raise TypeError("Only dataclasses can be merged!")

        new_name = self.__class__.__name__ + '_merged_' + '_'.join([elem.__class__.__name__ for elem in other])
        new_dict = merge_dicts(asdict(self), *[asdict(elem) for elem in other])
        merged_class = self._dataclass_from_nested_dict(new_dict, new_name, bases=(ConfigUtilsMixin, MergableMixin))

        return merged_class


class ConfigUtilsMixin:
    """
    Provides some utilities for configs.
    """

    @staticmethod
    def _check_if_yaml_suffix(*paths: str | PathLike | None):
        """
        Checks if every passed argument leads to a file with extension as in CONFIG_EXTENSIONS.

        Parameters
        ----------
        paths: str | PathLike
            path-like strings.

        Raises
        ------
        TypeError
        """
        if not all([PurePath(pth).suffix in CONFIG_EXTENSIONS for pth in paths if pth is not None]):
            raise TypeError(f"Only {CONFIG_EXTENSIONS} files are supported")

    def _dataclass_from_nested_dict(self, data: dict, name: str, **kwargs) -> DataClass:
        """
        Parses nested dictionary into a nested dataclass.

        Parameters
        ----------
        data: dict
            A nested dictionary.
        name: str
            A name for returned dataclass.
        kwargs: Any
            kwargs for make_dataclass()
        Returns
        -------
        DataClass
        """
        temp_dict = {}
        for k, v in data.items():
            if isinstance(v, dict):
                temp_dict[k] = self._dataclass_from_nested_dict(v, f"{name}_{k}", **kwargs)
            else:
                temp_dict[k] = v

        return make_dataclass(name, self._prepare_dict_for_dataclass(temp_dict), **kwargs)(**temp_dict)

    def _flat_tuples_from_nested_dict(self, nested: dict, key: Optional[str] = None) -> list[tuple]:
        """
        Creates a flat list of tuples from nested dictionary.

        Parameters
        ----------
        nested: dict
        key: str
            A name of key for new key prefix creation, e.g.: "key.old_key"

        Returns
        -------
        list[tuple]
        """

        def extend_key(k: str) -> str:
            return k if key is None else f"{key}.{k}"

        flat = []
        for k, v in nested.items():

            match v:
                case dict():
                    elem = self._flat_tuples_from_nested_dict(v, extend_key(k))
                case list():
                    elem = [(extend_key(k), v)]
                case int() | float() | bool() | str():
                    elem = [(extend_key(k), [v])]
                case _:
                    raise TypeError(
                        f"Unsupported nested value type {type(v)}! Allowed are: dict, list, int, float, bool, str.")
            flat.extend(elem)

        return flat

    @staticmethod
    def _prepare_dict_for_dataclass(items: dict[str, Any]) -> list[tuple[str, type]]:
        """
        Parses dictionary items into make_dataclass compatible tuples.

        Parameters
        ----------
        items: dict[str, Any]

        Returns
        -------
        list[tuple[str, type]]
        """
        return [(name, type(value)) for name, value in items.items()]

    def _make_nested_dict(self, keys: str, val: Any) -> dict[str, Any]:
        """
        From keys aggregated by dot notation, e.g. "a.b.c.d", creates a nested dictionary.

        Parameters
        ----------
        keys: str
        val: Any

        Returns
        -------
        dict[str, Any]
        """
        if "." not in keys:
            return {keys: val}

        split_k = keys.split(".")
        return {split_k[0]: self._make_nested_dict(".".join(split_k[1:]), val)}


class ConfigManager(ConfigUtilsMixin):
    """
    Class for loading, accessing, changing an dumping YAML config.
    """

    def __init__(self,
                 config: str | os.PathLike | dict,
                 template: Optional[str | os.PathLike | dict] = None):
        """
        Parameters
        ----------
        config: str | os.PathLike | dict
        template: Optional[str | os.PathLike | dict]
        """
        match [type(config), type(template)]:

            case [builtins.dict, (builtins.dict | types.NoneType)]:
                self._config_dict = config
                self._template_dict = template if template is not None else {}

                self._config_path = None
                self._template_path = None

            case [(builtins.str | os.PathLike), (builtins.str | os.PathLike | types.NoneType)]:
                self._check_if_yaml_suffix(config, template)

                with open(config, "r") as cfg:
                    self._config_dict = load(cfg, Loader)

                if template is not None:
                    with open(template, "r") as cfg_default:
                        self._template_dict = load(cfg_default, Loader)
                        self._template_path = template

                else:
                    self._template_dict = {}
                    self._template_path = None

            case [builtins.dict, (builtins.str | os.PathLike)] | [(builtins.str | os.PathLike), builtins.dict]:
                raise TypeError(
                    f"config must be the same type as template (if the latter is not None). "
                    f"Received {type(config)} and {type(template)}")

            case _:
                raise TypeError(f"Unsupported type: {type(config)}. Allowed are: dict, str, os.PathLike.")

        # typehint DataClass is a protocol, not a class
        self._config: DataClass = self._dataclass_from_nested_dict(
            self._config_dict, "Config", bases=(ConfigUtilsMixin, MergableMixin)
        )
        self._template: DataClass = self._dataclass_from_nested_dict(
            self._template_dict, "Template", bases=(ConfigUtilsMixin, MergableMixin)
        ) if self._template_dict is not None else None

        self.cfg = self._template | self._config
        self._merged_config_dict = asdict(self.cfg)

    @property
    def cfg_specific(self) -> DataClass:
        return self._config

    @property
    def cfg_specific_dict(self) -> dict:
        return self._config_dict

    @property
    def template(self) -> DataClass:
        return self._template

    @property
    def template_dict(self) -> dict:
        return self._template_dict

    @property
    def cfg_dict(self) -> dict:
        return self._merged_config_dict

    def change_config(self, config: str | os.PathLike | dict):
        """
        Changes current config, leaving the loaded template unchanged.

        Parameters
        ----------
        config: str | os.PathLike | dict
            New config.

        Returns
        -------
        None
        """
        if isinstance(config, (str, os.PathLike)):
            with open(config, "r") as cfg:
                self.__init__(load(cfg, Loader), self.template_dict)
        elif isinstance(config, dict):
            self.__init__(config, self.template_dict)
        else:
            self.__init__(config, config)  # raises a TypeError

    def change_template(self, template: str | os.PathLike | dict):
        """
        Changes loaded template, leaving the current config unchanged.

        Parameters
        ----------
        template: str | os.PathLike | dict
            New template.

        Returns
        -------
        None
        """
        if isinstance(template, (str, os.PathLike)):
            with open(template, "r") as templ:
                self.__init__(self.cfg_specific_dict, load(templ, Loader))
        elif isinstance(template, dict):
            self.__init__(self.cfg_specific_dict, template)
        else:
            self.__init__(template, template)  # raises a TypeError

    def save_to_disk(self, path: str | os.PathLike):
        """
        Saves current state of self.cfg into given path.
        :param path: destination to save the file into.
        """
        with open(path, "w") as file:
            dump(self.cfg_dict, file, Dumper)

    def recreate_config(self):
        """
        Recreates original config.
        """
        self.cfg = self._config | self._template


class GridManager(ConfigUtilsMixin):
    """
    Provides generator of ConfigManager objects, based of provided grids of configuration.
    **Simplified, dictionary based example** of what config generation from grid is:

    # defined grid
    grid_dict = {"key1": ["value1", "value2"], "key2": ["value3", "value4"]}

    # generated configs
    config_dict1 = {"key1": "value1", "key2": "value3"}
    config_dict2 = {"key1": "value2", "key2": "value4"}
    config_dict3 = {"key1": "value1", "key2": "value4"}
    config_dict4 = {"key1": "value2", "key2": "value3"}
    """

    def __init__(self,
                 grid: str | os.PathLike | dict,
                 config: str | os.PathLike | dict,
                 template: Optional[str | os.PathLike | dict] = None):
        """
        Parameters
        ----------
        grid: str | os.PathLike | dict
        config: str | os.PathLike | dict
        template: str | os.PathLike | dict
        """
        match [type(grid), type(config), type(template)]:

            case [builtins.dict, builtins.dict, (builtins.dict | types.NoneType)]:
                self._grid_dict = grid
                self._config_dict = config
                self._template_dict = template if template is not None else {}

                self._grid_path = None
                self._config_path = None
                self._template_path = None

            case [(builtins.str | os.PathLike), (builtins.str | os.PathLike),
                  (builtins.str | types.NoneType | os.PathLike)]:
                self._check_if_yaml_suffix(grid, config, template)

                with open(grid, "r") as grid, open(config, "r") as cfg:
                    self._grid_dict = load(grid, Loader)
                    self._config_dict = load(cfg, Loader)

                if template is not None:
                    with open(template, "r") as cfg_template:
                        self._template_dict = load(cfg_template, Loader)
                else:
                    self._template_dict = {}

                self._grid_path = grid
                self._config_path = config
                self._template_path = template

            case [(builtins.str | os.PathLike), builtins.dict, _] | [builtins.dict, (builtins.str | os.PathLike), _]:
                raise TypeError(f"grid must be the same type as config. Received {type(grid)} and {type(config)}")

            case _:
                raise TypeError(f"Unsupported type: {type(config)}. Allowed are: dict, str, os.PathLike.")

        self._settings_list = self._flat_tuples_from_nested_dict(self._grid_dict)
        self._settings_grid = product(*[elem[1] for elem in self._settings_list])

    def __len__(self):
        total_configs = 1
        for elem in self._settings_list:
            total_configs *= len(elem[1])
        return total_configs

    def __next__(self):
        return next(self._generate_config_manager())

    def _generate_config_manager(self):
        for entry in self._generate_grid_entry():

            yield ConfigManager(
                merge_dicts(self._config_dict, entry),
                self._template_dict
            )

    def _generate_grid_entry(self):
        for setting in self._settings_grid:
            grid_entries: list[dict] = []

            for i in range(len(setting)):
                grid_entries.append(self._make_nested_dict(self._settings_list[i][0], setting[i]))

            yield merge_dicts(*grid_entries)

    def next(self):
        return self.__next__()
