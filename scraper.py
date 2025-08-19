import asyncio
import re
import sys
import os
import pandas as pd
from playwright.async_api import Page, async_playwright, expect, TimeoutError
from datetime import datetime, timedelta, date

# ==============================================================================
# --- AUTHENTICATION AND PAGE SETUP FUNCTIONS ---
# ==============================================================================

async def set_location_and_login_prep(page: Page):
    """
    Handles the initial page load for a first-time run.

    This function is responsible for correctly setting the delivery location, which is
    a mandatory step to access the main features of the Blinkit website. It handles
    several potential pop-ups and uses robust locators to navigate the location
    selection workflow.

    Args:
        page (Page): The Playwright page object to interact with.
    """
    # An optional "Download App" pop-up can sometimes appear on the first visit.
    # This block safely clicks the "Continue on web" button if it exists,
    # with a short timeout to avoid delaying the script if it's not present.
    print("LOG: Checking for the 'Download App' pop-up...")
    try:
        continue_button = page.locator('button:has-text("Continue on web")')
        await continue_button.click(timeout=7000)
        print("LOG: 'Download App' pop-up found and dismissed.")
    except TimeoutError:
        print("LOG: 'Download App' pop-up did not appear. Continuing.")

    # This is the main, mandatory workflow for setting a delivery location.
    print("\nLOG: Starting the location setting process...")
    try:
        # The locator uses an exact, case-sensitive match on the placeholder text,
        # which is more precise and reliable than a partial match.
        location_input = page.locator('input[placeholder="search delivery location"]')
        await expect(location_input).to_be_visible(timeout=20000)
        print("LOG: Location input box found.")

        # Click the input to focus it, then type the desired location.
        location_query = "nirvana country"
        await location_input.click()
        print(f"LOG: Typing '{location_query}' into the location search bar...")
        await location_input.fill(location_query)

        # This locator specifically targets the container for the suggestion list,
        # making it more stable than trying to match text directly.
        all_suggestions_locator = page.locator("div.LocationSearchList__LocationListContainer-sc-93rfr7-0")

        print("LOG: Waiting for the location suggestions to appear...")
        await expect(all_suggestions_locator.first).to_be_visible(timeout=10000)

        # A hard pause is used here as a safeguard against subtle animations or
        # front-end framework state updates that might not be fully captured by
        # Playwright's auto-waiting, ensuring the element is truly ready to be clicked.
        print("LOG: Suggestions are visible. Pausing for 2 seconds before clicking...")
        await page.wait_for_timeout(2000)

        await all_suggestions_locator.first.click()
        print("LOG: Clicked on the first location suggestion.")

        # To confirm the location was set successfully, we wait for the 'Login' button
        # to become visible on the now-accessible homepage.
        print("LOG: Waiting for page to refresh and 'Login' button to appear...")
        # `get_by_text` is a robust locator that finds elements by their visible text,
        # regardless of the underlying HTML tag (e.g., <button> or <div>).
        login_button = page.get_by_text("Login", exact=True)
        await expect(login_button).to_be_visible(timeout=15000)
        print("LOG: Login button is visible. Ready for the login flow.")

    except TimeoutError as e:
        print(f"CRITICAL ERROR: A timeout occurred while setting the location. The script cannot continue. Error: {e}")
        raise

async def login_to_blinkit(page: Page):
    """
    Handles the interactive login process, including entering the phone number and OTP.

    Args:
        page (Page): The Playwright page object where the 'Login' button is visible.
    """
    try:
        print("\n--- Starting Login Process ---")
        login_button = page.get_by_text("Login", exact=True)
        await expect(login_button).to_be_visible(timeout=10000)
        await login_button.click()
        print("LOG: Login button clicked.")

        # Wait for the phone number input to be visible before prompting the user.
        mobile_input = page.locator('[data-test-id="phone-no-text-box"]')
        await expect(mobile_input).to_be_visible(timeout=10000)
        print("LOG: Mobile number pop-up is visible.")

        phone_number = input("👉 Please enter your 10-digit mobile number: ")
        if len(phone_number) != 10 or not phone_number.isdigit():
            raise ValueError("Invalid phone number. It must be 10 digits.")
        await mobile_input.fill(phone_number)
        print(f"LOG: Mobile number '{phone_number}' entered.")

        await page.locator('button:has-text("Continue")').click()
        print("LOG: Continue button clicked.")

        # Wait for the OTP screen to appear.
        await expect(page.locator('text="OTP Verification"')).to_be_visible(timeout=10000)
        print("LOG: OTP Verification pop-up is visible.")

        otp = input("👉 Please enter the 4-digit OTP you received: ")
        if len(otp) != 4 or not otp.isdigit():
            raise ValueError("Invalid OTP. It must be 4 digits.")

        # This website uses input fields that automatically advance focus after each
        # digit is typed. To handle this, we simulate individual key presses rather
        # than using a single `.fill()` command.
        first_otp_input = page.locator('[data-test-id="otp-text-box"]').first
        await first_otp_input.click() # Focus the first box
        print(f"LOG: Entering OTP '{otp}' digit by digit...")
        for digit in otp:
            await page.keyboard.press(digit)
            await page.wait_for_timeout(100) # A small delay can improve reliability.
        print("LOG: Full OTP has been entered.")

        # The most reliable indicator of a successful login is the appearance of the
        # "Account" button in the navigation bar.
        print("LOG: Waiting for final login confirmation...")
        account_button = page.get_by_text("Account", exact=True)
        await expect(account_button).to_be_visible(timeout=20000)

        print("\n✅ LOGIN SUCCESSFUL!")
        print("   The 'Account' button is visible. We are ready to start scraping!")

    except TimeoutError as e:
        print(f"\nCRITICAL ERROR: A timeout occurred during the login process. Error: {e}")
        raise
    except ValueError as e:
        print(f"\nINPUT ERROR: {e}")
        raise

# ==============================================================================
# --- DATA PARSING AND SCRAPING FUNCTIONS ---
# ==============================================================================

def parse_order_date(date_str: str) -> datetime:
    """
    Parses colloquial date/time formats from Blinkit (e.g., "Today, 4:22 pm")
    into a standard datetime object for precise filtering and sorting.

    Args:
        date_str (str): The date string scraped from the website.

    Returns:
        datetime: A standardized datetime object.
    """
    today = date.today()
    date_str_lower = date_str.lower()
    try:
        if "today" in date_str_lower:
            time_part = date_str.split(',')[1].strip()
            return datetime.strptime(f"{today.strftime('%Y-%m-%d')} {time_part}", "%Y-%m-%d %I:%M %p")
        if "yesterday" in date_str_lower:
            yesterday = today - timedelta(days=1)
            time_part = date_str.split(',')[1].strip()
            return datetime.strptime(f"{yesterday.strftime('%Y-%m-%d')} {time_part}", "%Y-%m-%d %I:%M %p")
        full_date_str = f"{date_str} {today.year}"
        return datetime.strptime(full_date_str, "%d %b, %I:%M %p %Y")
    except (ValueError, IndexError):
        return datetime(1900, 1, 1) # Return a sentinel value on failure.

def get_start_date_from_user() -> date:
    """
    Prompts the user to enter a start date in YYYY-MM-DD format and validates it,
    looping until a valid date is provided.

    Returns:
        date: The validated start date from the user.
    """
    while True:
        date_str = input("\n👉 Please enter the start date to scrape orders from (YYYY-MM-DD): ")
        try:
            start_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            print(f"✅ Great! Scraping orders on and after {start_date.strftime('%B %d, %Y')}.")
            return start_date
        except ValueError:
            print("\n❌ Invalid format. Please use the YYYY-MM-DD format. Example: 2025-08-01")

async def scrape_orders_since(page: Page, start_date: date) -> list[dict]:
    """
    The main scraping engine. Navigates to 'My Orders', scrolls through the history,
    and scrapes and cleans summary data for all orders placed on or after the `start_date`.

    Args:
        page (Page): A logged-in Playwright page object.
        start_date (date): The earliest date for orders to be included.

    Returns:
        list[dict]: A list of dictionaries, each holding cleaned data for one order.
    """
    print(f"\n--- Starting Order Scraping Process for orders since {start_date.strftime('%Y-%m-%d')} ---")

    try:
        print("LOG: Navigating to the 'My Orders' page...")
        await page.get_by_text("Account", exact=True).click()
        # Waiting for the link to have the 'active' class is a reliable way to
        # confirm that the navigation to the "My Orders" page was successful.
        active_my_orders_link = page.locator('a.profile-nav__list-item.active:has-text("My Orders")')
        await page.get_by_text("My Orders", exact=True).click()
        await expect(active_my_orders_link).to_be_visible(timeout=20000)
        print("LOG: 'My Orders' page loaded successfully.")
    except TimeoutError as e:
        print(f"CRITICAL ERROR: Could not navigate to the 'My Orders' page. Error: {e}")
        raise

    all_orders_data = []
    processed_order_ids = set() # Tracks scraped orders to prevent duplicates during scrolling.
    stop_scraping = False

    print("\nLOG: Beginning scrape and scroll loop...")
    while not stop_scraping:
        order_cards_locator = page.locator('div.tw-flex.tw-flex-col:has(div.tw-text-500)')
        try:
            await expect(order_cards_locator.first).to_be_visible(timeout=10000)
        except TimeoutError:
            print("LOG: No order cards found on the page. Ending scrape.")
            break

        for card in await order_cards_locator.all():
            try:
                # This section applies the specific business logic for data extraction.
                status_element = card.locator('div.tw-text-500').first
                status_text = await status_element.inner_text()
                status_text_lower = status_text.lower()

                # Rule: Ignore any orders that have been returned.
                if "return completed" in status_text_lower:
                    print(f"  [-] Ignoring a 'Return completed' card.")
                    continue

                # Rule: Only process cards that contain transaction details (indicated by a "•" separator).
                if await card.locator('div:has-text("•")').count() > 0:
                    details_text = await card.locator('div:has-text("•")').first.inner_text()
                    # Use regex to extract only the numbers from the amount string.
                    amount_match = re.search(r'₹([\d,]+)', details_text)
                    total_amount = int(amount_match.group(1).replace(',', '')) if amount_match else 0
                    date_str = details_text.split('•')[1].strip()
                    order_datetime = parse_order_date(date_str)
                else:
                    print(f"  [!] Skipping a card with an unknown format. Status: '{status_text}'")
                    continue

                # Create a stable ID from the cleaned data to prevent duplicate entries.
                unique_order_id = f"{date_str}-{total_amount}"
                if unique_order_id in processed_order_ids:
                    continue
                processed_order_ids.add(unique_order_id)

                # Stop the entire process if we find an order older than the user's start date.
                if order_datetime.date() < start_date:
                    print(f"\nLOG: Found an order from {order_datetime.strftime('%d %b')}, which is before the start date. Stopping scrape.")
                    stop_scraping = True
                    continue

                # Rule: Default delivery time to 0 unless the status explicitly says "Arrived in X mins".
                delivery_time_mins = 0
                if "arrived in" in status_text_lower:
                    delivery_match = re.search(r"(\d+)", status_text)
                    if delivery_match:
                        delivery_time_mins = int(delivery_match.group(1))

                print(f"  [+] Scraped Order: Date='{order_datetime.strftime('%Y-%m-%d %H:%M')}', Amount='{total_amount}', Delivery='{delivery_time_mins} mins'")
                all_orders_data.append({
                    "order_datetime": order_datetime,
                    "total_amount": total_amount,
                    "delivery_time_minutes": delivery_time_mins,
                })
            except (IndexError, TimeoutError, ValueError) as e:
                print(f"  [!] Skipping a card that could not be parsed. Error: {e}")
                continue

        if stop_scraping:
            break

        # This "smart scroll" logic is more reliable than waiting for network idle.
        # It scrolls and then waits for a new element to appear at the end of the list.
        card_count_before_scroll = await order_cards_locator.count()
        print(f"\nLOG: Scrolling down from {card_count_before_scroll} visible orders...")
        await page.mouse.wheel(0, 10000)
        try:
            await order_cards_locator.nth(card_count_before_scroll).wait_for(timeout=7000)
            print(f"LOG: Scroll successful. New order count is {await order_cards_locator.count()}.")
        except TimeoutError:
            print("\nLOG: Scrolled, but no new orders loaded. Reached the end of the history.")
            break

    return all_orders_data

# ==============================================================================
# --- DATA EXPORT AND MAIN WORKFLOW ---
# ==============================================================================

def export_to_excel(orders_data: list[dict]):
    """
    Saves the cleaned data to a formatted Excel file.

    Args:
        orders_data (list[dict]): The list of scraped order dictionaries.
    """
    if not orders_data:
        print("\nNo data was scraped to export.")
        return

    print("\n--- Processing data for Excel export ---")
    df = pd.DataFrame(orders_data)

    # Sort data chronologically with the newest orders first.
    df.sort_values(by="order_datetime", ascending=False, inplace=True)
    # Format the datetime into a more readable string for the final Excel file.
    df['order_datetime'] = df['order_datetime'].dt.strftime('%Y-%m-%d %I:%M %p')

    df.rename(columns={
        'order_datetime': 'Order Date & Time',
        'total_amount': 'Total Amount (₹)',
        'delivery_time_minutes': 'Delivery Time (Minutes)'
    }, inplace=True)

    output_filename = "blinkit_orders_cleaned.xlsx"
    try:
        df.to_excel(output_filename, index=False, engine='openpyxl')
        print(f"\n✅ Success! Data for {len(df)} orders saved to '{output_filename}'")
    except Exception as e:
        print(f"\n❌ Failed to save Excel file. Error: {e}")

async def main():
    """
    The main function that orchestrates the entire scraping workflow.

    It uses a state-driven approach to determine whether to log in or proceed
    directly to scraping, making it resilient to expired sessions.
    """
    AUTH_FILE = "auth.json"
    if '--relogin' in sys.argv:
        print("LOG: '--relogin' flag detected. Forcing a new login.")
        if os.path.exists(AUTH_FILE):
            os.remove(AUTH_FILE)
            print(f"LOG: Removed existing authentication file: '{AUTH_FILE}'")

    start_date = get_start_date_from_user()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=50)
        # Load the saved session state (cookies, local storage) if it exists.
        # This allows the script to start from a logged-in state on subsequent runs.
        context = await browser.new_context(storage_state=AUTH_FILE if os.path.exists(AUTH_FILE) else None)
        page = await context.new_page()

        try:
            print("\n--- Starting Blinkit Scraper ---")
            await page.goto("https://blinkit.com/", timeout=60000)


            print("\nLOG: Determining current login state...")
            # This state-driven logic is more resilient than just checking for a file.
            # It reacts to what is actually visible on the page.

            # STATE 1: We are already fully logged in.
            if await page.get_by_text("Account", exact=True).is_visible():
                print("LOG: State detected: Fully logged in ('Account' button is visible).")
                print("LOG: Proceeding directly to scraping.")

            # STATE 2: Logged out, but location is already set.
            elif await page.get_by_text("Login", exact=True).is_visible():
                print("LOG: State detected: Logged out, but location is set ('Login' button is visible).")
                if os.path.exists(AUTH_FILE):
                    os.remove(AUTH_FILE)
                    print(f"LOG: Removed outdated session file: '{AUTH_FILE}'")

                await login_to_blinkit(page)

                print(f"LOG: Login successful! Saving new session to '{AUTH_FILE}' for future runs...")
                await context.storage_state(path=AUTH_FILE)
                print("LOG: Session saved.")

            # STATE 3: First-time run or cookies fully cleared.
            else:
                print("LOG: State detected: No location set.")
                if os.path.exists(AUTH_FILE):
                    os.remove(AUTH_FILE)

                await set_location_and_login_prep(page)
                await login_to_blinkit(page)

                print(f"LOG: Login successful! Saving new session to '{AUTH_FILE}' for future runs...")
                await context.storage_state(path=AUTH_FILE)
                print("LOG: Session saved.")

            # By this point, the script is guaranteed to be in a logged-in state.

            all_orders_data = await scrape_orders_since(page, start_date)

            if all_orders_data:
                export_to_excel(all_orders_data)
            else:
                print(f"\n--- Scraping finished, but no orders were found on or after {start_date.strftime('%Y-%m-%d')}. ---")

        except (TimeoutError, ValueError) as e:
            print(f"\n❌ A critical error occurred: {e}")
            await page.screenshot(path="error.png")
        except Exception as e:
            print(f"\n❌ An unexpected error occurred: {e}")
            await page.screenshot(path="error.png")
        finally:
            print("\n--- Workflow Complete. Closing browser. ---")
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
