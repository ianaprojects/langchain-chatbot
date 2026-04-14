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

    def redact_outbound_text(self, text: str):
        if not text or not OUTBOUND_REDACTION_ENABLED:
            return text

        analyzer_results = self.analyzer.analyze(
            text=text,
            entities=list(OUTBOUND_REDACTION_ENTITIES),
            language="en",
        )

        if not analyzer_results:
            return text

        operators = {
            entity: OperatorConfig("replace", {"new_value": f"[{entity}]"})
            for entity in OUTBOUND_REDACTION_ENTITIES
        }

        redacted = self.anonymizer.anonymize(
            text=text,
            analyzer_results=analyzer_results,
            operators=operators,
        )
        return redacted.text

    def render_safe_text(self, text: str):
        return self.redact_outbound_text(self.deanonymize_text(text))

protector = PII_Vault()