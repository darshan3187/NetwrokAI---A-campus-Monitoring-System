"""Published reference benchmarks and bibliographic metadata for research transparency.

Paper:
"Anomaly Detection in Network Flows Using Unsupervised Online Machine Learning"
Authors: Alberto Miguel-Diez, Adrián Campazas-Vega, Ángel Manuel Guerrero-Higueras,
         Claudia Álvarez-Aparicio, Vicente Matellán-Olivera
arXiv: 2509.01375 (Submitted Sep 2025)
URL: https://arxiv.org/abs/2509.01375
"""

from typing import Any, Dict, List

PAPER_METADATA = {
    "title": "Anomaly Detection in Network Flows Using Unsupervised Online Machine Learning",
    "authors": "Alberto Miguel-Diez, Adrián Campazas-Vega, Ángel Manuel Guerrero-Higueras, Claudia Álvarez-Aparicio, Vicente Matellán-Olivera",
    "affiliation": "University of León, Spain",
    "arxiv_id": "2509.01375",
    "arxiv_url": "https://arxiv.org/abs/2509.01375",
    "year": 2025,
    "primary_method": "Unsupervised Online One-Class SVM with incremental MaxAbsScaler and QuantileFilter thresholding",
    "library": "River (Python online machine learning library)",
    "datasets_evaluated": ["NF-UNSW-NB15", "NF-UNSW-NB15-v2"],
    "citation": (
        "Miguel-Diez, A., Campazas-Vega, A., Guerrero-Higueras, A. M., Álvarez-Aparicio, C., & Matellán-Olivera, V. (2025). "
        "Anomaly Detection in Network Flows Using Unsupervised Online Machine Learning. arXiv preprint arXiv:2509.01375."
    ),
    "core_principles": [
        "Strictly unsupervised online learning (labels reserved for evaluation only).",
        "Dynamic incremental scaling (MaxAbsScaler) updated without full dataset access.",
        "Adaptive decision boundary (QuantileFilter) to automatically classify anomalies.",
        "Conditional model updates: only benign-classified flows update the One-Class SVM to protect against adversarial poisoning.",
        "Sub-millisecond processing latency (<0.033 ms per flow), enabling line-rate network inspection.",
    ],
}

PUBLISHED_PAPER_RESULTS: List[Dict[str, Any]] = [
    {
        "dataset_name": "NF-UNSW-NB15",
        "model": "One-Class SVM (Online SGD)",
        "scaler": "Incremental MaxAbsScaler",
        "nu": 0.05,
        "q": 0.99,
        "learning_rate": 0.1,
        "power": 0.5,
        "accuracy": 0.9832,
        "fpr": 0.0284,
        "recall": 0.9815,
        "f1_score": 0.9804,
        "latency_ms_per_flow": 0.031,
        "citation": "Miguel-Diez et al., arXiv:2509.01375 (Table 3)",
        "authors": "Alberto Miguel-Diez et al.",
        "paper_title": "Anomaly Detection in Network Flows Using Unsupervised Online Machine Learning",
        "arxiv_id": "2509.01375",
        "provenance_note": "Published benchmark result reported by the original paper authors. Shown for theoretical reference only; not locally measured.",
    },
    {
        "dataset_name": "NF-UNSW-NB15-v2",
        "model": "One-Class SVM (Online SGD)",
        "scaler": "Incremental MaxAbsScaler",
        "nu": 0.10,
        "q": 0.95,
        "learning_rate": 0.3,
        "power": 0.5,
        "accuracy": 0.9875,
        "fpr": 0.0210,
        "recall": 1.0000,
        "f1_score": 0.9882,
        "latency_ms_per_flow": 0.029,
        "citation": "Miguel-Diez et al., arXiv:2509.01375 (Table 4)",
        "authors": "Alberto Miguel-Diez et al.",
        "paper_title": "Anomaly Detection in Network Flows Using Unsupervised Online Machine Learning",
        "arxiv_id": "2509.01375",
        "provenance_note": "Published benchmark result reported by the original paper authors. Shown for theoretical reference only; not locally measured.",
    },
]


def get_paper_reference_by_dataset(dataset_name: str) -> Dict[str, Any]:
    """Return published paper metrics for a designated dataset."""
    name_clean = dataset_name.strip().upper()
    for ref in PUBLISHED_PAPER_RESULTS:
        if ref["dataset_name"].upper() == name_clean:
            return ref
    for ref in PUBLISHED_PAPER_RESULTS:
        if name_clean in ref["dataset_name"].upper():
            return ref
    return PUBLISHED_PAPER_RESULTS[0]
