import uuid
import re
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern, RecognizerRegistry
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig


OUTBOUND_REDACTION_ENABLED = True
OUTBOUND_REDACTION_ENTITIES = (
    "PERSON",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "CREDIT_CARD",
)
UI_REDACTION_EXCLUDED_ENTITIES = ("PERSON",)

class PII_Vault:
    def __init__(self):
        # 1. Create pattern for Serbian license plates
        # Supported formats: BG-123-AA, BG 123 AA, BG123AA
        plate_pattern = Pattern(
            name="serbian_plate_pattern", 
            regex=r'[A-Z]{2}[-\s]?\d{3,5}[-\s]?[A-Z]{2}', 
            score=0.8
        )
        
        # 2. Create the recognizer
        plate_recognizer = PatternRecognizer(
            supported_entity="CAR_PLATE", 
            patterns=[plate_pattern]
        )

        # 3. Configure the registry (add built-in recognizers + our custom one)
        registry = RecognizerRegistry()
        registry.load_predefined_recognizers() # Load PERSON, PHONE_NUMBER, etc.
        registry.add_recognizer(plate_recognizer)

        # 4. Pass the registry to the engine
        self.analyzer = AnalyzerEngine(registry=registry)
        self.anonymizer = AnonymizerEngine()
        self.vault = {}

    def _generate_typed_id(self, value, entity_type):
        """Creates a typed ID and stores it in the local vault"""
        prefix = "USER" if entity_type == "PERSON" else "PLATE" if entity_type == "CAR_PLATE" else "ID"
        unique_id = f"{prefix}_{uuid.uuid4().hex[:4].upper()}"
        self.vault[unique_id] = value
        return unique_id

    def tokenize_value(self, value: str, entity_type: str):
        """
        Deterministically map known sensitive values to vault tokens.
        Reuses existing token for the same value when possible.
        """
        if not value:
            return value

        for token, real_value in self.vault.items():
            if real_value == value:
                return token

        return self._generate_typed_id(value, entity_type)

    def anonymize_session(self, text: str):
        # CAR_PLATE is now available for analysis
        results = self.analyzer.analyze(text=text, entities=["PERSON", "CAR_PLATE", "PHONE_NUMBER", "CREDIT_CARD", "EMAIL_ADDRESS"], language='en')
        
        operators = {
            "PERSON": OperatorConfig("custom", {"lambda": lambda x: self._generate_typed_id(x, "PERSON")}),
            "CAR_PLATE": OperatorConfig("custom", {"lambda": lambda x: self._generate_typed_id(x, "CAR_PLATE")}),
        }

        anonymized = self.anonymizer.anonymize(text=text, analyzer_results=results, operators=operators)
        return anonymized.text

    def get_real_value(self, placeholder: str):
        return self.vault.get(placeholder, placeholder)
    
    def deanonymize_text(self, text: str):
        """
        Searches the text for any tokens (USER_XXXX, PLATE_XXXX)
        and replaces them with the real values from self.vault.
        """
        if not text:
            return text
            
        # Regex matches tokens starting with USER_, PLATE_, LOC_, or ID_
        pattern = r'(USER_[A-Z0-9]{4}|PLATE_[A-Z0-9]{4}|LOC_[A-Z0-9]{4}|ID_[A-Z0-9]{4})'
        
        def replace_match(match):
            token = match.group(0)
            # Return the real value if it exists in the vault
            return self.vault.get(token, token)

        return re.sub(pattern, replace_match, text)

    def redact_outbound_text(self, text: str, entities: tuple[str, ...] | list[str] | None = None):
        if not text or not OUTBOUND_REDACTION_ENABLED:
            return text

        selected_entities = tuple(entities or OUTBOUND_REDACTION_ENTITIES)
        if not selected_entities:
            return text

        analyzer_results = self.analyzer.analyze(
            text=text,
            entities=list(selected_entities),
            language="en",
        )

        if "PERSON" in selected_entities:
            analyzer_results = self._filter_address_like_person_entities(text, analyzer_results)

        if not analyzer_results:
            return text

        operators = {
            entity: OperatorConfig("replace", {"new_value": f"[{entity}]"})
            for entity in selected_entities
        }

        redacted = self.anonymizer.anonymize(
            text=text,
            analyzer_results=analyzer_results,
            operators=operators,
        )
        return redacted.text

    def _filter_address_like_person_entities(self, text: str, analyzer_results: list):
        """Avoid masking PERSON entities when they are likely part of an address."""
        if not analyzer_results:
            return analyzer_results

        street_tokens = (
            "street",
            "st",
            "st.",
            "road",
            "rd",
            "rd.",
            "avenue",
            "ave",
            "ave.",
            "boulevard",
            "blvd",
            "blvd.",
            "ulica",
            "ul.",
            "bulevar",
            "trg",
            "bb",
        )

        filtered = []
        for result in analyzer_results:
            if getattr(result, "entity_type", "") != "PERSON":
                filtered.append(result)
                continue

            end = int(getattr(result, "end", 0))
            window = text[end : min(len(text), end + 32)].strip().lower()
            starts_with_number = bool(re.match(r"^\d+", window))
            has_street_hint = any(re.match(rf"^{re.escape(token)}\b", window) for token in street_tokens)
            if starts_with_number or has_street_hint:
                continue

            filtered.append(result)

        return filtered

    def render_safe_text(self, text: str):
        return self.redact_outbound_text(self.deanonymize_text(text))

    def render_user_visible_text(self, text: str):
        """
        UI renderer:
        - deanonymize placeholders for user readability
        - keep person names visible
        - still redact other sensitive entities
        """
        if not text:
            return text

        visible_text = self.deanonymize_text(text)
        ui_entities = tuple(
            entity for entity in OUTBOUND_REDACTION_ENTITIES if entity not in UI_REDACTION_EXCLUDED_ENTITIES
        )
        return self.redact_outbound_text(visible_text, entities=ui_entities)

protector = PII_Vault()