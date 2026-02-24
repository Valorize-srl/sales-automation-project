"""Test script to check Instantly API response structure."""
import asyncio
import httpx
import json
import os
from dotenv import load_dotenv

load_dotenv()

async def test_instantly():
    api_key = os.getenv("INSTANTLY_API_KEY")
    if not api_key:
        print("ERROR: INSTANTLY_API_KEY not found in environment")
        return

    url = "https://api.instantly.ai/api/v2/campaigns"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    print("Testing Instantly API...")
    print(f"URL: {url}")
    print(f"Headers: {headers}")
    print("\n" + "="*80 + "\n")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers, params={"limit": 3})

        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print("\n" + "="*80 + "\n")

        if response.status_code == 200:
            data = response.json()
            print("Response JSON structure:")
            print(json.dumps(data, indent=2))
            print("\n" + "="*80 + "\n")

            # Check what keys are present
            print("Top-level keys in response:")
            print(list(data.keys()))
            print("\n" + "="*80 + "\n")

            # Try to find campaigns
            if "data" in data:
                print(f"Found 'data' key with {len(data['data'])} items")
                if data['data']:
                    print("First campaign structure:")
                    print(json.dumps(data['data'][0], indent=2))
            elif "items" in data:
                print(f"Found 'items' key with {len(data['items'])} items")
                if data['items']:
                    print("First campaign structure:")
                    print(json.dumps(data['items'][0], indent=2))
            elif "campaigns" in data:
                print(f"Found 'campaigns' key with {len(data['campaigns'])} items")
                if data['campaigns']:
                    print("First campaign structure:")
                    print(json.dumps(data['campaigns'][0], indent=2))
            else:
                print("WARNING: No 'data', 'items', or 'campaigns' key found!")
                print("Available keys:", list(data.keys()))

            # Check pagination
            if "pagination" in data:
                print("\n" + "="*80 + "\n")
                print("Pagination info:")
                print(json.dumps(data['pagination'], indent=2))
        else:
            print(f"ERROR: {response.status_code}")
            print(response.text)

if __name__ == "__main__":
    asyncio.run(test_instantly())
