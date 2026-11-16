import pytest

from resolveit_core.calibrate.agreement import cohens_kappa, krippendorff_alpha


def test_perfect_and_chance_agreement() -> None:
    assert cohens_kappa(["a", "b"], ["a", "b"]) == 1
    assert cohens_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"]) == 0
    assert krippendorff_alpha([["a", "a"], ["b", "b"], [None]]) == 1


def test_missing_and_undefined_agreement_stays_missing() -> None:
    assert cohens_kappa([], []) is None
    assert cohens_kappa(["a"], ["a"]) is None
    assert krippendorff_alpha([[None, "a"], ["a", "a"]]) is None
    assert krippendorff_alpha([["a", "b"], ["a", "b"]]) == pytest.approx(-0.5)
    with pytest.raises(ValueError):
        cohens_kappa(["a"], [])
