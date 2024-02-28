import os
from typing import Tuple

import pytest
from yaml import Loader, load

TEST_ROOT_DIR = os.path.abspath("tests")


@pytest.fixture()
def config_paths() -> Tuple[str, str]:
    return (
        os.path.join(TEST_ROOT_DIR, "artifacts/config_for_tests.yaml"),
        os.path.join(TEST_ROOT_DIR, "artifacts/template_for_tests.yaml"),
    )


@pytest.fixture()
def config_dicts(config_paths) -> Tuple[dict, dict]:
    with open(config_paths[0], "r") as config, open(config_paths[1]) as template:
        return load(config, Loader), load(template, Loader)


@pytest.fixture()
def grid_paths(config_paths) -> Tuple[str, str, str]:
    return (
        os.path.join(TEST_ROOT_DIR, "artifacts/grid_for_tests.yaml"),
        config_paths[0],
        config_paths[1],
    )
