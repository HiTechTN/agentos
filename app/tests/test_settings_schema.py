"""Tests for app/config/settings_schema.py — schema metadata."""

from app.config.settings_schema import get_settings_schema


class TestGetSettingsSchema:
    def test_returns_fields_and_categories(self) -> None:
        schema = get_settings_schema()
        assert "fields" in schema
        assert "categories" in schema
        assert len(schema["fields"]) > 0
        assert len(schema["categories"]) > 0

    def test_fields_have_required_keys(self) -> None:
        schema = get_settings_schema()
        for name, meta in schema["fields"].items():
            assert "category" in meta, f"{name} missing category"
            assert "description" in meta, f"{name} missing description"
            assert isinstance(meta["description"], str)

    def test_log_level_field_present(self) -> None:
        schema = get_settings_schema()
        assert "log_level" in schema["fields"]
        assert schema["fields"]["log_level"]["type"] == "string"
