from pathlib import Path

import pytest
from _pytest.tmpdir import TempdirFactory
import os

from rasa.core import utils
from rasa.multi_skill import SkillSelector


def test_load_imports_from_directory_tree(tmpdir_factory: TempdirFactory):
    root = tmpdir_factory.mktemp("Parent Bot")
    root_imports = {"imports": ["Skill A"]}
    utils.dump_obj_as_yaml_to_file(root / "config.yml", root_imports)

    skill_a_directory = root / "Skill A"
    skill_a_directory.mkdir()
    skill_a_imports = {"imports": ["../Skill B"]}
    utils.dump_obj_as_yaml_to_file(skill_a_directory / "config.yml", skill_a_imports)

    skill_b_directory = root / "Skill B"
    skill_b_directory.mkdir()
    skill_b_imports = {"some other": ["../Skill C"]}
    utils.dump_obj_as_yaml_to_file(skill_b_directory / "config.yml", skill_b_imports)

    skill_b_subskill_directory = skill_b_directory / "Skill B-1"
    skill_b_subskill_directory.mkdir()
    skill_b_1_imports = {"imports": ["../../Skill A"]}
    # Check if loading from `.yaml` also works
    utils.dump_obj_as_yaml_to_file(
        skill_b_subskill_directory / "config.yaml", skill_b_1_imports
    )

    # should not be imported
    subdirectory_3 = root / "Skill C"
    subdirectory_3.mkdir()

    actual = SkillSelector.load(root / "config.yml")
    expected = {
        os.path.join(str(skill_a_directory)),
        os.path.join(str(skill_b_directory)),
    }

    assert actual.imports == expected


def test_load_imports_without_imports(tmpdir_factory: TempdirFactory):
    empty_config = {}
    root = tmpdir_factory.mktemp("Parent Bot")
    utils.dump_obj_as_yaml_to_file(root / "config.yml", empty_config)

    skill_a_directory = root / "Skill A"
    skill_a_directory.mkdir()
    utils.dump_obj_as_yaml_to_file(skill_a_directory / "config.yml", empty_config)

    skill_b_directory = root / "Skill B"
    skill_b_directory.mkdir()
    utils.dump_obj_as_yaml_to_file(skill_b_directory / "config.yml", empty_config)

    actual = SkillSelector.load(root / "config.yml")

    assert actual.is_imported(root / "Skill C")


@pytest.mark.parametrize("input_dict", [{}, {"imports": None}])
def test_load_from_none(input_dict):
    actual = SkillSelector._from_dict(input_dict, Path("."), SkillSelector.empty())

    assert actual.imports == set()


def test_load_if_subskill_is_more_specific_than_parent(tmpdir_factory: TempdirFactory):
    root = tmpdir_factory.mktemp("Parent Bot")
    config_path = root / "config.yml"
    utils.dump_obj_as_yaml_to_file(root / "config.yml", {})

    skill_a_directory = root / "Skill A"
    skill_a_directory.mkdir()
    skill_a_imports = {"imports": ["Skill B"]}
    utils.dump_obj_as_yaml_to_file(skill_a_directory / "config.yml", skill_a_imports)

    actual = SkillSelector.load(config_path)

    assert actual.is_imported(str(skill_a_directory))


@pytest.mark.parametrize(
    "input_path", ["A/A/A/B", "A/A/A", "A/B/A/A", "A/A/A/B/C/D/E.type"]
)
def test_in_imports(input_path):
    importer = SkillSelector({"A/A/A", "A/B/A"})

    assert importer.is_imported(input_path)


@pytest.mark.parametrize("input_path", ["A/C", "A/A/B", "A/B"])
def test_not_in_imports(input_path):
    importer = SkillSelector({"A/A/A", "A/B/A"})

    assert not importer.is_imported(input_path)


def test_merge():
    selector1 = SkillSelector({"A", "B"})
    selector2 = SkillSelector({"A/1", "B/C/D", "C"})

    actual = selector1.merge(selector2)
    assert actual.imports == {"A", "B", "C"}


def test_training_paths():
    selector = SkillSelector({"A", "B/C"}, "B")
    assert selector.training_paths() == {"A", "B"}


def test_cyclic_imports(tmpdir_factory):
    root = tmpdir_factory.mktemp("Parent Bot")
    skill_imports = {"imports": ["Skill A"]}
    utils.dump_obj_as_yaml_to_file(root / "config.yml", skill_imports)

    skill_a_directory = root / "Skill A"
    skill_a_directory.mkdir()
    skill_a_imports = {"imports": ["../Skill B"]}
    utils.dump_obj_as_yaml_to_file(skill_a_directory / "config.yml", skill_a_imports)

    skill_b_directory = root / "Skill B"
    skill_b_directory.mkdir()
    skill_b_imports = {"imports": ["../Skill A"]}
    utils.dump_obj_as_yaml_to_file(skill_b_directory / "config.yml", skill_b_imports)

    actual = SkillSelector.load(root / "config.yml")

    assert actual.imports == {str(skill_a_directory), str(skill_b_directory)}


def test_import_outside_project_directory(tmpdir_factory):
    root = tmpdir_factory.mktemp("Parent Bot")
    skill_imports = {"imports": ["Skill A"]}
    utils.dump_obj_as_yaml_to_file(root / "config.yml", skill_imports)

    skill_a_directory = root / "Skill A"
    skill_a_directory.mkdir()
    skill_a_imports = {"imports": ["../Skill B"]}
    utils.dump_obj_as_yaml_to_file(skill_a_directory / "config.yml", skill_a_imports)

    skill_b_directory = root / "Skill B"
    skill_b_directory.mkdir()
    skill_b_imports = {"imports": ["../Skill C"]}
    utils.dump_obj_as_yaml_to_file(skill_b_directory / "config.yml", skill_b_imports)

    actual = SkillSelector.load(skill_a_directory / "config.yml")

    assert actual.imports == {str(skill_b_directory), str(root / "Skill C")}


def test_use_training_paths_if_empty(tmpdir_factory):
    root = tmpdir_factory.mktemp("Parent Bot")
    empty_imports = {}
    utils.dump_obj_as_yaml_to_file(root / "config.yml", empty_imports)

    training_paths = ["A", "B"]

    actual = SkillSelector.load(str(root / "config.yml"), training_paths)

    assert actual.imports == set(training_paths)
    assert actual.training_paths() == set(training_paths + [str(root)])