import os
import asyncio
import certifi
import sys
from pathlib import Path
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_google_genai import ChatGoogleGenerativeAI

os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

load_dotenv()

TAVILY_API_KEY= os.getenv('TAVILY_API_KEY')
AVIATIONSTACK_API_KEY= os.getenv('AVIATIONSTACK_API_KEY')
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
GEMINI_API_KEY= os.getenv('GEMINI_API_KEY')

# Automatically find the current project folder.
# This replaces the hard-coded Windows paths.
PROJECT_DIR = Path(__file__).resolve().parent
WEATHER_SERVER_PATH = PROJECT_DIR / "custom_weather_mcp_server.py"

# Preserve the complete Windows environment when starting
# local stdio MCP servers.
AVIATION_ENV = os.environ.copy()
AVIATION_ENV["AVIATION_STACK_API_KEY"] = (
    AVIATIONSTACK_API_KEY or ""
)

WEATHER_ENV = os.environ.copy()
WEATHER_ENV["OPENWEATHER_API_KEY"] = (
    OPENWEATHER_API_KEY or ""
)

# LLM
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    google_api_key=GEMINI_API_KEY
)

client= MultiServerMCPClient(
    {
        'tavily': {
            'transport': 'streamable_http',
            'url': f'https://mcp.tavily.com/mcp/?tavilyApiKey={TAVILY_API_KEY}'
        },

        "aviationstack": {
        "transport": "stdio",
        "command": "uvx",
        "args": [
            "--python", "3.13",
            "--with", "mcp[cli]>=1.10.1,<2",
            "aviationstack-mcp"
        ],
        "env": AVIATION_ENV
        },
        
        "weather": {
            "transport": "stdio",

            # Use the same Python environment that runs app.py.
            "command": sys.executable,

            # Automatically use custom_weather_mcp_server.py
            # from the current project directory.
            "args": [
                str(WEATHER_SERVER_PATH)
            ],

            "env": WEATHER_ENV
        }

    }
)

async def get_all_tools():
    tools= await client.get_tools()
    print('\nAvailable MCP Tools: \n')

    for tool in tools:
        print(tool.name)


# Tavily and aviation tools 
search_tool= None
aviation_tools= {}

async def initialize_mcp():
    global search_tool
    global aviation_tools

    if search_tool is not None and aviation_tools:
        return

    tools= await client.get_tools()

    print('\nAvailable MCP tools:\n')

    for tool in tools:
        print(tool.name)

    search_tool= next(
        tool 
        for tool in tools
        if tool.name=='tavily_search'
    )

    aviation_tools= {
        tool.name: tool
        for tool in tools
        if tool.name != 'tavily_search'
    }


async def tavily_mcp_search(query: str):
    await initialize_mcp()
    result= await search_tool.ainvoke(
        {
            'query': query
        }
    )
    return result

async def aviation_mcp_call(
        tool_name: str,
        tool_args: dict= None 
):
    tools= await client.get_tools()

    tool= next(
        t for t in tools
        if t.name== tool_name 
    )

    result= await tool.ainvoke(
        tool_args or {}
    )

    return result


# Weather MCP tools
weather_tool = None
forecast_tool = None


async def initialize_weather_tools():
    global weather_tool
    global forecast_tool

    if (
        weather_tool is not None
        and forecast_tool is not None
    ):
        return

    if not WEATHER_SERVER_PATH.exists():
        raise FileNotFoundError(
            "Weather MCP server file was not found: "
            f"{WEATHER_SERVER_PATH}"
        )

    # Load only Weather.
    # Tavily and AviationStack will not be started.
    tools = await client.get_tools(
        server_name="weather"
    )

    tools_by_name = {
        tool.name: tool
        for tool in tools
    }

    weather_tool = tools_by_name.get(
        "get_current_weather"
    )

    forecast_tool = tools_by_name.get(
        "get_forecast"
    )

    missing_tools = []

    if weather_tool is None:
        missing_tools.append(
            "get_current_weather"
        )

    if forecast_tool is None:
        missing_tools.append(
            "get_forecast"
        )

    if missing_tools:
        available_tools = ", ".join(
            tools_by_name.keys()
        )

        raise RuntimeError(
            "Missing Weather MCP tools: "
            f"{', '.join(missing_tools)}. "
            f"Available tools: "
            f"{available_tools or 'none'}"
        )


async def weather_mcp_search(city: str):
    await initialize_weather_tools()

    result = await weather_tool.ainvoke(
        {
            "city": city
        }
    )

    return result


async def forecast_mcp_search(city: str):
    await initialize_weather_tools()

    result = await forecast_tool.ainvoke(
        {
            "city": city
        }
    )

    return result

# Destination extractor
def extract_destination(query: str):
    prompt = f"""
    Extract only the destination city or country.

    Query:
    {query}

    Return only destination name.
    """

    response = llm.invoke(prompt)

    # Use response.text or unpack list safely
    if hasattr(response, "text") and response.text:
        return response.text.strip()
    elif isinstance(response.content, list):
        return "".join(
            part if isinstance(part, str) else part.get("text", "")
            for part in response.content
        ).strip()
    
    return str(response.content).strip()
