import pytest

from longshot import registry


def test_empty_registry_roundtrip(tmp_path):
    p = tmp_path / "r.csv"
    registry.save(registry.empty(), p)
    df = registry.load(p)
    assert list(df.columns) == registry.COLUMNS
    assert len(df) == 0


def test_upsert_insert_and_update(tmp_path):
    df = registry.upsert(registry.empty(), [{"id": "LS-0001", "tic": "123", "status": "signal"}])
    df = registry.upsert(df, [{"id": "LS-0001", "status": "candidate"}])
    assert len(df) == 1
    assert df.loc[0, "status"] == "candidate"
    assert df.loc[0, "tic"] == "123"


def test_rejects_unknown_status():
    with pytest.raises(registry.RegistryError):
        registry.upsert(registry.empty(), [{"id": "LS-1", "status": "planet"}])


def test_rejected_needs_reason():
    with pytest.raises(registry.RegistryError):
        registry.upsert(registry.empty(), [{"id": "LS-1", "status": "rejected"}])
    df = registry.upsert(
        registry.empty(),
        [{"id": "LS-1", "status": "rejected", "rejection_reason": "momentum dump"}],
    )
    assert df.loc[0, "rejection_reason"] == "momentum dump"


def test_unknown_field_is_error():
    with pytest.raises(registry.RegistryError):
        registry.upsert(registry.empty(), [{"id": "LS-1", "status": "signal", "planet": "yes"}])


def test_committed_registry_is_valid():
    registry.load(registry.DEFAULT_PATH)
