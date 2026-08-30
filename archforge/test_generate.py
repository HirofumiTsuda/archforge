from archforge.generate import get_domain_system_prompt, get_reviewer_system_prompt


def test_get_domain_system_prompt() -> None:
    res = get_domain_system_prompt(exam_name="test_exam", domain="test_domain")
    assert res is not None


def test_get_reviewer_system_prompt() -> None:
    res = get_reviewer_system_prompt(exam_name="test_exam")
    assert res is not None
