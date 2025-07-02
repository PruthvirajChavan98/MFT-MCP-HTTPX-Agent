import asyncio
from fastmcp import Client
from fastmcp.client.transports import SSETransport

async def test_hero_fincorp_api():
    # Create transport with custom headers
    transport = SSETransport(
        "http://0.0.0.0:8050/sse",
        headers={
            "X-Session-ID": "3"
        }
    )
    
    client = Client(transport)

    async with client:
        tools_to_test = [
            "generate_otp",
            "validate_otp",
            # "get_dashboard_data",
            # "get_loan_details", 
            # "get_overdue_details",
            # "get_repayment_schedule",
            # "get_foreclosure_details",
            # "download_noc_letter"
        ]

        for tool_name in tools_to_test:
            try:
                result = await client.call_tool(tool_name, {})
                print(f"{tool_name} result: {result[0].text}")
            except Exception as e:
                print(f"Error calling {tool_name}: {e}")

if __name__ == "__main__":
    asyncio.run(test_hero_fincorp_api())