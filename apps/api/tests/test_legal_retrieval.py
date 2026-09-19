import tempfile

from app.services.legal_retrieval import LegalRetrievalService


def test_qenlo_retrieval_persists_and_returns_matching_chunk():
    corpus = [
        {"label": "OKF Rule", "title": "Liability", "text": "Liability is capped at fees paid."},
        {"label": "OKF Rule", "title": "Payment", "text": "Invoices are due net thirty days."},
    ]
    with tempfile.TemporaryDirectory() as directory:
        service = LegalRetrievalService(directory, dimension=64)
        hits = service.search(corpus, "What is the liability cap?", k=1)
        assert hits[0]["title"] == "Liability"
        assert service.status()["ready"] is True
