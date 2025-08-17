import argparse
import time
import re
import pandas as pd
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def scrape_data_from_html(page_content):
    """Parses the HTML of the order history page and extracts order details for August."""
    print("\n--- Starting Data Scraping ---")
    soup = BeautifulSoup(page_content, 'html.parser')

    # These selectors are educated guesses based on common web structures.
    # They might need adjustment if Blinkit's website structure is different.
    order_card_selector = "order-card-wrapper"
    date_selector = "order-date-formated"
    item_container_selector = "order-item"
    item_name_selector = "product-title"
    item_price_selector = "price"

    all_orders_data = []

    order_cards = soup.find_all('div', class_=re.compile(order_card_selector))
    print(f"Found {len(order_cards)} potential order cards on the page.")

    for card in order_cards:
        date_element = card.find('div', class_=re.compile(date_selector))
        if not date_element:
            continue

        order_date_text = date_element.get_text(strip=True)

        if "Aug" not in order_date_text:
            continue

        cleaned_date = order_date_text.replace("Ordered on ", "")

        item_containers = card.find_all('div', class_=re.compile(item_container_selector))
        if not item_containers:
            continue

        print(f"Processing an order from {cleaned_date} with {len(item_containers)} items...")
        for item in item_containers:
            name_element = item.find('p', class_=re.compile(item_name_selector))
            item_name = name_element.get_text(strip=True) if name_element else "N/A"

            price_element = item.find('span', class_=re.compile(item_price_selector))
            if price_element:
                item_price = re.sub(r'[^\d.]', '', price_element.get_text(strip=True))
            else:
                item_price = "0.00"

            all_orders_data.append({
                "Date": cleaned_date,
                "Item Name": item_name,
                "Price": float(item_price) if item_price else 0.0
            })

    return all_orders_data

def main():
    parser = argparse.ArgumentParser(description="Scrape Blinkit order data for August.")
    parser.add_argument("--phone", required=True, help="Your 10-digit phone number for Blinkit.")
    args = parser.parse_args()

    with sync_playwright() as p:
        # Final version runs in headless mode
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            print("Navigating to Blinkit...")
            page.goto("https://blinkit.com/", timeout=60000)

            # Handle location prompt if it appears
            location_input_selector = 'input[placeholder*="Search for your location"]'
            try:
                page.wait_for_selector(location_input_selector, timeout=5000)
                print("Location prompt found. Setting a default location...")
                page.fill(location_input_selector, "Gurugram")
                first_option_selector = 'div[class*="location-suggestions"]'
                page.wait_for_selector(first_option_selector, timeout=5000)
                page.locator(first_option_selector).first.click()
                print("Location set.")
            except Exception:
                print("Location prompt not found, continuing...")

            # --- Login Flow ---
            print("Starting login process...")
            # Using a more robust selector for the login button.
            # This looks for a button element specifically, which is less brittle.
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

            # --- Navigation to Order History ---
            print("Navigating to order history...")
            page.click(profile_icon_selector)
            page.locator('a:has-text("My Orders")').click()
            page.wait_for_selector('h1:has-text("My Orders")', timeout=30000)
            print("Order history page loaded.")

            # --- Scrolling to Load Data ---
            print("Scrolling to find all orders from August...")
            last_height = page.evaluate("document.body.scrollHeight")
            while True:
                page.wait_for_selector('div[class*="order-card-wrapper"]', timeout=15000)
                all_cards_text = page.locator('div[class*="order-card-wrapper"]').all_text_contents()
                if all_cards_text and re.search(r'(Jul|Jun|May)', all_cards_text[-1]):
                    print("Found orders from a previous month. Stopping scroll.")
                    break

                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2) # Wait for page to load new content

                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    print("Reached the bottom of the page.")
                    break
                last_height = new_height

            # --- Scraping and Saving ---
            page_content = page.content()
            scraped_data = scrape_data_from_html(page_content)

            if scraped_data:
                df = pd.DataFrame(scraped_data)
                output_filename = "orders.csv"
                df.to_csv(output_filename, index=False)
                print(f"\n✅ Success! Scraped {len(df)} items.")
                print(f"Data saved to '{output_filename}'")
            else:
                print("\nNo data was found for August.")

        except Exception as e:
            print(f"\n❌ An error occurred: {e}")
            page.screenshot(path="error.png")
            print("A screenshot named 'error.png' has been saved for debugging.")

        finally:
            print("Closing browser.")
            browser.close()

if __name__ == "__main__":
    main()
