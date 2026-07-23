from evals.metrics import citation_accuracy, factual_precision


def test_citation_accuracy_all_valid():
    report = "The market grew significantly [1]. Adoption rose too [2]."
    assert citation_accuracy(report, n_sources=2) == 1.0


def test_citation_accuracy_catches_out_of_range():
    report = "The market grew [1]. It also did something odd [5]."
    assert citation_accuracy(report, n_sources=2) == 0.5


def test_citation_accuracy_no_citations():
    assert citation_accuracy("No citations here.", n_sources=3) == 0.0


def test_factual_precision_full_match():
    report = "UPI processed 117 billion transactions in 2023."
    assert factual_precision(report, ["117", "2023"]) == 1.0


def test_factual_precision_partial_match():
    report = "UPI processed a lot of transactions."
    assert factual_precision(report, ["117", "2023"]) == 0.0
