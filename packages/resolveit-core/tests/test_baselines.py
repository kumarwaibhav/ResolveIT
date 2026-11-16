import numpy as np

from resolveit_core.bench.baselines import (
    TfidfLogistic,
    forced_single_label,
    metrics,
    naive_confidence,
    paired_bootstrap_accuracy,
    zero_shot_cached,
)


def test_baselines_and_missing_external_predictions() -> None:
    p = np.array([[0.9, 0.1], [0.6, 0.4]])
    y = np.array([0, 1], dtype=np.int64)
    assert forced_single_label(p).tolist() == [0, 0]
    assert naive_confidence(p).tolist() == [0, -1]
    assert metrics(naive_confidence(p), y).selective_error == 0
    assert zero_shot_cached(None, y, model_family="x", silver_annotator_family="x") == (None, True)


def test_tfidf_vocabulary_is_training_only_and_unicode_preserved() -> None:
    model = TfidfLogistic(2)
    model.fit(["vpn टूट गया", "vpn नहीं", "email broken", "email unavailable"],
              np.array([0, 0, 1, 1], dtype=np.int64), epochs=40)
    assert "टूट" in model.vocabulary
    assert model.predict(["vpn secret_test_word", "email"]).tolist() == [0, 1]
    assert "secret_test_word" not in model.vocabulary


def test_paired_bootstrap_identical_predictions_has_zero_difference() -> None:
    y = np.array([0, 1, 0, 1], dtype=np.int64)
    assert paired_bootstrap_accuracy(y, y, y, resamples=100) == (0, 0, 0)
