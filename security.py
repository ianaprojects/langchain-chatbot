import uuid
import re
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern, RecognizerRegistry
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

class PII_Vault:
    def __init__(self):
        # 1. Создаем паттерн для сербских номеров
        # Учитываем форматы: BG-123-AA, BG 123 AA, BG123AA
        plate_pattern = Pattern(
            name="serbian_plate_pattern", 
            regex=r'[A-Z]{2}[-\s]?\d{3,5}[-\s]?[A-Z]{2}', 
            score=0.8
        )
        
        # 2. Создаем сам распознаватель
        plate_recognizer = PatternRecognizer(
            supported_entity="CAR_PLATE", 
            patterns=[plate_pattern]
        )

        # 3. Настраиваем реестр (добавляем стандартные + наш новый)
        registry = RecognizerRegistry()
        registry.load_predefined_recognizers() # Загружаем PERSON, PHONE_NUMBER и т.д.
        registry.add_recognizer(plate_recognizer)

        # 4. Передаем реестр в движок
        self.analyzer = AnalyzerEngine(registry=registry)
        self.anonymizer = AnonymizerEngine()
        self.vault = {}

    def _generate_typed_id(self, value, entity_type):
        """Создает типизированный ID и сохраняет в локальный сейф"""
        prefix = "USER" if entity_type == "PERSON" else "PLATE" if entity_type == "CAR_PLATE" else "ID"
        unique_id = f"{prefix}_{uuid.uuid4().hex[:4].upper()}"
        self.vault[unique_id] = value
        return unique_id

    def anonymize_session(self, text: str):
        # Теперь CAR_PLATE доступен для анализа
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
        Ищет в тексте любые токены (USER_XXXX, PLATE_XXXX) 
        и заменяет их на реальные значения из self.vault.
        """
        if not text:
            return text
            
        # Регулярка ищет слова, начинающиеся с USER_, PLATE_ или LOC_
        pattern = r'(USER_[A-Z0-9]{4}|PLATE_[A-Z0-9]{4}|LOC_[A-Z0-9]{4}|ID_[A-Z0-9]{4})'
        
        def replace_match(match):
            token = match.group(0)
            # Возвращаем реальное значение, если оно есть в сейфе
            return self.vault.get(token, token)

        return re.sub(pattern, replace_match, text)

protector = PII_Vault()