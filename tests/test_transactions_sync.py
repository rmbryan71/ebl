from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def load_transactions_sync_module():
    module_path = Path(__file__).resolve().parents[1] / "transactions-sync.py"
    spec = spec_from_file_location("transactions_sync", module_path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_transaction_matches():
    transactions_sync = load_transactions_sync_module()
    patterns = ("added to 40-man roster", "selected from")
    assert transactions_sync.transaction_matches(patterns, "Added to 40-man roster")
    assert transactions_sync.transaction_matches(patterns, "Selected from AAA")
    assert not transactions_sync.transaction_matches(patterns, "Placed on 10-day IL")
    assert not transactions_sync.transaction_matches(patterns, "")
