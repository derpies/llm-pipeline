"""Tests for Weaviate schema initialization and tenant management."""

from unittest.mock import MagicMock, patch

from llm_pipeline.knowledge.weaviate_schema import (
    RAG_COLLECTION,
    SUMMARIZATION_COLLECTION,
    TIER_COLLECTIONS,
    ensure_tenant,
    init_weaviate,
)


def _mock_client(existing_collections: set[str] | None = None) -> MagicMock:
    """Build a mock Weaviate client."""
    existing = existing_collections or set()
    client = MagicMock()
    client.collections.exists.side_effect = lambda name: name in existing
    client.collections.create.return_value = None
    return client


class TestInitWeaviate:
    def test_creates_all_collections(self):
        client = _mock_client()
        init_weaviate(client)

        created_names = {
            call.kwargs["name"] if "name" in call.kwargs else call.args[0]
            for call in client.collections.create.call_args_list
        }
        expected = set(TIER_COLLECTIONS.values()) | {SUMMARIZATION_COLLECTION, RAG_COLLECTION}
        assert created_names == expected

    def test_idempotent_skips_existing(self):
        existing = set(TIER_COLLECTIONS.values()) | {SUMMARIZATION_COLLECTION, RAG_COLLECTION}
        client = _mock_client(existing)
        init_weaviate(client)
        client.collections.create.assert_not_called()

    def test_finding_collection_has_extra_properties(self):
        client = _mock_client()
        init_weaviate(client)

        # Find the Finding collection create call
        for call in client.collections.create.call_args_list:
            name = call.kwargs.get("name", call.args[0] if call.args else None)
            if name == "Finding":
                props = call.kwargs.get("properties", [])
                prop_names = {p.name for p in props}
                assert "finding_status" in prop_names
                assert "entry_id" in prop_names  # base property
                break
        else:
            raise AssertionError("Finding collection create call not found")

    def test_all_collections_have_multi_tenancy(self):
        client = _mock_client()
        init_weaviate(client)

        for call in client.collections.create.call_args_list:
            mt_config = call.kwargs.get("multi_tenancy_config")
            assert mt_config is not None, f"Missing multi_tenancy_config for {call}"


class TestEnsureTenant:
    def test_creates_new_tenant(self):
        client = MagicMock()
        collection = MagicMock()
        client.collections.get.return_value = collection
        collection.tenants.get.return_value = {}

        ensure_tenant(client, "Finding", "community")

        collection.tenants.create.assert_called_once()

    def test_skips_existing_active_tenant(self):
        client = MagicMock()
        collection = MagicMock()
        client.collections.get.return_value = collection

        from weaviate.classes.tenants import TenantActivityStatus

        mock_tenant = MagicMock()
        mock_tenant.activity_status = TenantActivityStatus.ACTIVE
        collection.tenants.get.return_value = {"community": mock_tenant}

        ensure_tenant(client, "Finding", "community")

        collection.tenants.create.assert_not_called()
        collection.tenants.update.assert_not_called()
