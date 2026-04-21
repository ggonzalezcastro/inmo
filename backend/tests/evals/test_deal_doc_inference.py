"""
Eval: document slot inference accuracy (keyword heuristic — no LLM key needed).
Run with: pytest tests/evals/test_deal_doc_inference.py -v --noconftest
"""
import json
from pathlib import Path
from app.services.deals.intake import _infer_slot_from_filename


def test_keyword_heuristic_accuracy():
    dataset_path = Path(__file__).parent / "deal_doc_inference.json"
    dataset = json.loads(dataset_path.read_text())

    correct = 0
    for item in dataset:
        result = _infer_slot_from_filename(item["filename"], item["mime_type"])
        if result == item["expected_slot"]:
            correct += 1
        else:
            print(f"MISS: {item['filename']} → got '{result}', expected '{item['expected_slot']}'")

    accuracy = correct / len(dataset)
    print(f"\nAccuracy: {correct}/{len(dataset)} = {accuracy:.0%}")
    assert accuracy >= 0.8, f"Keyword heuristic accuracy too low: {accuracy:.0%}"
