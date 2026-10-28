import pytest
from era.psychometrics.rasch import probability_correct, fisher_information, eap_update


def test_probability_is_half_at_equal_ability_and_difficulty():
    assert probability_correct(0.5, 0.5) == pytest.approx(0.5)


def test_information_is_maximum_at_equal_ability_and_difficulty():
    assert fisher_information(0.0, 0.0) == pytest.approx(0.25)


def test_correct_response_increases_eap_mean():
    theta, sd = eap_update(0.0, 1.0, 0.0, True)
    assert theta > 0.0
    assert sd < 1.0


def test_incorrect_response_decreases_eap_mean():
    theta, sd = eap_update(0.0, 1.0, 0.0, False)
    assert theta < 0.0
    assert sd < 1.0
