from abc import ABC, abstractmethod


class NLUModel(ABC):

    @abstractmethod
    def predict(self, utterance: str, threshold=None) -> dict or list or None:
        pass
