import os
import pytest
from yaml import Loader, load
from copy import deepcopy

from simple_copoco import (
    ConfigManager,
    DataClass,
    GridManager,
    ConfigUtilsMixin,
    MergableMixin
)


@pytest.fixture()
def example_of_configs() -> tuple[dict, dict]:
    config = {
        "key_1": 1, "key_2": 2, "key_3": 3, "key_4": {
            "key_5": 5, "key_6": {
                "key_7": 7, "key_8": 8
            }
        }
    }
    template = {
        "key_1": "template_value", "other_key_1": 1, "key_4": {
            "key_5": 10, "key_6": {
                "key_7": 14, "key_8": 8, 'key_9': 9
            }
        }
    }
    return config, template


class TestConfigManager:

    @staticmethod
    def test_yaml_input(config_paths):
        cfg_man = ConfigManager(*config_paths)
        assert isinstance(cfg_man.cfg, DataClass)

        assert cfg_man.cfg.jobs.build.docker.image == 'nvidia/cuda'
        assert cfg_man.cfg.jobs.build.docker.version == 'latest'

    @staticmethod
    def test_dict_input(config_dicts):
        cfg_man = ConfigManager(*config_dicts)
        assert isinstance(cfg_man.cfg, DataClass)

        assert cfg_man.cfg.jobs.build.docker.image == 'nvidia/cuda'
        assert cfg_man.cfg.jobs.build.docker.version == 'latest'

    @staticmethod
    def test_save_to_disk(tmp_path, config_paths):
        tmp = os.path.join(tmp_path, "test.yaml")
        cfg_man = ConfigManager(*config_paths)
        cfg_man.save_to_disk(tmp)
        with open(tmp, "r") as file:
            loaded = load(file, Loader)

        assert loaded == cfg_man.cfg_dict

    @staticmethod
    def test_construction(example_of_configs):
        cfg_man = ConfigManager(*example_of_configs)
        cfg = cfg_man.cfg
        assert cfg.key_1 == 1
        assert cfg.other_key_1 == 1
        assert cfg.key_4.key_5 == 5
        assert cfg.key_4.key_6.key_7 == 7
        assert cfg.key_4.key_6.key_9 == 9

    @staticmethod
    def test_recursion(example_of_configs):
        config, template = example_of_configs
        config["level_1"] = deepcopy(template)
        config["level_1"]["level_2"] = deepcopy(template)
        config["level_1"]["level_2"]["level_3"] = deepcopy(template)
        cfg_man = ConfigManager(config, template)
        cfg = cfg_man.cfg
        assert cfg.level_1.level_2.level_3.key_1 == "template_value"

    @staticmethod
    def test_invalid_types():
        with pytest.raises(TypeError):
            ConfigManager({}, 'a.yml')
            ConfigManager('a.yml', {})
            ConfigManager(1, 'b.yml')


class TestGridManager:

    @staticmethod
    def test_grid_len(grid_paths):
        grid_man = GridManager(*grid_paths)
        assert len(grid_man) == len([0 for _ in grid_man._generate_config_manager()])

    @staticmethod
    def test_grid_elem(grid_paths):
        grid_man = GridManager(*grid_paths)
        assert isinstance(grid_man.next(), ConfigManager)

    @staticmethod
    def test_invalid_types():
        with pytest.raises(TypeError):
            GridManager({}, 'a.yml')
            GridManager('a.yml', {})
            GridManager(1, 'b.yml')
            GridManager({}, {}, 1)


class TestGridConstruction(ConfigUtilsMixin):

    grid = {"a": {"b": {"c": [1, 2, 3]}, "b2": [4, 5, 6]}, "a2": [9, 8, 7]}
    grid_test = {"a": {"b": {"c": 1}, "b2": 4}, "a2": 9}
    grid_manager = GridManager(grid, {})

    def test_comparison_of_grids(self):
        grid_entry = self.grid_manager.next().cfg_dict
        assert grid_entry == self.grid_test

    @staticmethod
    def test_grid_construction(grid_paths):
        grid = GridManager(*grid_paths)
        for _ in range(len(grid)):
            cfg = grid.next().cfg

        # proper ordering of configs
        assert cfg.jobs.build.docker.image == 'hilthon'
        assert cfg.jobs.test.docker.image == 'hilthon'

        # proper merge with template
        assert cfg.jobs.build.on_finish.run == 'echo "this is the end"'


def test_mergable_mixin():
    class SomeKlass(MergableMixin):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            ...

        def _dataclass_from_nested_dict(self, data: dict, name: str, **kwargs):
            ...

    with pytest.raises(TypeError, match='must be a dataclass'):
        SomeKlass()
