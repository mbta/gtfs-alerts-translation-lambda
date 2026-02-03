from abc import ABC, abstractmethod


class Translator(ABC):
    @abstractmethod
    async def translate_batch(self, texts: list[str], target_lang: str) -> list[str]:
        """
        Translate multiple strings into the target language.
        Returns translations in the same order as input texts.
        """
        pass


class MockTranslator(Translator):
    async def translate_batch(self, texts: list[str], target_lang: str) -> list[str]:
        """
        Appends the language code to the text for testing.
        """
        return [f"[{target_lang}] {text}" for text in texts]
