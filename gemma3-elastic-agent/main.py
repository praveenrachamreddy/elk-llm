import asyncio
import os
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_community.chat_models import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
import urllib.parse

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
        self.elastic_url = self._validate_and_normalize_url(elastic_url)
        self.username = username
        self.password = password
    
    def _validate_and_normalize_url(self, url: str) -> str:
        """Validate and normalize the Elasticsearch URL."""
        if not url or url.strip() == "":
            raise ValueError("Elasticsearch URL cannot be empty")
        
        # Remove any trailing slashes
        url = url.rstrip('/')
        
        # Parse the URL to validate it
        try:
            parsed = urllib.parse.urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL format")
        except Exception as e:
            raise ValueError(f"Invalid Elasticsearch URL format: {e}")
        
        # For MCP server, we might need to use http instead of https for local/internal URLs
        # Check if this is an internal IP and adjust accordingly
        if parsed.hostname and (
            parsed.hostname.startswith('172.') or 
            parsed.hostname.startswith('192.168.') or 
            parsed.hostname.startswith('10.') or
            parsed.hostname == 'localhost'
        ):
            # Try http for internal IPs if https fails
            if parsed.scheme == 'https':
                logger.warning(f"Internal IP detected, may need to use http instead of https")
        
        return url
    
    @asynccontextmanager
    async def get_session(self):
        """Context manager that yields a ready-to-use MCP session for Elasticsearch."""
        try:
            # Build MCP server command with authentication if provided
            server_args = [
                "-y",
                "@elastic/mcp-server-elasticsearch",
                f"--elasticsearch-url={self.elastic_url}",
            ]
            
            # Add authentication if credentials are provided
            if self.username and self.password:
                server_args.extend([
                    f"--username={self.username}",
                    f"--password={self.password}"
                ])
            
            # Add additional debugging
            logger.info(f"MCP server command: npx {' '.join(server_args)}")
            
            server = StdioServerParameters(
                command="npx",
                args=server_args,
                env=os.environ.copy()  # Pass environment variables
            )
            
            logger.info(f"Connecting to Elasticsearch at {self.elastic_url}")
            async with stdio_client(server) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    logger.info("MCP session initialized successfully")
                    yield session
                    
        except Exception as e:
            logger.error(f"Failed to establish MCP session: {e}")
            
            # Try with http if https failed and it's an internal IP
            if 'https://' in self.elastic_url and any(
                self.elastic_url.startswith(f'https://{prefix}') 
                for prefix in ['172.', '192.168.', '10.', 'localhost']
            ):
                http_url = self.elastic_url.replace('https://', 'http://')
                logger.info(f"Retrying with HTTP URL: {http_url}")
                
                try:
                    server_args = [
                        "-y",
                        "@elastic/mcp-server-elasticsearch",
                        f"--elasticsearch-url={http_url}",
                    ]
                    
                    if self.username and self.password:
                        server_args.extend([
                            f"--username={self.username}",
                            f"--password={self.password}"
                        ])
                    
                    server = StdioServerParameters(
                        command="npx",
                        args=server_args,
                        env=os.environ.copy()
                    )
                    
                    async with stdio_client(server) as (read, write):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            logger.info("MCP session initialized successfully with HTTP")
                            self.elastic_url = http_url  # Update the URL for future use
                            yield session
                            return
                            
                except Exception as http_error:
                    logger.error(f"HTTP retry also failed: {http_error}")
            
            raise

class Gemma3ElasticAgent:
    """Main agent class that orchestrates Gemma3 model with Elasticsearch tools."""
    
    def __init__(self, llama_url: str, elastic_config: Dict[str, Any]):
        self.llama_url = llama_url
        self.elastic_client = ElasticsearchMCPClient(**elastic_config)
        self.llm = None
        self.agent = None
    
    def _initialize_llm(self):
        """Initialize the Gemma3 model via OpenAI-compatible API."""
        try:
            self.llm = ChatOpenAI(
                base_url=self.llama_url,
                model="gemma-3-12b-q4.gguf",  # Model name
                temperature=0.1,
                max_tokens=2048,
                timeout=30,  # Add timeout
                api_key="dummy",  # Some servers require this even if not used
            )
            
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
                
                # Log available tools
                for tool in tools:
                    logger.info(f"Available tool: {tool.name}")
                
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

async def test_elasticsearch_connection(elastic_config):
    """Test Elasticsearch connection before initializing the full agent."""
    try:
        logger.info("Testing Elasticsearch connection...")
        client = ElasticsearchMCPClient(**elastic_config)
        
        async with client.get_session() as session:
            # Try to list available tools
            tools = await load_mcp_tools(session)
            logger.info(f"✅ Elasticsearch connection successful! Found {len(tools)} tools")
            return True
            
    except Exception as e:
        logger.error(f"❌ Elasticsearch connection failed: {e}")
        return False

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
        
        # Test Elasticsearch connection first
        if not await test_elasticsearch_connection(elastic_config):
            logger.error("Cannot proceed without Elasticsearch connection")
            print("❌ Elasticsearch connection failed. Please check your configuration.")
            print(f"Current URL: {ELASTIC_URL}")
            print("Common issues:")
            print("1. Use http:// instead of https:// for internal IPs")
            print("2. Ensure Elasticsearch is running and accessible")
            print("3. Check firewall/network policies")
            print("4. Verify credentials if authentication is required")
            return
        
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
        
        # In OpenShift, you can either:
        # 1. Keep the container running for external API calls
        # 2. Run interactive mode for testing
        
        # Uncomment the line below for interactive mode
        # await run_interactive_mode(agent)
        
        # Keep pod alive for external queries
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

