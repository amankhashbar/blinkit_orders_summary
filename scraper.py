import asyncio
import time
import re
import pandas as pd
from playwright.async_api import async_playwright, expect, TimeoutError

async def set_location_and_login_prep(page):
    """
    Handles the full initial page load and login preparation for Blinkit.
    """
    # --- Part 1: Handle the OPTIONAL "Download App" pop-up ---
    print("Checking for the 'Download App' pop-up...")
    try:
        continue_button = page.locator('button:has-text("Continue on web")')
        await continue_button.click(timeout=7000)
        print("'Download App' pop-up found and dismissed.")
    except TimeoutError:
        print("'Download App' pop-up did not appear. Continuing.")

    # --- Part 2: Handle the REQUIRED "Set Location" Workflow ---
    print("\nStarting the location setting process...")
    try:
        location_input = page.locator('input[placeholder*="Search delivery location"]')
        await expect(location_input).to_be_visible(timeout=20000)
        print("Location input box found.")

        location_query = "nirvana country"
        await location_input.click()
        print(f"Typing '{location_query}' into the location search bar...")
        await location_input.fill(location_query)

        suggestion_locator = page.locator("div:has-text('Nirvana Country'):has-text('Sector 50')")

        print("Waiting for the correct location suggestion...")
        await expect(suggestion_locator.first).to_be_visible(timeout=10000)
        await suggestion_locator.first.click()
        print("Top suggestion for 'Nirvana Country, Sector 50' was selected.")

        print("Waiting for page to refresh and 'Login' button to appear...")
        login_button = page.locator('button:has-text("Login")')
        await expect(login_button).to_be_visible(timeout=15000)
        print("Login button is visible. Ready for the login flow.")

    except TimeoutError as e:
        print(f"CRITICAL ERROR: A timeout occurred while setting the location. The script cannot continue. Error: {e}")
        raise

async def login_to_blinkit(page):
    """
    Handles the entire login flow on Blinkit, from clicking the login button
    to verifying a successful login.
    """
    try:
        # --- Step 1: Click the Login Button ---
        print("\n--- Starting Login Process ---")
        login_button = page.locator('button:has-text("Login")')
        await expect(login_button).to_be_visible(timeout=10000)
        await login_button.click()
        print("Login button clicked.")

        # --- Step 2: Enter Mobile Number ---
        mobile_input_selector = 'input[placeholder="Enter mobile number"]'
        mobile_input = page.locator(mobile_input_selector)
        await expect(mobile_input).to_be_visible(timeout=10000)
        print("Mobile number pop-up is visible.")

        phone_number = input("Please enter your 10-digit mobile number: ")
        if len(phone_number) != 10 or not phone_number.isdigit():
            raise ValueError("Invalid phone number. It must be 10 digits.")

        await mobile_input.fill(phone_number)
        print(f"Mobile number '{phone_number}' entered.")

        continue_button = page.locator('button:has-text("Continue")')
        await continue_button.click()
        print("Continue button clicked.")

        # --- Step 3: Enter OTP ---
        await expect(page.locator('text="OTP Verification"')).to_be_visible(timeout=10000)
        print("OTP Verification pop-up is visible.")

        otp = input("Please enter the 4-digit OTP you received: ")
        if len(otp) != 4 or not otp.isdigit():
            raise ValueError("Invalid OTP. It must be 4 digits.")

        first_otp_input = page.locator('input[type="tel"]').first
        await first_otp_input.fill(otp)
        print(f"OTP '{otp}' entered.")

        # --- Step 4: Verify Successful Login ---
        print("Waiting for final login confirmation...")
        account_button_selector = 'div.nav-bar-logo-container >> div[role="button"]:has-text("Account")'
        account_button = page.locator(account_button_selector)
        await expect(account_button).to_be_visible(timeout=20000)

        print("\n🎉🎉🎉 LOGIN SUCCESSFUL! 🎉🎉🎉")
        print("The 'Account' button is visible. We are ready to start scraping!")

    except TimeoutError as e:
        print(f"\nCRITICAL ERROR: A timeout occurred during the login process. The script cannot continue. Error: {e}")
        raise
    except ValueError as e:
        print(f"\nINPUT ERROR: {e}")
        raise

async def scrape_order_details_page(page):
    """
    On an order detail page, scrolls to load all items, then scrapes all
    relevant data for that single order.
    """
    print("  Scraping order detail page...")

    # Scroll down the detail page to ensure all items are loaded
    last_height = await page.evaluate("document.body.scrollHeight")
    while True:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1000) # wait for content to load
        new_height = await page.evaluate("document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    page_content = await page.content()
    soup = BeautifulSoup(page_content, 'html.parser')

    # NOTE: These selectors are guesses and will likely need refinement.
    order_id = soup.find('div', string=re.compile("Order ID")).find_next_sibling('div').get_text(strip=True)
    order_date = soup.find('div', string=re.compile("Order Time")).find_next_sibling('div').get_text(strip=True)
    total_amount = soup.find('div', string=re.compile("Total Amount")).find_next_sibling('div').get_text(strip=True)

    items = []
    item_elements = soup.find_all('div', class_=re.compile("item-details-container")) # Guessed selector
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

async def scrape_orders(page):
    """Navigates to order history and orchestrates the scraping of each order."""
    print("\n--- Navigating to Order History ---")
    account_button = page.locator('div.nav-bar-logo-container >> div[role="button"]:has-text("Account")')
    await account_button.click()

    my_orders_link = page.locator('a:has-text("My Orders")')
    await my_orders_link.click()

    await expect(page.locator('h1:has-text("My Orders")')).to_be_visible(timeout=20000)
    print("Order history page loaded.")

    print("Scrolling order list page to find all orders from August...")
    last_height = await page.evaluate("document.body.scrollHeight")
    while True:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(2000)
        new_height = await page.evaluate("document.body.scrollHeight")
        page_content = await page.content()
        if "Jul" in page_content or "Jun" in page_content or new_height == last_height:
            print("Found previous months or reached bottom of page. Stopping scroll.")
            break
        last_height = new_height

    print("Collecting links for all August orders...")
    page_content = await page.content()
    soup = BeautifulSoup(page_content, 'html.parser')
    order_cards = soup.find_all('div', class_=re.compile("order-card-wrapper"))
    detail_page_links = []
    base_url = "https://blinkit.com"
    for card in order_cards:
        if "Aug" in card.get_text():
            link_tag = card.find('a', href=re.compile("/orders/"))
            if link_tag and link_tag.has_attr('href'):
                href = link_tag['href']
                full_url = href if href.startswith('http') else base_url + href
                if full_url not in detail_page_links:
                    detail_page_links.append(full_url)

    print(f"Found {len(detail_page_links)} orders from August to scrape.")

    all_orders_data = []
    for i, link in enumerate(detail_page_links):
        print(f"Navigating to order {i+1}/{len(detail_page_links)}: {link}")
        await page.goto(link, timeout=60000)
        await expect(page.locator('div:has-text("Order ID")')).to_be_visible(timeout=15000)

        order_data = await scrape_order_details_page(page)
        all_orders_data.append(order_data)

    return all_orders_data

def export_to_excel(orders_data):
    """
    Transforms the scraped data into a wide-format DataFrame and saves it
    as an Excel file.
    """
    if not orders_data:
        print("\nNo data was scraped to export.")
        return

    print("\n--- Processing data for Excel export ---")
    processed_rows = []

    for order in orders_data:
        row = {
            'Order ID': order.get('order_id'),
            'Order Date': order.get('order_date'),
            'Total Order Amount': order.get('total_amount')
        }
        for i, item in enumerate(order.get('items', [])):
            row[f'Item {i+1}'] = item
        processed_rows.append(row)

    df = pd.DataFrame(processed_rows)

    output_filename = "orders.xlsx"
    try:
        df.to_excel(output_filename, index=False, engine='openpyxl')
        print(f"\n✅ Success! Data for {len(df)} orders saved to '{output_filename}'")
    except Exception as e:
        print(f"\n❌ Failed to save Excel file. Error: {e}")

async def main():
    """Main function to run the full scraping workflow."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=100)
        page = await browser.new_page()

        try:
            await page.goto("https://blinkit.com/", timeout=60000)

            # Step 1: Handle popups and set location
            await set_location_and_login_prep(page)

            # Step 2: Perform interactive login
            await login_to_blinkit(page)

            # Step 3: Scrape the order data
            all_orders_data = await scrape_orders(page)

            # Step 4: Export the data to Excel
            export_to_excel(all_orders_data)

        except (TimeoutError, ValueError) as e:
            print(f"\n❌ A critical error occurred: {e}")
            print("   Please check the error message and the screenshot 'error.png' for details.")
            await page.screenshot(path="error.png")

        except Exception as e:
            print(f"\n❌ An unexpected error occurred: {e}")
            await page.screenshot(path="error.png")

        finally:
            print("Closing browser.")
            await browser.close()


if __name__ == "__main__":
    # This runs the main async function
    asyncio.run(main())
