import argparse
import time
import re
import pandas as pd
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def scrape_order_details_page(page: sync_playwright.sync_api.Page):
    """
    On an order detail page, scrolls to load all items, then scrapes all
    relevant data for that single order.
    """
    print("  Scraping order detail page...")

    # Scroll down the detail page to ensure all items are loaded
    last_height = page.evaluate("document.body.scrollHeight")
    while True:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)
        new_height = page.evaluate("document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    page_content = page.content()
    soup = BeautifulSoup(page_content, 'html.parser')

    # --- Scrape data from the detail page ---
    # NOTE: These selectors are guesses and will likely need refinement.
    order_id = soup.find('div', class_=re.compile("order-id")).get_text(strip=True).replace("Order ID: ", "")
    order_date = soup.find('div', class_=re.compile("order-date")).get_text(strip=True)
    total_amount = soup.find('div', class_=re.compile("total-amount")).get_text(strip=True)

    items = []
    item_elements = soup.find_all('div', class_=re.compile("item-row"))
    for item_el in item_elements:
        name = item_el.find('p', class_=re.compile("item-name")).get_text(strip=True)
        price = item_el.find('span', class_=re.compile("item-price")).get_text(strip=True)
        items.append(f"{name} ({price})")

    print(f"    Found {len(items)} items for Order ID {order_id}")

    return {
        "order_id": order_id,
        "order_date": order_date,
        "total_amount": total_amount,
        "items": items
    }

def export_to_excel(orders_data):
    """
    Transforms the scraped data into a wide-format DataFrame and saves it
    as an Excel file.
    """
    if not orders_data:
        print("No data to export.")
        return

    print("Processing data for Excel export...")
    processed_rows = []

    for order in orders_data:
        row = {
            'Order ID': order.get('order_id'),
            'Order Date': order.get('order_date'),
            'Total Order Amount': order.get('total_amount')
        }
        # Add item columns dynamically
        for i, item in enumerate(order.get('items', [])):
            row[f'Item {i+1}'] = item
        processed_rows.append(row)

    # Create DataFrame from the list of processed rows
    df = pd.DataFrame(processed_rows)

    # Save to Excel
    output_filename = "orders.xlsx"
    try:
        df.to_excel(output_filename, index=False, engine='openpyxl')
        print(f"\n✅ Success! Data for {len(df)} orders saved to '{output_filename}'")
    except Exception as e:
        print(f"\n❌ Failed to save Excel file. Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Scrape Blinkit order data for August.")
    parser.add_argument("--phone", required=True, help="Your 10-digit phone number for Blinkit.")
    args = parser.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=50)
        page = browser.new_page()

        try:
            # ... (Location and Login logic remains the same) ...
            print("Navigating to Blinkit...")
            page.goto("https://blinkit.com/", timeout=60000)

            print("Looking for the location search pop-up...")
            location_input_selector = 'input[placeholder*="Search for your location"]'
            try:
                page.wait_for_selector(location_input_selector, timeout=20000)
                location_query = "nirvana country sector 50"
                print(f"Location prompt found. Typing: '{location_query}'")
                page.fill(location_input_selector, location_query)
                time.sleep(2)
                suggestion_selector = 'div[role="button"]:has-text("Nirvana Country")'
                print(f"Looking for suggestion with selector: {suggestion_selector}")
                page.wait_for_selector(suggestion_selector, timeout=10000)
                page.locator(suggestion_selector).first.click()
                print("Location selected.")
                print("Waiting for main page to load after setting location...")
                page.wait_for_load_state("networkidle", timeout=15000)
                print("Main page loaded.")
            except Exception as e:
                print(f"Critical error: Could not handle the location prompt. The script cannot continue. Error: {e}")
                raise

            print("Starting login process...")
            login_button_selector = 'button:has-text("Login")'
            page.wait_for_selector(login_button_selector, timeout=30000)
            page.locator(login_button_selector).click()

            phone_input_selector = 'input[type="tel"]'
            page.wait_for_selector(phone_input_selector, timeout=15000)
            page.fill(phone_input_selector, args.phone)
            page.locator('button:has-text("Continue")').click()

            page.wait_for_selector('div:has-text("Enter OTP")', timeout=15000)
            otp = input("Please enter the 4-digit OTP you received: ")
            if len(otp) != 4 or not otp.isdigit():
                raise ValueError("Invalid OTP. It must be 4 digits.")
            page.locator('input[type="tel"]').nth(1).fill(otp)

            profile_icon_selector = 'div[data-test-id="user-profile"]'
            page.wait_for_selector(profile_icon_selector, timeout=30000)
            print("Login successful!")

            try:
                skip_button_selector = 'button:is(:text-is("Not Now"), :text-is("Skip for now"))'
                print("Checking for 'Open in App' popup...")
                page.wait_for_selector(skip_button_selector, timeout=5000)
                page.click(skip_button_selector)
                print("'Open in App' popup was found and skipped.")
            except Exception:
                print("'Open in App' popup not found, continuing...")

            print("Navigating to order history...")
            page.click(profile_icon_selector)
            page.locator('a:has-text("My Orders")').click()
            page.wait_for_selector('h1:has-text("My Orders")', timeout=30000)
            print("Order history page loaded.")

            # --- Scroll Order List Page to Load All August Orders ---
            print("Scrolling order list page to find all orders from August...")
            last_height = page.evaluate("document.body.scrollHeight")
            while True:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)
                new_height = page.evaluate("document.body.scrollHeight")
                page_content = page.content()
                if "Jul" in page_content or "Jun" in page_content or new_height == last_height:
                    print("Found previous months or reached bottom of page. Stopping scroll.")
                    break
                last_height = new_height

            # --- Get Links for All August Orders ---
            print("Collecting links for all August orders...")
            page_content = page.content()
            soup = BeautifulSoup(page_content, 'html.parser')
            order_cards = soup.find_all('div', class_=re.compile("order-card-wrapper"))
            detail_page_links = []
            base_url = "https://blinkit.com"
            for card in order_cards:
                if "Aug" in card.get_text():
                    # NOTE: This selector for the link is a guess.
                    link_tag = card.find('a', href=re.compile("/orders/"))
                    if link_tag and link_tag.has_attr('href'):
                        href = link_tag['href']
                        full_url = href if href.startswith('http') else base_url + href
                        detail_page_links.append(full_url)

            print(f"Found {len(detail_page_links)} orders from August to scrape.")

            # --- Loop Through Detail Pages and Scrape Data ---
            all_orders_data = []
            for i, link in enumerate(detail_page_links):
                print(f"Navigating to order {i+1}/{len(detail_page_links)}: {link}")
                page.goto(link, timeout=60000)
                # Wait for a unique element on the detail page before scraping
                page.wait_for_selector('div:has-text("Order ID")', timeout=15000)

                order_data = scrape_order_details_page(page)
                all_orders_data.append(order_data)

            # --- Process and Save Data to Excel ---
            export_to_excel(all_orders_data)

        except Exception as e:
            print(f"\n❌ An error occurred: {e}")
            page.screenshot(path="error.png")
            print("A screenshot named 'error.png' has been saved for debugging.")

        finally:
            print("Closing browser.")
            browser.close()

if __name__ == "__main__":
    main()
