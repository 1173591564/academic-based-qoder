"""
Tests for _extract_paper_metrics — paper-reported metric extraction precision.

Tests cover:
- Colon/equals format (accuracy: 85.2)
- Sentence format (achieves accuracy of 92.3%)
- Markdown table rows (| accuracy | 88.5% |)
- Multiple values (takes best)
- Normalization (percentage → ratio)
- New metrics (EM, AUC, precision, recall)
- Non-results sections are ignored
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scholar.commands.execution_ops import _extract_paper_metrics


def approx(val, expected, tol=1e-6):
    """Float comparison with tolerance."""
    return abs(val - expected) < tol


class TestSimpleColonFormat:
    """Basic metric: value extraction."""

    def test_accuracy_colon(self):
        data = {"sections": [{"heading": "Results", "content": "accuracy: 85.2"}]}
        result = _extract_paper_metrics(data)
        acc = next(m for m in result if m["name"] == "accuracy")
        assert approx(acc["value"], 0.852)
        assert acc["type"] == "higher_better"

    def test_accuracy_equals(self):
        data = {"sections": [{"heading": "Results", "content": "accuracy = 87.3"}]}
        result = _extract_paper_metrics(data)
        acc = next(m for m in result if m["name"] == "accuracy")
        assert approx(acc["value"], 0.873)

    def test_loss_colon(self):
        data = {"sections": [{"heading": "Experiments", "content": "loss: 0.34"}]}
        result = _extract_paper_metrics(data)
        loss = next(m for m in result if m["name"] == "loss")
        assert loss["value"] == 0.34
        assert loss["type"] == "lower_better"

    def test_percentage_sign(self):
        data = {"sections": [{"heading": "Results", "content": "accuracy: 92.5%"}]}
        result = _extract_paper_metrics(data)
        acc = next(m for m in result if m["name"] == "accuracy")
        assert approx(acc["value"], 0.925)


class TestSentenceFormat:
    """achieves/reaches/obtains sentence patterns."""

    def test_achieves_accuracy(self):
        data = {"sections": [{"heading": "Results", "content": "Our model achieves accuracy of 92.3% on the test set."}]}
        result = _extract_paper_metrics(data)
        acc = next(m for m in result if m["name"] == "accuracy")
        assert approx(acc["value"], 0.923)

    def test_reaches_f1(self):
        data = {"sections": [{"heading": "Evaluation", "content": "The system reaches F1 of 0.87."}]}
        result = _extract_paper_metrics(data)
        f1 = next(m for m in result if m["name"] == "f1_score")
        assert approx(f1["value"], 0.87)

    def test_bleu_achieves(self):
        data = {"sections": [{"heading": "Results", "content": "Our approach achieves BLEU of 34.5."}]}
        result = _extract_paper_metrics(data)
        bleu = next(m for m in result if m["name"] == "bleu")
        assert approx(bleu["value"], 0.345)


class TestMarkdownTable:
    """Markdown table row extraction."""

    def test_simple_table(self):
        content = "| accuracy | 88.5% |\n| F1 | 0.82 |"
        data = {"sections": [{"heading": "Results", "content": content}]}
        result = _extract_paper_metrics(data)
        names = {m["name"] for m in result}
        assert "accuracy" in names
        acc = next(m for m in result if m["name"] == "accuracy")
        assert approx(acc["value"], 0.885)

    def test_table_with_multiple_metrics(self):
        content = "| accuracy | 90.2 |\n| F1 | 88.1 |\n| loss | 0.15 |"
        data = {"sections": [{"heading": "Experiments", "content": content}]}
        result = _extract_paper_metrics(data)
        names = {m["name"] for m in result}
        assert "accuracy" in names
        assert "f1_score" in names
        assert "loss" in names

    def test_table_takes_priority_over_prose(self):
        """Table extraction runs first; prose should not duplicate."""
        content = "| accuracy | 88.0% |\naccuracy: 92.3"
        data = {"sections": [{"heading": "Results", "content": content}]}
        result = _extract_paper_metrics(data)
        acc_metrics = [m for m in result if m["name"] == "accuracy"]
        assert len(acc_metrics) == 1  # No duplicate
        assert approx(acc_metrics[0]["value"], 0.88)  # Table value


class TestMultipleValues:
    """When multiple values found, takes best."""

    def test_higher_better_takes_max(self):
        """accuracy: 85.2 and accuracy: 87.3 → 0.873"""
        data = {"sections": [{"heading": "Results", "content": "accuracy: 85.2\naccuracy: 87.3"}]}
        result = _extract_paper_metrics(data)
        acc = next(m for m in result if m["name"] == "accuracy")
        assert approx(acc["value"], 0.873)

    def test_lower_better_takes_min(self):
        """loss: 2.3 and loss: 1.8 → 1.8"""
        data = {"sections": [{"heading": "Results", "content": "loss: 2.3\nloss: 1.8"}]}
        result = _extract_paper_metrics(data)
        loss = next(m for m in result if m["name"] == "loss")
        assert loss["value"] == 1.8


class TestNormalization:
    """Percentage values > 1 are normalized to ratio."""

    def test_accuracy_normalized(self):
        data = {"sections": [{"heading": "Results", "content": "accuracy: 85.2"}]}
        result = _extract_paper_metrics(data)
        acc = next(m for m in result if m["name"] == "accuracy")
        assert approx(acc["value"], 0.852)

    def test_bleu_normalized(self):
        data = {"sections": [{"heading": "Results", "content": "bleu: 34.5"}]}
        result = _extract_paper_metrics(data)
        bleu = next(m for m in result if m["name"] == "bleu")
        assert approx(bleu["value"], 0.345)

    def test_auc_not_normalized_when_below_1(self):
        data = {"sections": [{"heading": "Results", "content": "auc: 0.91"}]}
        result = _extract_paper_metrics(data)
        auc = next(m for m in result if m["name"] == "auc")
        assert approx(auc["value"], 0.91)

    def test_loss_not_normalized(self):
        """Loss values are never normalized."""
        data = {"sections": [{"heading": "Results", "content": "loss: 2.34"}]}
        result = _extract_paper_metrics(data)
        loss = next(m for m in result if m["name"] == "loss")
        assert approx(loss["value"], 2.34)


class TestNewMetrics:
    """EM, AUC, precision, recall."""

    def test_exact_match(self):
        data = {"sections": [{"heading": "Results", "content": "EM: 75.0%"}]}
        result = _extract_paper_metrics(data)
        em = next(m for m in result if m["name"] == "exact_match")
        assert approx(em["value"], 0.75)

    def test_auc(self):
        data = {"sections": [{"heading": "Evaluation", "content": "AUC: 0.93"}]}
        result = _extract_paper_metrics(data)
        auc = next(m for m in result if m["name"] == "auc")
        assert auc["value"] == 0.93

    def test_precision(self):
        data = {"sections": [{"heading": "Results", "content": "precision: 88.5%"}]}
        result = _extract_paper_metrics(data)
        prec = next(m for m in result if m["name"] == "precision")
        assert approx(prec["value"], 0.885)

    def test_recall(self):
        data = {"sections": [{"heading": "Results", "content": "recall = 0.82"}]}
        result = _extract_paper_metrics(data)
        recall = next(m for m in result if m["name"] == "recall")
        assert approx(recall["value"], 0.82)


class TestSectionFiltering:
    """Metrics in non-results sections should not be extracted."""

    def test_no_metrics_in_introduction(self):
        data = {"sections": [{"heading": "Introduction", "content": "accuracy: 99.9"}]}
        result = _extract_paper_metrics(data)
        assert len(result) == 0

    def test_no_metrics_in_related_work(self):
        data = {"sections": [{"heading": "Related Work", "content": "loss: 0.01"}]}
        result = _extract_paper_metrics(data)
        assert len(result) == 0

    def test_metrics_in_main_results(self):
        """'Main Results' heading should match."""
        data = {"sections": [{"heading": "Main Results", "content": "accuracy: 90.0"}]}
        result = _extract_paper_metrics(data)
        assert len(result) > 0

    def test_abstract_metrics_extracted(self):
        """Abstract is always checked."""
        data = {"abstract": "We achieve accuracy of 95.2%.", "sections": []}
        result = _extract_paper_metrics(data)
        acc = next(m for m in result if m["name"] == "accuracy")
        assert approx(acc["value"], 0.952)


class TestEdgeCases:
    """Edge cases and robustness."""

    def test_empty_paper_data(self):
        assert _extract_paper_metrics({}) == []

    def test_no_sections(self):
        data = {"abstract": "Some text without metrics."}
        result = _extract_paper_metrics(data)
        assert len(result) == 0

    def test_section_with_empty_content(self):
        data = {"sections": [{"heading": "Results", "content": ""}]}
        assert _extract_paper_metrics(data) == []

    def test_perplexity_lower_better(self):
        data = {"sections": [{"heading": "Results", "content": "perplexity: 15.3"}]}
        result = _extract_paper_metrics(data)
        ppl = next(m for m in result if m["name"] == "perplexity")
        assert ppl["type"] == "lower_better"
        # Perplexity is not normalized
        assert ppl["value"] == 15.3
