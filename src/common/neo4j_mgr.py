import os
from neo4j import GraphDatabase

class Neo4jManager:
    _driver = None

    @classmethod
    def get_driver(cls):
        """
        Returns the singleton Neo4j driver instance.
        """
        if cls._driver is None:
            # Default to docker service name 'neo4j' if running inside container
            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            user = os.getenv("NEO4J_USER", "neo4j")
            password = os.getenv("NEO4J_PASSWORD", "password")
            
            try:
                cls._driver = GraphDatabase.driver(uri, auth=(user, password))
                cls._driver.verify_connectivity()
                print(f"✅ Connected to Neo4j at {uri}")
            except Exception as e:
                print(f"❌ Failed to connect to Neo4j: {e}")
                raise e
        
        return cls._driver

    @classmethod
    def close(cls):
        if cls._driver:
            cls._driver.close()
            cls._driver = None

    @classmethod
    def execute_write(cls, query, params=None):
        """Helper to execute a write transaction."""
        driver = cls.get_driver()
        with driver.session() as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]