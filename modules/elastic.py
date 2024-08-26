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

def get_es():
    return es

# Elasticsearch CRUD operations
def create_es_index(index_name):
    es.indices.create(index=index_name, ignore=400)

def add_to_es(index_name, document, id=None):

    if id:
        return es.index(index=index_name, id=id, body=document)
    
    else:
        return es.index(index=index_name, body=document)
    
def delete_from_es(index_name, document_id):
    return es.delete(index=index_name, id=document_id)

def search_es(index_name, query):
    return es.search(index=index_name, body=query)

def update_document(index_name, document_id, updated_fields):
    es.update(index=index_name, id=document_id, body={"doc": updated_fields})


def get_document_by_id(index_name, document_id):
    """
    Retrieve a document by its _id from the specified index.
    
    :param index_name: The name of the index to search in
    :param document_id: The _id of the document to retrieve
    :return: A dictionary containing the document if found, or None if not found
    """
    query = {
        "query": {
            "ids": {
                "values": [document_id]
            }
        }
    }
    
    result = search_es(index_name, query)
    
    if result["hits"]["total"]["value"] > 0:
        document = result["hits"]["hits"][0]["_source"]
        document["_id"] = result["hits"]["hits"][0]["_id"]
        return document
    
    return None

def bulk_delete_by_query(index_name, query):
    """
    Delete multiple documents that match the given query from the specified index.
    
    :param index_name: The name of the index to delete from
    :param query: The query to match documents for deletion
    :return: A dictionary containing the deletion results
    """
    return es.delete_by_query(index=index_name, body=query)

