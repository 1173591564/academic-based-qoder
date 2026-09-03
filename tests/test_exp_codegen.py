"""
Test exp_codegen.py — experiment code template generator.
Uses tmp_path fixtures, no dependency on real paper data.
"""
import json
import pytest
from pathlib import Path

from scholar.exp_codegen import (
    title_to_module_name,
    extract_hyperparameters,
    generate_model_py,
    generate_train_py,
    generate_config_yaml,
    generate_requirements_txt,
    generate_readme_md,
    generate_experiment_template,
)


class TestTitleToModuleName:
    def test_basic(self):
        assert title_to_module_name("Attention Is All You Need") == "attention_is_all_you_need"

    def test_with_punctuation(self):
        result = title_to_module_name("BERT: Pre-training of Deep Transformers")
        assert ":" not in result
        assert "bert" in result

    def test_empty(self):
        assert title_to_module_name("") == "untitled_model"

    def test_long_title_truncated(self):
        long_title = "A Very Long Title That Should Be Truncated To Six Words Max"
        result = title_to_module_name(long_title)
        assert len(result.split("_")) <= 6


class TestExtractHyperparameters:
    def test_learning_rate(self):
        sections = [{"content": "We use a learning rate of 0.001 with Adam optimizer.", "heading": ""}]
        params = extract_hyperparameters(sections)
        assert params.get("learning_rate") == 0.001

    def test_batch_size(self):
        sections = [{"content": "batch size of 256 was used", "heading": ""}]
        params = extract_hyperparameters(sections)
        assert params.get("batch_size") == 256

    def test_epochs(self):
        sections = [{"content": "We train for 100 epochs", "heading": ""}]
        params = extract_hyperparameters(sections)
        assert params.get("epochs") == 100

    def test_optimizer(self):
        sections = [{"content": "using AdamW optimizer", "heading": ""}]
        params = extract_hyperparameters(sections)
        assert params.get("optimizer", "").lower() == "adamw"

    def test_no_params(self):
        sections = [{"content": "This paper has no hyperparameters mentioned.", "heading": ""}]
        params = extract_hyperparameters(sections)
        assert params == {}

    def test_multiple_params(self):
        sections = [{"content": "learning rate = 1e-4, batch size = 32, train for 50 epochs", "heading": ""}]
        params = extract_hyperparameters(sections)
        assert params.get("learning_rate") == 1e-4
        assert params.get("batch_size") == 32
        assert params.get("epochs") == 50


class TestGenerateModelPy:
    def test_basic_generation(self):
        formulas = [{"latex": "y = Wx + b", "label": "eq:linear"}]
        code = generate_model_py(formulas, "Test Paper")
        assert "class Testpaper(nn.Module)" in code or "class " in code
        assert "def forward(self, x)" in code
        assert "def create_model" in code
        assert "y = Wx + b" in code

    def test_empty_formulas(self):
        code = generate_model_py([], "Empty Paper")
        assert "class " in code
        assert "No formulas" in code

    def test_none_latex(self):
        formulas = [{"latex": None, "label": None}]
        code = generate_model_py(formulas, "Test")
        assert "class " in code


class TestGenerateConfigYaml:
    def test_defaults(self):
        yaml = generate_config_yaml({}, "Test Paper")
        assert "learning_rate" in yaml
        assert "batch_size" in yaml
        assert "epochs" in yaml

    def test_custom_params(self):
        yaml = generate_config_yaml({"learning_rate": 0.01, "batch_size": 64}, "Test")
        assert "0.01" in yaml
        assert "64" in yaml


class TestGenerateExperimentTemplate:
    def test_full_generation(self, tmp_path):
        """Test complete template generation with mock paper JSON."""
        # Create mock parsed JSON
        parsed_dir = tmp_path / "parsed"
        parsed_dir.mkdir()
        ulid = "TESTULID001"
        (parsed_dir / f"{ulid}.json").write_text(json.dumps({
            "paper_id": ulid,
            "title": "Test Paper for Code Generation",
            "authors": ["Author A", "Author B"],
            "year": 2024,
            "formulas": [
                {"latex": "L = -\\sum y \\log p", "label": "eq:loss"},
                {"latex": "p = \\text{softmax}(Wx)", "label": "eq:softmax"},
            ],
            "sections": [
                {"heading": "Method", "content": "We use learning rate of 0.001 with batch size of 64."},
                {"heading": "Experiments", "content": "We train for 50 epochs using Adam optimizer."},
            ],
        }), encoding="utf-8")

        # Create experiments directory
        exp_dir = tmp_path / "experiments"

        # Patch config
        from scholar import config as scholar_config
        old_parsed = scholar_config.PARSED_DIR
        old_exp = scholar_config.EXPERIMENTS_DIR
        scholar_config.PARSED_DIR = parsed_dir
        scholar_config.EXPERIMENTS_DIR = exp_dir

        try:
            result = generate_experiment_template(ulid)
        finally:
            scholar_config.PARSED_DIR = old_parsed
            scholar_config.EXPERIMENTS_DIR = old_exp

        assert "error" not in result
        assert result["ulid"] == ulid
        assert result["title"] == "Test Paper for Code Generation"
        assert len(result["files_created"]) == 7
        assert "model.py" in result["files_created"]
        assert "train.py" in result["files_created"]
        assert "config.yaml" in result["files_created"]
        assert result["formulas_count"] == 2
        assert result["hyperparams"].get("learning_rate") == 0.001
        assert result["hyperparams"].get("batch_size") == 64

        # Verify files exist
        out_dir = exp_dir / ulid
        for fname in result["files_created"]:
            assert (out_dir / fname).exists(), f"{fname} not created"

    def test_paper_not_found(self, tmp_path):
        parsed_dir = tmp_path / "parsed"
        parsed_dir.mkdir()
        exp_dir = tmp_path / "experiments"

        from scholar import config as scholar_config
        old_parsed = scholar_config.PARSED_DIR
        old_exp = scholar_config.EXPERIMENTS_DIR
        scholar_config.PARSED_DIR = parsed_dir
        scholar_config.EXPERIMENTS_DIR = exp_dir

        try:
            result = generate_experiment_template("NONEXISTENT")
        finally:
            scholar_config.PARSED_DIR = old_parsed
            scholar_config.EXPERIMENTS_DIR = old_exp

        assert "error" in result
