import pytest
from nubetalo.theme import eta_text


@pytest.mark.parametrize('seconds,expected', [
    (0, '—'), (float('inf'), '—'), (1, '0:01'), (59, '0:59'),
    (60, '1:00'), (3599, '59:59'), (3600, '1 hora'),
    (7200, '2 horas'), (86400, '1 día'), (604800, '1 semana'),
    (30 * 86400, '1 mes'), (365 * 86400, '1 año'),
    (2 * 365 * 86400, '2 años'),
])
def test_eta_uses_only_largest_unit(seconds, expected):
    assert eta_text(seconds, 'es') == expected


def test_eta_english():
    assert eta_text(3600, 'en') == '1 hour'
    assert eta_text(60 * 86400, 'en') == '2 months'
