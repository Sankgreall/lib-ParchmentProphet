import datetime as datetime
import os
from elasticsearch import Elasticsearch
import base64


elastic_url = os.getenv("ELASTIC_URL")
elastic_username = os.getenv("ELASTIC_USERNAME")
elastic_password = os.getenv("ELASTIC_PASSWORD")

# Initialize Elasticsearch connection
es = Elasticsearch(
    hosts=[f"{elastic_url}"],
    basic_auth=(elastic_username, elastic_password),
)

# Elasticsearch CRUD operations
def create_es_index(index_name):
    es.indices.create(index=index_name, ignore=400)

def add_to_es(index_name, document, id=None):

    if id:
        # Create a base64 encoded string from the document name
        document_id = base64.urlsafe_b64encode(id.encode()).decode()
    
        return es.index(index=index_name, id=document_id, body=document)
    
    else:
        return es.index(index=index_name, body=document)
    
def delete_from_es(index_name, document_id):
    return es.delete(index=index_name, id=document_id)

def search_es(index_name, query):
    return es.search(index=index_name, body=query)