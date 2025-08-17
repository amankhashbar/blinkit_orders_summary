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

async def scrape_august_orders(page):
    """
    Navigates to the 'My Orders' page, scrolls through the history, and scrapes
    the summary data for all orders placed in August using specific element locators.
    """
    print("\n--- Starting Order Scraping Process ---")

    # --- Step 1: Navigate to 'My Orders' page ---
    try:
        print("Clicking on the 'Account' button...")
        account_button_selector = 'div.nav-bar-logo-container >> div[role="button"]:has-text("Account")'
        await page.locator(account_button_selector).click()

        print("Clicking on 'My Orders' from the dropdown...")
        my_orders_link = page.locator('a:has-text("My Orders")')
        await my_orders_link.click()

        print("Waiting for the 'My Orders' page to load...")
        # This looks for a div that acts like a button AND contains the right-arrow icon.
        order_card_selector = "div[role='button']:has(span.icon-right-arrow)"
        await expect(page.locator(order_card_selector).first).to_be_visible(timeout=20000)
        print("'My Orders' page loaded successfully.")

    except TimeoutError as e:
        print(f"CRITICAL ERROR: Could not navigate to the 'My Orders' page. Error: {e}")
        raise

    # --- Step 2: Scroll and Scrape August Orders ---
    all_orders_data = []
    # Use the full text of an order card as a unique identifier to avoid duplicates
    processed_orders = set()
    stop_scraping = False

    print("\nStarting to scroll and scrape orders using specific locators...")
    while not stop_scraping:
        # Find all currently visible order cards based on the provided structure
        order_cards = await page.locator(order_card_selector).all()

        if not order_cards:
            print("No more order cards found on the page.")
            break

        new_orders_found = False
        for card in order_cards:
            # Use a combination of elements to create a unique key for the order
            try:
                # Target the div containing amount and date
                details_container = card.locator("div.tw-flex.tw-gap-1")
                unique_card_key = await details_container.inner_text()
            except TimeoutError:
                # If the card doesn't have the expected structure, skip it
                continue

            if unique_card_key in processed_orders:
                continue  # Skip if we've already processed this exact card

            new_orders_found = True
            processed_orders.add(unique_card_key)

            # Locate the specific element for the date
            date_element = card.locator("div.tw-flex.tw-gap-1 > div:nth-child(3)")
            order_date_str = await date_element.inner_text()

            if "Aug" in order_date_str:
                # It's an August order, so extract all details

                # Extract Delivery Time
                delivery_element = card.locator("div.tw-text-500.tw-font-extrabold")
                delivery_text = await delivery_element.inner_text()
                delivery_match = re.search(r"(\d+)", delivery_text)
                delivery_time = delivery_match.group(1) if delivery_match else "N/A"

                # Extract Total Amount
                amount_element = card.locator("div.tw-flex.tw-gap-1 > div:nth-child(1)")
                total_amount = await amount_element.inner_text()

                print(f"  [+] Scraped August Order: Date='{order_date_str}', Amount='{total_amount}', Delivery='{delivery_time} mins'")

                all_orders_data.append({
                    "order_date_time": order_date_str,
                    "total_amount": total_amount,
                    "delivery_time_minutes": delivery_time,
                })
            else:
                # If we encounter a non-August month, we can stop
                print(f"\nFound an order from a different month ('{order_date_str}'). Stopping the scraping process.")
                stop_scraping = True
                break

        if stop_scraping:
            break

        if not new_orders_found and len(order_cards) > 0:
            print("\nScrolled to the end of the order history. No new orders loaded.")
            break

        # Scroll down to load more orders
        print("Scrolling down for more orders...")
        await page.mouse.wheel(0, 10000)
        # Give the page a moment to load new content
        await page.wait_for_timeout(3000)

    return all_orders_data

def export_to_excel(orders_data):
    """
    Saves the scraped summary data to an Excel file.
    """
    if not orders_data:
        print("\nNo data was scraped to export.")
        return

    print("\n--- Processing data for Excel export ---")

    # The data is already in the correct format for a DataFrame
    df = pd.DataFrame(orders_data)

    # Rename columns for clarity in the final output
    df.rename(columns={
        'order_date_time': 'Order Date & Time',
        'total_amount': 'Total Amount',
        'delivery_time_minutes': 'Delivery Time (Minutes)'
    }, inplace=True)

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
            all_orders_data = await scrape_august_orders(page)

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
