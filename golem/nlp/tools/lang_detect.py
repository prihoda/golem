import os
import pandas as pd
import pickle
import requests
import tarfile
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.multiclass import OneVsRestClassifier

from golem.core.parsing.entity_extractor import EntityExtractor


class LanguageDetector(EntityExtractor):
    def __init__(self):
        super().__init__()
        try:
            with open("data/nlp/lang/lang_det.pkl", 'rb') as f:
                self.tfidf, self.cls = pickle.load(f)
        except Exception:
            self.tfidf, self.cls = self.train()

    def load_training_data(self):
        dl_path = os.path.join('data/nlp/lang', "sentences.tar.bz2")
        ds_path = os.path.join('data/nlp/lang', 'sentences.csv')

        if not os.path.isfile(ds_path):
            if not os.path.exists('data/nlp/lang'):
                os.mkdir('data/nlp/lang')
            print("Downloading language dataset ...")
            response = requests.get('http://downloads.tatoeba.org/exports/sentences.tar.bz2', stream=True)
            response.raise_for_status()
            with open(dl_path, 'wb') as f:
                for buf in response.iter_content(4096):
                    f.write(buf)

            print("Unzipping language dataset ...")
            with tarfile.open(dl_path, 'r:bz2') as f:
                f.extractall(path='data/nlp/lang')

        df = pd.read_csv(ds_path, delimiter='\t', header=None, error_bad_lines=False, warn_bad_lines=False)
        df.columns = ['id', 'lang', 'text']
        df = df[df['lang'].isin(['ces', 'slk', 'eng'])]  # TODO
        return df

    def train(self):
        print("Training language detector")
        df = self.load_training_data()
        # df.head()
        languages = df['lang'].drop_duplicates().values
        print(languages)
        lang_to_id = dict((lang, idx) for idx, lang in enumerate(languages))
        x_train, x_test, y_train, y_test = train_test_split(df['text'], df['lang'], test_size=0.1)
        tfidf = TfidfVectorizer().fit(x_train)
        # train
        cls = OneVsRestClassifier(LogisticRegression())
        cls.fit(tfidf.transform(x_train), y_train)  # TODO unidecode?
        y_pred = cls.predict(tfidf.transform(x_train))
        print("Training accuracy:", accuracy_score(y_train, y_pred))
        # test
        y_pred = cls.predict(tfidf.transform(x_test))
        print("Testing accuracy:", accuracy_score(y_test, y_pred))
        print("Language detector trained")
        with open("data/nlp/lang/lang_det.pkl", 'wb') as f:
            pickle.dump([tfidf, cls], f)
        return tfidf, cls

    def extract_entities(self, text: str, max_retries=5):
        features = self.tfidf.transform([text])
        labels = self.cls.predict(features)
        return {"_language": [{"value": labels[0]}]}
