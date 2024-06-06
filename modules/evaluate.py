import re
import numpy as np
import pandas as pd
import nltk
import string
import syllapy
from nltk.tokenize import word_tokenize, sent_tokenize
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from collections import Counter
from sklearn.feature_extraction.text import CountVectorizer
from textstat import flesch_reading_ease, gunning_fog
import matplotlib.pyplot as plt
from scipy.spatial.distance import euclidean
import json
import spacy
import networkx as nx
from networkx.algorithms.similarity import graph_edit_distance
from transformers import pipeline

nltk.download('punkt')
nltk.download('stopwords')
nltk.download('words')
nltk.download('maxent_ne_chunker')

nlp = spacy.load('en_core_web_lg')
ner_pipeline = pipeline("ner", model="dbmdz/bert-large-cased-finetuned-conll03-english", grouped_entities=True)



def preprocess_text(text):
    # Remove markdown links, images, and titles
    text = re.sub(r'\[.*?\]\(.*?\)', '', text)  # Remove markdown links
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)  # Remove markdown images
    text = re.sub(r'#+', '', text)  # Remove markdown titles

    # Remove markdown tables
    text = re.sub(r'\|.*\|', '', text)  # Remove markdown table rows
    text = re.sub(r'\s*[-:]+\s*\|', '', text)  # Remove markdown table headers and separators

    # Remove embedded HTML completely
    text = re.sub(r'<[^>]*>', '', text)  # Remove HTML tags and their content

    # Replace line breaks and tabs with a space
    text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')

    # Remove extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

# 1. Lexical Diversity
def type_token_ratio(text):
    """
    Purpose: Calculate the ratio of unique words (types) to total words (tokens) in a text.
    Utility: Measures lexical diversity, indicating how varied the vocabulary is within the text.
    Value: A higher value suggests a more diverse vocabulary, which can be indicative of a richer and more complex language use.
    """
    text = preprocess_text(text)
    tokens = word_tokenize(text.lower())
    types = set(tokens)
    return len(types) / len(tokens)

def hapax_legomena_ratio(text):
    """
    Purpose: Calculate the ratio of words that appear only once (hapax legomena) to total words in a text.
    Utility: Provides insight into the uniqueness of the vocabulary used in the text.
    Value: A higher value indicates a higher proportion of unique, less repetitive vocabulary.
    """
    text = preprocess_text(text)
    tokens = word_tokenize(text.lower())
    freq_dist = Counter(tokens)
    hapax_legomena = [word for word in freq_dist if freq_dist[word] == 1]
    return len(hapax_legomena) / len(tokens)

# 2. Syntactic Features
def average_sentence_length(text):
    """
    Purpose: Calculate the average length of sentences in a text.
    Utility: Indicates syntactic complexity and verbosity.
    Value: Longer sentences can suggest more complex and detailed expression, while shorter sentences may indicate simplicity or brevity.
    """
    text = preprocess_text(text)
    sentences = sent_tokenize(text)
    words = word_tokenize(text)
    return len(words) / len(sentences)

def average_word_length(text):
    """
    Purpose: Calculate the average length of words in a text.
    Utility: Reflects lexical complexity; longer words often suggest a more advanced vocabulary.
    Value: Higher average word length can indicate a higher level of sophistication in language use.
    """
    text = preprocess_text(text)
    words = word_tokenize(text)
    return sum(len(word) for word in words) / len(words)

# 3. Lexical Features
def word_frequency_distribution(text):
    """
    Purpose: Calculate the distribution of word frequencies in a text.
    Utility: Provides insights into vocabulary richness and word usage patterns.
    Value: Helps in understanding the diversity of word usage and identifying the most dominant words in the text.
    """
    text = preprocess_text(text)
    words = word_tokenize(text.lower())
    freq_dist = Counter(words)
    unique_word_count = len(freq_dist)
    most_common_word_frequency = freq_dist.most_common(1)[0][1] if freq_dist else 0
    return float(unique_word_count), float(most_common_word_frequency)

def common_ngrams(text, n=3):
    """
    Purpose: Calculate the average frequency of common n-grams (word sequences) in a text.
    Utility: Assesses repetitive patterns or common phrases used within the text.
    Value: A higher average frequency can indicate repetitive usage of certain phrases or expressions.
    """
    text = preprocess_text(text)
    vectorizer = CountVectorizer(ngram_range=(n, n))
    ngrams = vectorizer.fit_transform([text])
    ngram_freq = ngrams.toarray().sum(axis=0)
    average_ngram_frequency = np.mean(ngram_freq)
    return average_ngram_frequency

# 4. Readability Scores
def flesch_kincaid_reading_ease_score(text):
    """
    Purpose: Calculate the Flesch-Kincaid Reading Ease score of a text.
    Utility: Measures how easy or difficult a text is to read.
    Value: Higher scores indicate easier readability, while lower scores suggest higher complexity and difficulty.
    """
    text = preprocess_text(text)
    return flesch_reading_ease(text)

def gunning_fog_index_score(text):
    """
    Purpose: Calculate the Gunning Fog Index score of a text.
    Utility: Estimates the years of formal education needed to understand the text on a first reading.
    Value: A higher score suggests that the text is more complex and harder to read.
    """    
    text = preprocess_text(text)
    return gunning_fog(text)

# 5. Semantic Features
def named_entity_recognition_counts(text):
    """
    Purpose: Count the occurrences of named entities (like people, organizations, locations) in a text.
    Utility: Provides insight into the content and focus of the text by identifying significant entities.
    Value: Higher counts can indicate a text rich in specific details and proper nouns, which might suggest a higher level of informational content.
    """    
    text = preprocess_text(text)
    words = word_tokenize(text)
    tagged = nltk.pos_tag(words)
    entities = nltk.ne_chunk(tagged)
    entity_counts = Counter(ent.label() for ent in entities if isinstance(ent, nltk.Tree))
    total_entity_count = sum(entity_counts.values())
    most_common_entity_type_count = entity_counts.most_common(1)[0][1] if entity_counts else 0
    return float(total_entity_count), float(most_common_entity_type_count)


# 6. Stylistic Features
def use_of_passive_voice(text):
    """
    Purpose: Calculate the frequency of passive voice constructions per 100 words in a text.
    Utility: Indicates stylistic choices, as passive voice can affect the tone and clarity of the writing.
    Value: A higher frequency of passive voice may suggest a more formal or impersonal tone.
    """
    text = preprocess_text(text)
    tokens = word_tokenize(text)
    tagged = nltk.pos_tag(tokens)
    passive_count = sum(1 for i in range(len(tagged) - 2) if tagged[i][1] == 'VBN' and tagged[i + 1][0] in ('is', 'was', 'were', 'be', 'been', 'being'))
    
    # Normalize the count by the number of words and scale to per 100 words
    words_count = len(tokens)
    if words_count == 0:
        return 0.0
    passive_frequency = (passive_count / words_count) * 100
    return passive_frequency

def frequency_of_different_punctuation_marks(text):
    """
    Purpose: Calculate the average frequency of different punctuation marks in a text.
    Utility: Provides insights into the stylistic and structural aspects of the writing.
    Value: High variability in punctuation use can indicate a more complex or nuanced writing style.
    """    
    text = preprocess_text(text)
    punctuation_counts = Counter(char for char in text if char in string.punctuation)
    total_punctuation_count = sum(punctuation_counts.values())
    if total_punctuation_count == 0:
        return 0.0
    average_punctuation_count = total_punctuation_count / len(punctuation_counts)
    return average_punctuation_count

# 7. Phonological Features
def average_syllable_count_per_word(text):
    text = preprocess_text(text)
    words = word_tokenize(text)
    total_syllables = sum(syllapy.count(word) for word in words)
    return total_syllables / len(words)

def syllable_count_per_word(text):
    """
    Purpose: Calculate the syllable count for each word in the text.
    Utility: Provides the basis for analyzing rhythmic complexity.
    Value: List of syllable counts corresponding to each word in the text.
    """
    text = preprocess_text(text)
    words = word_tokenize(text)
    syllable_counts = [syllapy.count(word) for word in words]
    return syllable_counts

def rhythmic_complexity(text):
    """
    Purpose: Calculate a metric for rhythmic complexity based on syllable count variability and regularity.
    Utility: Provides a more meaningful measure of rhythmic complexity beyond text length.
    Value: A higher value indicates greater rhythmic complexity.
    """
    syllable_counts = syllable_count_per_word(text)
    
    if len(syllable_counts) < 2:
        return 0.0  # Not enough data to calculate variability
    
    # Calculate the standard deviation of syllable counts
    std_dev = np.std(syllable_counts)
    
    # Calculate the average absolute difference between consecutive syllable counts
    avg_abs_diff = np.mean([abs(syllable_counts[i] - syllable_counts[i-1]) for i in range(1, len(syllable_counts))])
    
    # Combine both measures into a single metric (you may adjust the combination formula as needed)
    rhythmic_complexity = std_dev + avg_abs_diff
    
    return float(rhythmic_complexity)

def extract_features(text):
    preprocessed_text = preprocess_text(text)
    
    unique_word_count, most_common_word_frequency = word_frequency_distribution(preprocessed_text)
    total_entity_count, most_common_entity_type_count = named_entity_recognition_counts(preprocessed_text)
    
    features = {
        "type_token_ratio": type_token_ratio(preprocessed_text),
        "hapax_legomena_ratio": hapax_legomena_ratio(preprocessed_text),
        # "average_sentence_length": average_sentence_length(preprocessed_text),
        # "average_word_length": average_word_length(preprocessed_text),
        # "unique_word_count": unique_word_count,
        # "most_common_word_frequency": most_common_word_frequency,
        "average_common_bigram_frequency": common_ngrams(preprocessed_text, 2),
        "flesch_kincaid_reading_ease_score": flesch_kincaid_reading_ease_score(preprocessed_text),
        "gunning_fog_index_score": gunning_fog_index_score(preprocessed_text),
        # "total_entity_count": total_entity_count,
        # "most_common_entity_type_count": most_common_entity_type_count,
        "use_of_passive_voice": use_of_passive_voice(preprocessed_text),
        # "average_punctuation_frequency": frequency_of_different_punctuation_marks(preprocessed_text),
        # "average_syllable_count_per_word": average_syllable_count_per_word(preprocessed_text),
        # "rhythmic_complexity": rhythmic_complexity(preprocessed_text)
    }
    
    return features

def compare_samples_nd(samples):
    human_features_list = []
    ai_features_list = []

    for sample_pair in samples:
        human_features = extract_features(sample_pair["human_generated"])
        ai_features = extract_features(sample_pair["ai_generated"])
        human_features_list.append(human_features)
        ai_features_list.append(ai_features)

    human_df = pd.DataFrame(human_features_list)
    ai_df = pd.DataFrame(ai_features_list)


    # Standardize features
    scaler = StandardScaler()
    standardized_human_features = scaler.fit_transform(human_df)
    standardized_ai_features = scaler.transform(ai_df)

    # Compute Euclidean distances
    distances = [euclidean(standardized_human_features[i], standardized_ai_features[i]) for i in range(len(samples))]

    # Compute average distances
    avg_distance = np.mean(distances)

    # Prepare individual scores DataFrame
    individual_scores = pd.DataFrame({
        "Human Features": human_features_list,
        "AI Features": ai_features_list,
        "Distance": distances
    })

    return individual_scores, avg_distance

def compare_samples_pca(sample_list):
    human_features_list = []
    ai_features_list = []

    for sample_pair in sample_list:
        human_features = extract_features(sample_pair["human_generated"])
        ai_features = extract_features(sample_pair["ai_generated"])
        human_features_list.append(human_features)
        ai_features_list.append(ai_features)

    all_features = human_features_list + ai_features_list
    feature_df = pd.DataFrame(all_features)

    # Standardize features
    scaler = StandardScaler()
    standardized_features = scaler.fit_transform(feature_df)

    # Apply PCA
    pca = PCA(n_components=2)
    pca_features = pca.fit_transform(standardized_features)

    # Create a DataFrame for PCA results
    pca_df = pd.DataFrame(pca_features, columns=["PC1", "PC2"])
    pca_df["Sample Type"] = ["Human"] * len(human_features_list) + ["AI"] * len(ai_features_list)

    # Compute average scores
    avg_human_features = np.mean(standardized_features[:len(human_features_list)], axis=0)
    avg_ai_features = np.mean(standardized_features[len(human_features_list):], axis=0)

    avg_human_score = np.mean(avg_human_features)
    avg_ai_score = np.mean(avg_ai_features)

    # Combine individual scores with sample type for each pair
    individual_scores = pd.DataFrame({
        "Human Features": human_features_list,
        "AI Features": ai_features_list
    })

    return pca_df, individual_scores, avg_human_score, avg_ai_score

def ner_overlap_similarity(human_text, ai_text):
    human_entities_raw = ner_pipeline(human_text)
    ai_entities_raw = ner_pipeline(ai_text)

    print("Raw Human Entities:")
    print(human_entities_raw)
    print("Raw AI Entities:")
    print(ai_entities_raw)

    # Extract entity texts
    human_entities = {entity['word'] for entity in human_entities_raw}
    ai_entities = {entity['word'] for entity in ai_entities_raw}

    print("Processed Human Entities:")
    print(human_entities)
    print("Processed AI Entities:")
    print(ai_entities)

    intersection = human_entities.intersection(ai_entities)
    union = human_entities.union(ai_entities)

    print(f"Intersection: {intersection}")
    print(f"Union: {union}")

    jaccard_similarity = len(intersection) / len(union) if union else 0.0

    return jaccard_similarity

def compute_ner_similarity(samples):
    ner_results = []

    for sample in samples:
        human_text = sample["human_generated"]
        ai_text = sample["ai_generated"]

        ner_similarity = ner_overlap_similarity(human_text, ai_text)

        result = {
            "NER Similarity": ner_similarity,
        }
        ner_results.append(result)

    ner_df = pd.DataFrame(ner_results)
    avg_ner_similarity = ner_df["NER Similarity"].mean()

    return ner_df, avg_ner_similarity

if __name__ == "__main__":
    samples = [
        {
            "human_generated": (
                "The advancements in artificial intelligence over the past decade "
                "have been remarkable. Researchers at MIT and Google have developed algorithms that "
                "can learn from data, recognize patterns, and make decisions with "
                "a high degree of accuracy. However, ethical concerns remain, particularly "
                "around the potential for bias and the impact on employment. Addressing these "
                "issues will require ongoing dialogue and collaboration between technologists, "
                "policymakers in the United States, and the public."
            ),
            "ai_generated": (
                "The incredible advancements in toy bunnies over the past decade "
                "have been remarkable. Researchers at MIT and Google have developed algorithms that "
                "can learn from data, recognize patterns, and make decisions with "
                "a high degree of accuracy. However, ethical concerns remain, particularly "
                "around the potential for bias and the impact on employment. Addressing these "
                "issues will require ongoing dialogue and collaboration between technologists, "
                "policymakers in the United States, and the public."
            )
        },
        {
            "human_generated": (
                "Climate change poses a significant threat to ecosystems and human societies. "
                "The increasing frequency and intensity of extreme weather events, rising sea levels, "
                "and shifting climate patterns are already having profound impacts. Efforts to mitigate "
                "these effects include reducing greenhouse gas emissions, transitioning to renewable energy "
                "sources, and enhancing resilience through better infrastructure and planning, according to the UN."
            ),
            "ai_generated": (
                "Swamp change poses a really significant threat to ecosystems and human societies. "
                "The increasing frequency and intensity of extreme weather events, rising sea levels, "
                "and shifting swamp patterns are already having profound impacts. Efforts to mitigate "
                "these effects include reducing greenhouse gas emissions, transitioning to renewable energy "
                "sources, and enhancing resilience through better infrastructure and planning, according to the UN."
            )
        }
    ]
    # Compute linguistic similarity
    linguistic_scores, linguistic_distance = compare_samples_nd(samples)
    print("Linguistic Distance:", linguistic_distance)

    # Compute NER similarity
    ner_df, avg_ner_similarity = compute_ner_similarity(samples)
    print(ner_df)
    print("Average NER Similarity:", avg_ner_similarity)

