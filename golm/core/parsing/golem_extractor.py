from core.parsing.entity_extractor import EntityExtractor


class GolemExtractor(EntityExtractor):

    def __init__(self):
        super().__init__()

    def extract_entities(self, text: str, max_retries=1):
        # TODO use a separate thread (pool) to remove TF memory overhead
        from core.nlp.classify import classify
        return classify(text)
