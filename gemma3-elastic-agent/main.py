import asyncio
import os
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_community.chat_models import ChatLlamaCpp
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
LLAMA_CPP_URL = "https://gemma3-12b-model-praveen-datascience.apps.ocp4.imss.work/v1"
ELASTIC_URL = os.getenv("ELASTIC_URL", "http://localhost:9200")
ELASTIC_USERNAME = os.getenv("ELASTIC_USERNAME")
ELASTIC_PASSWORD = os.getenv("ELASTIC_PASSWORD")

class ElasticsearchMCPClient:
    """Enhanced Elasticsearch MCP client with authentication and error handling."""
    
    def __init__(self, elastic_url: str, username: Optional[str] = None, password: Optional[str] = None):
        self.elastic_url = elastic_url
        self.username = username
        self.password = password
    
    @asynccontextmanager
    async def get_session(self):
        """Context manager that yields a ready-to-use MCP session for Elasticsearch."""
        try:
            # Build MCP server command with authentication if provided
            server_args = [
                "-y",
                "@elastic/mcp-server-elasticsearch",
                "--elasticsearch-url", self.elastic_url,
            ]
            
            # Add authentication if credentials are provided
            if self.username and self.password:
                server_args.extend([
                    "--username", self.username,
                    "--password", self.password
                ])
            
            server = StdioServerParameters(
                command="npx",
                args=server_args,
            )
            
            logger.info(f"Connecting to Elasticsearch at {self.elastic_url}")
            async with stdio_client(server) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    logger.info("MCP session initialized successfully")
                    yield session
                    
        except Exception as e:
            logger.error(f"Failed to establish MCP session: {e}")
            raise

class Gemma3ElasticAgent:
    """Main agent class that orchestrates Gemma3 model with Elasticsearch tools."""
    
    def __init__(self, llama_url: str, elastic_config: Dict[str, Any]):
        self.llama_url = llama_url
        self.elastic_client = ElasticsearchMCPClient(**elastic_config)
        self.llm = None
        self.agent = None
    
    def _initialize_llm(self):
        """Initialize the Gemma3 model via LlamaCpp."""
        try:
            # self.llm = ChatOpenAI(
            #     base_url=self.llama_url,
            #     model="gemma-3-12b-q4.gguf",  # Model name (can be arbitrary for llama.cpp)
            #     temperature=0.1,  # Slightly higher for better reasoning
            #     max_tokens=2048,  # Reasonable token limit
            #     n_ctx=4096,  # Context window
            #     streaming=False,  # Set to True if you want streaming responses
            #     verbose=False,  # Set to True for debugging
            # )
            
            logger.info(f"LLM initialized with base URL: {self.llama_url}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            raise
    
    async def initialize_agent(self):
        """Initialize the ReAct agent with Elasticsearch tools."""
        try:
            # Initialize LLM if not already done
            if self.llm is None:
                self._initialize_llm()
            
            # Get MCP tools from Elasticsearch server
            async with self.elastic_client.get_session() as session:
                tools = await load_mcp_tools(session)
                logger.info(f"Loaded {len(tools)} MCP tools")
                
                # Create ReAct agent
                self.agent = create_react_agent(self.llm, tools)
                logger.info("ReAct agent created successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize agent: {e}")
            raise
    
    async def query(self, question: str) -> str:
        """Execute a query using the agent."""
        try:
            if self.agent is None:
                await self.initialize_agent()
            
            logger.info(f"Processing query: {question}")
            
            # Execute the query
            result = await self.agent.ainvoke({
                "messages": [HumanMessage(content=question)]
            })
            
            # Extract the response
            response = result["messages"][-1].content
            logger.info("Query executed successfully")
            return response
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise

async def run_interactive_mode(agent):
    """Run in interactive mode for OpenShift pod."""
    print("🤖 Gemma3 Elasticsearch Agent - Interactive Mode")
    print("Type 'quit' or 'exit' to stop the application")
    print("=" * 60)
    
    while True:
        try:
            # Get user input (or use default queries for demo)
            query = input("\n💬 Enter your query: ").strip()
            
            if query.lower() in ['quit', 'exit', 'stop']:
                print("👋 Goodbye!")
                break
                
            if not query:
                # Default demo queries
                demo_queries = [
                    "List all indices in the Elasticsearch cluster",
                    "What is the cluster health status?",
                    "Show me the cluster statistics"
                ]
                query = demo_queries[0]  # Use first demo query
                print(f"🔍 Running demo query: {query}")
            
            # Execute query
            response = await agent.query(query)
            print(f"\n📋 Response:\n{response}")
            print("-" * 50)
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            continue

async def main():
    """Main function for OpenShift deployment."""
    try:
        # Configuration
        elastic_config = {
            "elastic_url": ELASTIC_URL,
            "username": ELASTIC_USERNAME,
            "password": ELASTIC_PASSWORD
        }
        
        logger.info(f"Starting Gemma3 Elasticsearch Agent")
        logger.info(f"Elasticsearch URL: {ELASTIC_URL}")
        logger.info(f"Gemma3 Model URL: {LLAMA_CPP_URL}")
        
        # Initialize the agent
        agent = Gemma3ElasticAgent(LLAMA_CPP_URL, elastic_config)
        
        # For OpenShift pod - run a sample query then keep alive
        print("=" * 60)
        print("Gemma3 + Elasticsearch MCP Integration - OpenShift Pod")
        print("=" * 60)
        
        # Test connection with a simple query
        test_query = "What is the cluster health status?"
        print(f"\n🔍 Testing connection with: {test_query}")
        
        try:
            response = await agent.query(test_query)
            print(f"📋 Test Response:\n{response}")
            print("✅ Connection successful!")
        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            logger.error(f"Connection test failed: {e}")
        
        # Keep the pod alive and ready for queries
        logger.info("Agent initialized successfully. Ready to process queries.")
        
        # In OpenShift, we keep the container running
        # You can modify this to run periodic tasks or wait for external triggers
        while True:
            await asyncio.sleep(30)  # Keep pod alive
            logger.info("Agent heartbeat - ready for queries")
    
    except Exception as e:
        logger.error(f"Main execution failed: {e}")
        print(f"❌ Application failed: {e}")
        raise

if __name__ == "__main__":
    # Verify environment variables
    required_vars = ["ELASTIC_URL"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {missing_vars}")
        print("\nPlease set the following environment variables:")
        print("- ELASTIC_URL: Your Elasticsearch cluster URL")
        print("- ELASTIC_USERNAME: Your Elasticsearch username (optional)")
        print("- ELASTIC_PASSWORD: Your Elasticsearch password (optional)")
        exit(1)
    
    print("🚀 Starting Gemma3 + Elasticsearch integration...")

    asyncio.run(main())

