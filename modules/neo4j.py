import os
from neo4j import GraphDatabase
from neo4j.exceptions import ClientError


neo4j_uri = os.getenv("NEO4J_URI")
neo4j_username = os.getenv("NEO4J_USERNAME")
neo4j_password = os.getenv("NEO4J_PASSWORD")

# Initialize Neo4j connection
driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_username, neo4j_password))

def get_neo4j():
    return driver

#############################################################
# TEST CONNECTION
#############################################################

def test_neo4j_connection():
    with driver.session() as session:
        result = session.run("RETURN 1 AS num")
        result.single()


#############################################################
# CREATE AND FETCH ENTITIES 
#############################################################

def create_entities_and_relationships(tx, entities, relationships, project_id):
    # Create or update entities
    for entity in entities:
        tx.run("""
            MERGE (e:Entity {name: $name, project_id: $project_id})
            SET e.type = $type,
                e.description = $description,
                e.references = $references
        """, name=entity["name"], type=entity["type"], 
            description=entity["description"], 
            references=entity["references"],
            project_id=project_id)
    
    # Create relationships
    for relationship in relationships:
        query = """
            MATCH (a:Entity {name: $from_entity, project_id: $project_id})
            MATCH (b:Entity {name: $to_entity, project_id: $project_id})
            MERGE (a)-[r:RELATED_TO]->(b)
            SET r.description = $description,
                r.references = $references,
                r.project_id = $project_id
        """
        tx.run(query, 
            from_entity=relationship["source"], 
            to_entity=relationship["target"], 
            description=relationship["description"],
            references=relationship["references"],
            project_id=project_id)

def fetch_project_graph(project_id):
    with driver.session() as session:
        result = session.run("""
            MATCH (e:Entity {project_id: $project_id})
            OPTIONAL MATCH (e)-[r:RELATED_TO]->(target:Entity {project_id: $project_id})
            RETURN e, r, target
        """, project_id=project_id)
        return list(result)  # Convert result to a list so it can be used outside the session
    

def get_all_entities(project_id):
    with driver.session() as session:
        result = session.run("""
            MATCH (e:Entity {project_id: $project_id})
            RETURN e.name AS name, e.type AS type
        """, project_id=project_id)
        return {record["name"]: record["type"] for record in result}
    
#############################################################
# CRUD FUNCTIONS
#############################################################

def add_to_neo4j(data, project_id):
    with driver.session() as session:
        entities = data.get("entities", [])
        relationships = data.get("relationships", [])
        session.write_transaction(create_entities_and_relationships, entities, relationships, project_id)

def delete_from_neo4j(chunk_id, project_id):
    with driver.session() as session:
        session.run("""
            MATCH (e:Entity {chunk_id: $chunk_id, project_id: $project_id})
            DETACH DELETE e
        """, chunk_id=chunk_id, project_id=project_id)

def search_neo4j(query, project_id):
    with driver.session() as session:
        # Modify the query to include project_id filter
        modified_query = f"""
            MATCH (e:Entity {{project_id: $project_id}})
            WHERE {query}
            RETURN e
        """
        result = session.run(modified_query, project_id=project_id)
        return [record.data() for record in result]

def update_entity(entity_name, updated_fields, project_id):
    with driver.session() as session:
        session.run("""
            MATCH (e:Entity {name: $name, project_id: $project_id})
            SET e += $updated_fields
        """, name=entity_name, updated_fields=updated_fields, project_id=project_id)

def delete_project_data_from_neo4j(project_id):
    with driver.session() as session:
        session.run("""
            MATCH (n {project_id: $project_id})
            DETACH DELETE n
        """, project_id=project_id)

#############################################################
# EMEDDING FUNCTIONS
#############################################################

def project_graph(tx, project_id, node_label, relationship_type):
    tx.run("""
        CALL gds.graph.project($graph_name, 
            {
                Entity: {
                    label: $node_label,
                    properties: ['embedding'],
                    nodeFilter: 'project_id = $project_id'
                }
            }, 
            {
                RELATED_TO: {
                    type: $relationship_type,
                    orientation: 'UNDIRECTED',
                    relationshipFilter: 'project_id = $project_id'
                }
            }
        )
    """, graph_name=project_id, node_label=node_label, relationship_type=relationship_type, project_id=project_id)

def create_and_store_embeddings(
    tx, 
    project_id,
    write_property='embedding', 
    embedding_dimension=64, 
    walk_length=80, 
    walks_per_node=10, 
    in_out_factor=1.0, 
    return_factor=1.0, 
    concurrency=4
):
    tx.run("""
        CALL gds.node2vec.write($graph_name, {
            writeProperty: $write_property,
            embeddingDimension: $embedding_dimension,
            walkLength: $walk_length,
            walksPerNode: $walks_per_node,
            inOutFactor: $in_out_factor,
            returnFactor: $return_factor,
            concurrency: $concurrency
        })
    """, graph_name=project_id, write_property=write_property, embedding_dimension=embedding_dimension, 
       walk_length=walk_length, walks_per_node=walks_per_node, in_out_factor=in_out_factor, 
       return_factor=return_factor, concurrency=concurrency)
    
def drop_graph(tx, project_id):
    tx.run("CALL gds.graph.drop($graph_name)", graph_name=project_id)

def process_embeddings(
    project_id,
    node_label='Entity', 
    relationship_type='RELATED_TO', 
    write_property='embedding', 
    embedding_dimension=64, 
    walk_length=80, 
    walks_per_node=10, 
    in_out_factor=1.0, 
    return_factor=1.0, 
    concurrency=4
):
    with driver.session() as session:
        # Step 1: Project the graph into GDS
        session.write_transaction(project_graph, project_id, node_label, relationship_type)
        
        # Step 2: Create and store the embeddings
        session.write_transaction(create_and_store_embeddings, project_id, write_property, embedding_dimension, walk_length, walks_per_node, in_out_factor, return_factor, concurrency)
        
        # Step 3: Optionally, drop the graph from GDS memory
        session.write_transaction(drop_graph, project_id)

#############################################################
# EMEDDING FUNCTIONS
#############################################################

def similarity_search_neo4j(project_id, query_embedding, query_text, top_k=5, entity_types=None, include_entities=None, exclude_entities=None):
    keywords = query_text.lower().split()
    
    with driver.session() as session:
        try:
            result = session.run("""
                MATCH (e:Entity {project_id: $project_id})
                WHERE e.embedding IS NOT NULL AND size(e.embedding) = 64
                    AND (CASE WHEN $entity_types IS NOT NULL THEN e.type IN $entity_types ELSE true END)
                    AND (CASE WHEN $include_entities IS NOT NULL THEN e.name IN $include_entities ELSE true END)
                    AND (CASE WHEN $exclude_entities IS NOT NULL THEN NOT e.name IN $exclude_entities ELSE true END)
                WITH e, gds.similarity.cosine(e.embedding, $query_embedding) AS embedding_similarity,
                     toLower(e.name + ' ' + e.description) AS full_text
                WITH e, embedding_similarity, full_text,
                     REDUCE(count = 0, keyword IN $keywords | 
                         CASE WHEN full_text CONTAINS keyword THEN count + 1 ELSE count END
                     ) AS keyword_matches
                WITH e, 
                     embedding_similarity * 0.7 + 
                     (toFloat(keyword_matches) / size($keywords)) * 0.3 AS combined_score
                ORDER BY combined_score DESC, e.name
                LIMIT $top_k
                RETURN e.name AS name, e.type AS type, e.description AS description, 
                       combined_score AS similarity
            """, {
                "project_id": project_id,
                "query_embedding": query_embedding,
                "keywords": keywords,
                "top_k": top_k,
                "entity_types": entity_types,
                "include_entities": include_entities,
                "exclude_entities": exclude_entities
            })
            return [record.data() for record in result]
        except ClientError as e:
            print(f"An error occurred while querying Neo4j: {str(e)}")
            return []

#############################################################
# CLOSE CONNECTION
#############################################################

def close_connection():
    driver.close()