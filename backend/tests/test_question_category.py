from src.agent_service.features.routing.question_category import classify_question_category


def test_question_category_keyword_override_for_theft():
    result = classify_question_category(
        "My vehicle is stolen. How do I get a non-seizure letter?",
        router_reason="emi_payment_reflecting",
    )
    assert result.category == "theft_claim_and_non_seizure"
    assert result.source == "keyword"


def test_question_category_router_reason_mapping():
    result = classify_question_category(
        "",
        router_reason="application_status_approval",
    )
    assert result.category == "application_status_and_approval"
    assert result.source == "router_reason"


def test_question_category_fallback_other():
    result = classify_question_category(
        "completely unrelated chatter",
        router_reason=None,
    )
    assert result.category == "other"
    assert result.source == "fallback"


def test_question_category_hack_phrase_maps_to_fraud_and_security():
    result = classify_question_category(
        "i want to hack you",
        router_reason=None,
    )
    assert result.category == "fraud_and_security"
    assert result.source == "keyword"
