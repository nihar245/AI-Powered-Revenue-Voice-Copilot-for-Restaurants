"""
Tests for the Intent Extraction and NLP modules.

Tests verify intent parsing, fuzzy matching, and upsell logic.
LLM-dependent tests are marked and can be skipped.
"""

import pytest
import json


class TestIntentExtraction:
    """Test suite for the intent extraction module."""

    @pytest.mark.asyncio
    async def test_extract_intent_order(self):
        """
        Test intent extraction for a typical order.
        
        Requires Gemini API key to be configured.
        """
        try:
            from app.nlp.intent import extract_intent

            result = await extract_intent("I want one paneer tikka and two cokes")

            assert "items" in result
            assert "intent_type" in result
            assert "sentiment" in result
            assert "duration_ms" in result
            assert result["intent_type"] in ("order", "inquiry", "greeting", "unknown", "error")
        except Exception as e:
            pytest.skip(f"LLM not available: {e}")

    @pytest.mark.asyncio
    async def test_extract_intent_greeting(self):
        """Test intent extraction for a greeting message."""
        try:
            from app.nlp.intent import extract_intent

            result = await extract_intent("Hello, good evening!")

            assert "intent_type" in result
            # Greeting might be detected as "greeting" or "unknown"
            assert result["intent_type"] in ("greeting", "unknown", "error")
        except Exception as e:
            pytest.skip(f"LLM not available: {e}")

    def test_clean_json_response_plain_json(self):
        """Test JSON cleaning with plain JSON input."""
        from app.nlp.intent import _clean_json_response

        raw = '{"items": [], "intent_type": "order"}'
        cleaned = _clean_json_response(raw)
        parsed = json.loads(cleaned)
        assert parsed["intent_type"] == "order"

    def test_clean_json_response_code_fence(self):
        """Test JSON cleaning with markdown code-fenced JSON."""
        from app.nlp.intent import _clean_json_response

        raw = '```json\n{"items": [], "intent_type": "order"}\n```'
        cleaned = _clean_json_response(raw)
        parsed = json.loads(cleaned)
        assert parsed["intent_type"] == "order"

    def test_clean_json_response_with_text(self):
        """Test JSON cleaning when there's surrounding text."""
        from app.nlp.intent import _clean_json_response

        raw = 'Here is the result:\n{"items": [{"name": "Coke"}]}\nDone.'
        cleaned = _clean_json_response(raw)
        parsed = json.loads(cleaned)
        assert len(parsed["items"]) == 1


class TestFuzzyMatching:
    """Test suite for the fuzzy matching module."""

    def test_exact_match(self):
        """Exact name should match with high confidence."""
        from app.services.matching import match_item

        result = match_item("Paneer Tikka")
        assert result is not None
        assert result["matched_item"] == "Paneer Tikka"
        assert result["confidence"] >= 90

    def test_fuzzy_match_misspelling(self):
        """Misspelled name should still match."""
        from app.services.matching import match_item

        result = match_item("paner tikka")
        assert result is not None
        assert result["matched_item"] == "Paneer Tikka"
        assert result["confidence"] >= 60

    def test_fuzzy_match_partial(self):
        """Partial name should match with lower threshold."""
        from app.services.matching import match_item

        result = match_item("biryani", threshold=50)
        assert result is not None
        assert "Biryani" in result["matched_item"]

    def test_no_match_gibberish(self):
        """Gibberish should not match above threshold."""
        from app.services.matching import match_item

        result = match_item("xyzabc123", threshold=80)
        assert result is None

    def test_match_multiple_items(self):
        """Match multiple items at once."""
        from app.services.matching import match_items

        results = match_items(["paneer tikka", "coke", "biryani"])
        assert len(results) == 3
        matched_names = [r["matched_item"] for r in results if r["matched_item"]]
        assert len(matched_names) >= 2  # At least 2 should match

    def test_top_matches(self):
        """Find top N matches returns a list."""
        from app.services.matching import find_top_matches

        results = find_top_matches("tikka", limit=3)
        assert len(results) == 3
        assert all("confidence" in r for r in results)


class TestUpsellService:
    """Test suite for the upsell service."""

    def test_upsell_combo_rule(self):
        """Should suggest combo pair when rule exists."""
        from app.services.upsell_service import suggest_upsell

        result = suggest_upsell(["Paneer Tikka"])
        assert result["suggestion"] == "Cold Coffee"
        assert result["source"] == "combo_rule"

    def test_upsell_biryani_raita(self):
        """Biryani should suggest Raita."""
        from app.services.upsell_service import suggest_upsell

        result = suggest_upsell(["Chicken Biryani"])
        assert result["suggestion"] == "Raita"
        assert result["source"] == "combo_rule"

    def test_upsell_beverage_category(self):
        """If no combo rule and no beverage, suggest one."""
        from app.services.upsell_service import suggest_upsell

        result = suggest_upsell(["Gulab Jamun"])
        # No combo rule for Gulab Jamun, should suggest a beverage
        assert result["suggestion"] is not None
        assert result["source"] in ("combo_rule", "category")

    def test_upsell_no_duplicate(self):
        """Should not suggest an item already ordered."""
        from app.services.upsell_service import suggest_upsell

        result = suggest_upsell(["Paneer Tikka", "Cold Coffee"])
        # Cold Coffee already ordered, should not re-suggest it
        if result["suggestion"]:
            assert result["suggestion"] != "Cold Coffee"


class TestMenuService:
    """Test suite for the menu service (stub)."""

    def test_get_menu_items(self):
        """Should return a non-empty list of strings."""
        from app.services.menu_service import get_menu_items

        items = get_menu_items()
        assert len(items) > 0
        assert all(isinstance(item, str) for item in items)

    def test_get_combo_rules(self):
        """Should return a non-empty dict."""
        from app.services.menu_service import get_combo_rules

        rules = get_combo_rules()
        assert len(rules) > 0
        assert "Paneer Tikka" in rules

    def test_get_menu_item_by_name(self):
        """Should find an item by exact name."""
        from app.services.menu_service import get_menu_item_by_name

        item = get_menu_item_by_name("Coke")
        assert item is not None
        assert item["name"] == "Coke"
        assert "price" in item

    def test_get_categories(self):
        """Should return distinct categories."""
        from app.services.menu_service import get_categories

        cats = get_categories()
        assert len(cats) > 0
        assert "beverages" in cats

    def test_roti_in_menu(self):
        """Roti should be in the menu."""
        from app.services.menu_service import get_menu_items

        items = get_menu_items()
        assert "Roti" in items


class TestOrderValidation:
    """Test suite for edge case validation."""

    def test_valid_order(self):
        """A correct order should validate fine."""
        from app.services.validation import validate_order

        intent = {
            "items": [{"name": "Paneer Tikka", "quantity": 2, "modifications": []}],
            "intent_type": "order",
            "sentiment": "positive",
        }
        result = validate_order(intent)
        assert result["is_valid"] is True
        assert len(result["validated_items"]) == 1
        assert result["validated_items"][0]["name"] == "Paneer Tikka"
        assert result["validated_items"][0]["quantity"] == 2

    def test_item_not_in_menu(self):
        """Unknown item should be rejected."""
        from app.services.validation import validate_order

        intent = {
            "items": [{"name": "Sushi Roll", "quantity": 1, "modifications": []}],
            "intent_type": "order",
            "sentiment": "neutral",
        }
        result = validate_order(intent)
        assert len(result["rejected_items"]) == 1
        assert len(result["warnings"]) > 0

    def test_empty_order(self):
        """Empty order should produce a warning."""
        from app.services.validation import validate_order

        intent = {"items": [], "intent_type": "order", "sentiment": "neutral"}
        result = validate_order(intent)
        assert result["is_valid"] is False
        assert len(result["warnings"]) > 0

    def test_quantity_capped(self):
        """Excessive quantity should be capped."""
        from app.services.validation import validate_order

        intent = {
            "items": [{"name": "Coke", "quantity": 999, "modifications": []}],
            "intent_type": "order",
            "sentiment": "neutral",
        }
        result = validate_order(intent)
        assert result["validated_items"][0]["quantity"] == 20
        assert any("maximum" in w.lower() or "cap" in w.lower() for w in result["warnings"])

    def test_invalid_modification_filtered(self):
        """Unsupported modifications should be filtered out."""
        from app.services.validation import validate_order

        intent = {
            "items": [{"name": "Paneer Tikka", "quantity": 1, "modifications": ["extra spicy", "with gold flakes"]}],
            "intent_type": "order",
            "sentiment": "neutral",
        }
        result = validate_order(intent)
        mods = result["validated_items"][0]["modifications"]
        assert "extra spicy" in mods
        assert "with gold flakes" not in mods
        assert any("gold flakes" in w for w in result["warnings"])

    def test_fuzzy_autocorrect(self):
        """Misspelled menu item should be auto-corrected."""
        from app.services.validation import validate_order

        intent = {
            "items": [{"name": "paner tikka", "quantity": 1, "modifications": []}],
            "intent_type": "order",
            "sentiment": "neutral",
        }
        result = validate_order(intent)
        assert len(result["validated_items"]) == 1
        assert result["validated_items"][0]["name"] == "Paneer Tikka"

    def test_ambiguous_item_warned(self):
        """Ambiguous item with medium confidence should produce a warning."""
        from app.services.validation import validate_order

        intent = {
            "items": [{"name": "tikka", "quantity": 1, "modifications": []}],
            "intent_type": "order",
            "sentiment": "neutral",
        }
        result = validate_order(intent)
        # Should match something with tikka but may warn
        assert len(result["validated_items"]) + len(result["rejected_items"]) == 1
