import requests
import json

# Add your RapidAPI key here
RAPIDAPI_KEY = "501ebf2111msh0926bab70b8fd54p1b6636jsn9da140c98a7a"

async def get_terabox_download_link(link: str):
    """Function to fetch download link using RapidAPI"""
    try:
        # Prepare the request headers and data
        headers = {
            'Content-Type': 'application/json',
            'x-rapidapi-host': 'terabox-downloader-direct-download-link-generator.p.rapidapi.com',
            'x-rapidapi-key': RAPIDAPI_KEY
        }
        
        # The request body with the Terabox URL
        data = {
            'url': link
        }

        # Make the POST request to RapidAPI
        response = requests.post(
            'https://terabox-downloader-direct-download-link-generator.p.rapidapi.com/fetch',
            headers=headers,
            data=json.dumps(data)
        )

        # Check if the request was successful
        if response.status_code == 200:
            # Parse the response JSON
            response_data = response.json()
            
            # Get the download link from the response
            download_link = response_data.get("download_link", None)
            
            if download_link:
                return download_link
            else:
                logger.error("Download link not found in API response.")
                return None
        else:
            logger.error(f"Error fetching download link: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        logger.error(f"Error during API call: {str(e)}")
        return None
