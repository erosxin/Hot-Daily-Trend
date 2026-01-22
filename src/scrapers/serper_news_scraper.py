import os
import requests
import json
import time
import logging
from src.config import SERPER_API_KEY
from src.utils import setup_logger

# 初始化 logger
logger = setup_logger("serper_scraper")

class SerperNewsScraper:
    def __init__(self):
        if not SERPER_API_KEY:
            raise ValueError("SERPER_API_KEY is not set in environment variables.")
        self.api_key = SERPER_API_KEY
        self.base_url = "https://google.serper.dev/search"
        logger.info("SerperNewsScraper initialized.")

    def search(self, query: str, num: int = 10, max_retries: int = 3) -> list[dict]:
        headers = {
            "X-API-KEY": self.api_key,
            # requests 库在使用 json= 参数时会自动设置 Content-Type，所以这里不再手动设置，避免冲突
        }
        payload = {
            "q": query,
            "num": num,
            "tbm": "nws"  # tbm: type by market, 'nws' for news
        }

        for attempt in range(1, max_retries + 1):
            logger.info(f"Searching news for query: '{query}' (attempt {attempt}/{max_retries})")
            try:
                # 使用 json= 参数让 requests 自动处理 JSON 序列化和 Content-Type
                response = requests.post(self.base_url, headers=headers, json=payload, timeout=10)
                response.raise_for_status()  # 检查并对 4xx/5xx 响应抛出 HTTPError

                data = response.json()
                logger.info(f"Serper API response data: {data}")
                if "organic" in data:
                    logger.info(f"Successfully fetched news for query: '{query}'")
                    return data["organic"]
                logger.warning(f"No 'organic' key found in Serper API response for query: '{query}'")
                return []

            except requests.exceptions.HTTPError as http_err:
                logger.error(f"HTTP error occurred: {http_err}. Status code: {response.status_code}, Response: {response.text}")
                if response.status_code == 429:  # Too Many Requests
                    if attempt < max_retries:
                        wait_time = 2 ** (attempt - 1)  # Exponential backoff
                        logger.warning(f"Rate limit hit, retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error("Rate limit hit, max retries reached.")
                        return []
                elif response.status_code in [400, 401, 403, 404, 405]:
                    # Bad Request, Unauthorized, Forbidden, Not Found, Method Not Allowed
                    logger.error(f"Client error ({response.status_code}), no further retries.")
                    return []
                else:
                    if attempt < max_retries:
                        wait_time = 2 ** (attempt - 1)
                        logger.warning(f"Server error ({response.status_code}), retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Server error ({response.status_code}), max retries reached.")
                        return []
            except requests.exceptions.Timeout:
                logger.error("Request timed out.")
                if attempt < max_retries:
                    wait_time = 2 ** (attempt - 1)
                    logger.warning(f"Timeout, retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error("Timeout, max retries reached.")
                    return []
            except requests.exceptions.RequestException as req_err:
                logger.error(f"An unexpected request error occurred: {req_err}")
                return []
            except json.JSONDecodeError as json_err:
                logger.error(f"JSON decode error: {json_err}, Response text: {response.text}")
                return []
        
        logger.warning(f"Failed to fetch news for query: '{query}' after {max_retries} attempts.")
        return []

if __name__ == "__main__":
    try:
        scraper = SerperNewsScraper()
        news_items = scraper.search("科技新闻")
        if news_items:
            print("\n--- Fetched News Items (First 3) ---")
            for i, item in enumerate(news_items[:3]):
                print(f"Title: {item.get('title')}")
                print(f"Link: {item.get('link')}")
                print(f"Snippet: {item.get('snippet')[:100]}...")
                print("-" * 20)
            if len(news_items) > 3:
                print(f"...and {len(news_items) - 3} more.")
        else:
            print("No news items found or request failed.")
    except ValueError as e:
        print(f"Configuration Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
