#!/usr/bin/env python3
"""
Amazon Product Scraper

This script scrapes Amazon.com product listings based on a search term,
extracting product names, prices, and availability status.
Results are displayed in a formatted table using the rich library.
"""

import sys
import time
import random
import urllib.parse
import logging
from typing import List, Dict, Any, Optional

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from rich.console import Console
from rich.table import Table

# Constants
BASE_URL = "https://www.amazon.com/s"
MAX_PRODUCTS = 10
REQUEST_TIMEOUT = 10  # seconds
MIN_DELAY = 1  # seconds
MAX_DELAY = 3  # seconds
MAX_NAME_LENGTH = 70  # characters for truncation

# Check for verbose flag in command-line arguments
VERBOSE_MODE = '--verbose' in sys.argv

# Configure logging based on verbose flag
logging.basicConfig(
    level=logging.INFO if VERBOSE_MODE else logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def get_random_user_agent() -> str:
    """Generate a random user agent string."""
    try:
        ua = UserAgent()
        return ua.random
    except Exception:
        # Fallback user agents in case fake_useragent fails
        fallback_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/111.0",
        ]
        return random.choice(fallback_agents)


def get_headers() -> Dict[str, str]:
    """Create headers for HTTP requests."""
    return {
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }


def build_search_url(search_term: str) -> str:
    """Build the Amazon search URL with the given search term."""
    params = {
        "k": search_term,
        "ref": "nb_sb_noss",
    }
    return f"{BASE_URL}?{urllib.parse.urlencode(params)}"


def fetch_search_results(search_term: str) -> Optional[str]:
    """
    Fetch the search results page for a given search term.
    
    Args:
        search_term: The product search term
        
    Returns:
        The HTML content of the search results page or None if the request fails
    """
    url = build_search_url(search_term)
    headers = get_headers()
    
    try:
        # Implement a random delay to avoid rate limiting
        delay = random.uniform(MIN_DELAY, MAX_DELAY)
        time.sleep(delay)
        
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()  # Raise exception for 4XX/5XX status codes
        
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching search results: {e}")
        return None


def extract_product_data(html_content: str) -> List[Dict[str, Any]]:
    """
    Extract product data from the search results HTML.
    
    Args:
        html_content: The HTML content of the search results page
        
    Returns:
        A list of dictionaries containing product data
    """
    if not html_content:
        return []
    
    products = []
    soup = BeautifulSoup(html_content, "html.parser")
    
    # Find all product items in the search results
    # Amazon's HTML structure might change, so we need to adjust selectors accordingly
    product_items = soup.select("div.s-result-item[data-component-type='s-search-result']")
    logging.info(f"Found {len(product_items)} product items on the page.")
    
    # Limit to MAX_PRODUCTS
    for i, item in enumerate(product_items[:MAX_PRODUCTS]):
        try:
            # Extract product name using multiple selectors in a fallback sequence
            name = "N/A"
            name_selectors = [
                ".a-size-medium.a-color-base.a-text-normal",  # Common title class
                ".a-link-normal .a-text-normal",              # Another common pattern
                "h2 a span",                                  # Original selector
                ".a-size-base-plus.a-color-base.a-text-normal", # Alternative title class
                "h2 .a-link-normal"                           # Direct h2 link
            ]
            
            # Extract product URL
            url = None
            url_selectors = [
                "h2 a.a-link-normal",                         # Most common product link location
                ".a-link-normal.s-underline-text",            # Text link with underline
                ".a-link-normal.s-no-outline"                 # Link with no outline
            ]
            
            for selector in name_selectors:
                name_elem = item.select_one(selector)
                if name_elem:
                    name = name_elem.text.strip()
                    logging.info(f"Product {i+1}: Found name using selector: {selector}")
                    break
            
            if name == "N/A":
                logging.warning(f"Product {i+1}: Failed to extract name with any selector")
                
            # Try to find the product URL with different selectors
            for selector in url_selectors:
                url_elem = item.select_one(selector)
                if url_elem and url_elem.has_attr('href'):
                    # Get relative URL and convert to absolute URL
                    relative_url = url_elem['href']
                    if relative_url.startswith('/'):
                        url = f"https://www.amazon.com{relative_url}"
                    else:
                        url = relative_url
                    logging.info(f"Product {i+1}: Found URL using selector: {selector}")
                    break
                    
            if not url:
                logging.warning(f"Product {i+1}: Failed to extract URL with any selector")
                url = "No URL available"
            
            # Extract price
            price_elem = item.select_one(".a-price .a-offscreen")
            price = price_elem.text.strip() if price_elem else "N/A"
            
            # Extract availability using multiple selectors
            availability = "No availability info"
            availability_selectors = [
                ".a-color-success",                              # Green "In Stock" text
                ".a-color-price",                               # Price color with availability
                ".a-color-base.a-text-bold",                    # Bold availability text
                ".a-box-inner .a-section span",                 # Delivery info in a box
                ".a-spacing-small span.a-text-bold",            # Bold shipping info
                "#availability span",                           # Direct availability span
                ".a-section.a-spacing-none.a-spacing-top-micro .a-row"  # Shipping row
            ]
            
            # Try each selector until we find availability info
            for selector in availability_selectors:
                try:
                    avail_elems = item.select(selector)
                    for avail_elem in avail_elems:
                        text = avail_elem.text.strip()
                        # Look for keywords that indicate availability information
                        keywords = ["stock", "deliver", "ship", "arrive", "available", "sold", "unavailable"]
                        if any(keyword in text.lower() for keyword in keywords) and len(text) > 3:
                            availability = text
                            logging.info(f"Product {i+1}: Found availability using selector: {selector}")
                            break
                    if availability != "No availability info":
                        break
                except Exception as e:
                    logging.debug(f"Error with availability selector {selector}: {e}")
            
            # Clean up the availability text
            if availability != "No availability info":
                # Remove extra whitespace and line breaks
                availability = " ".join(availability.split())
                # Truncate if too long
                if len(availability) > 30:
                    availability = availability[:30] + "..."
            
            if availability == "No availability info":
                logging.warning(f"Product {i+1}: Failed to extract availability with any selector")
            
            # Truncate very long names for better display
            if len(name) > MAX_NAME_LENGTH:
                truncated_name = name[:MAX_NAME_LENGTH] + "..."
            else:
                truncated_name = name
                
            products.append({
                "name": name,
                "display_name": truncated_name,
                "price": price,
                "availability": availability,
                "url": url
            })
        except Exception as e:
            print(f"Error extracting product data: {e}")
            continue
    
    return products


def display_products(products: List[Dict[str, Any]]) -> None:
    """
    Display the products in a formatted table.
    
    Args:
        products: A list of dictionaries containing product data
    """
    console = Console()
    
    if not products:
        console.print("\n[bold red]No products found![/bold red] Please try another search term.")
        return
    
    table = Table(title="Amazon Search Results")
    
    # Add columns to the table with improved formatting for product names
    table.add_column("Name", style="cyan", no_wrap=False, width=50, overflow="fold")
    table.add_column("Price", style="green", width=8)
    table.add_column("Availability", style="yellow", width=20)
    
    # Add rows to the table
    for product in products:
        table.add_row(
            product["display_name"],
            product["price"],
            product["availability"]
        )
    
    # Print the table
    console.print(table)


def show_help() -> None:
    """Display help information about the script and its options."""
    print("\nAmazon Product Scraper - Help")
    print("==============================")
    print("Description: Scrapes Amazon for product information based on a search term")
    print("\nUsage:")
    print("  python amazon_scraper.py [options]")
    print("\nOptions:")
    print("  --help     Show this help message and exit")
    print("  --verbose  Enable detailed logging output")
    print("\nExample:")
    print("  python amazon_scraper.py --verbose")
    print("  python amazon_scraper.py")


def save_product_links(products: List[Dict[str, Any]], search_term: str) -> None:
    """
    Save product links to a text file.
    
    Args:
        products: A list of dictionaries containing product data
        search_term: The search term used to find the products
    """
    try:
        with open("product_links.txt", "w", encoding="utf-8") as f:
            f.write(f"Product links for search term: {search_term}\n")
            f.write(f"Search time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for i, product in enumerate(products, 1):
                f.write(f"{i}. {product['name']}\n")
                f.write(f"   URL: {product['url']}\n")
                f.write(f"   Price: {product['price']}\n")
                f.write(f"   Availability: {product['availability']}\n\n")
                
        logging.info(f"Successfully saved {len(products)} product links to product_links.txt")
        print(f"\nProduct links saved to 'product_links.txt'")
    except Exception as e:
        logging.error(f"Failed to save product links: {e}")
        print(f"\nError saving product links: {e}")


def main() -> None:
    """Main function to run the Amazon product scraper."""
    # Check for help flag
    if '--help' in sys.argv:
        show_help()
        return
        
    console = Console()
    
    # Show verbose mode status if enabled
    if VERBOSE_MODE:
        print("Verbose logging enabled")
        
    console.print("[bold blue]===== Amazon Product Scraper =====\n[/bold blue]")
    
    try:
        # Get the search term from the user
        search_term = input("Enter product keyword to search: ").strip()
        
        if not search_term:
            console.print("[bold red]Error:[/bold red] Search term cannot be empty!")
            return
        
        console.print(f"\nSearching for [bold]{search_term}[/bold] on Amazon.com...")
        console.print("This may take a few seconds...\n")
        
        # Fetch and process the search results
        html_content = fetch_search_results(search_term)
        if not html_content:
            console.print("[bold red]Failed to fetch search results.[/bold red] Please try again later.")
            return
        
        # Extract and display the product data
        logging.info(f"Extracting product data for search term: {search_term}")
        products = extract_product_data(html_content)
        logging.info(f"Found {len(products)} products to display")
        display_products(products)
        
        # Save product links to a text file
        if products:
            save_product_links(products, search_term)
        
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Search cancelled by user.[/bold yellow]")
    except Exception as e:
        console.print(f"\n[bold red]An unexpected error occurred:[/bold red] {str(e)}")


if __name__ == "__main__":
    main()

