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

        # A hard wait is added here to ensure the page has time to reload after location selection.
        # This prevents a race condition where the script looks for the Login button too quickly.
        await page.wait_for_timeout(2000)

        login_button = page.get_by_text("Login", exact=True)
        await expect(login_button).to_be_visible(timeout=15000)
        print("LOG: Login button is visible. Ready for the login flow.")

    except TimeoutError as e:
        print(f"CRITICAL ERROR: A timeout occurred while setting the location. The script cannot continue. Error: {e}")
        raise

async def login_to_blinkit(page: Page):
    """
    Handles the interactive login process, including entering the phone number and OTP,
    with a retry mechanism for resending the OTP.
    """
    try:
        print("\n--- Starting Login Process ---")
        login_button = page.get_by_text("Login", exact=True)
        await expect(login_button).to_be_visible(timeout=10000)
        await login_button.click()
        print("LOG: Login button clicked.")

        # A deliberate pause prevents a race condition by waiting for the phone number
        # modal to finish animating and become interactive before proceeding.
        print("LOG: Pausing for 1.5s to allow login modal to render...")
        await page.wait_for_timeout(1500)

        # Now, it is safe to look for the mobile input field.
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

        # Another pause waits for the UI to transition from the phone number screen to the OTP screen.
        print("LOG: Pausing for 1.5s to allow OTP modal to render...")
        await page.wait_for_timeout(1500)

        # The OTP entry is wrapped in a loop to allow for multiple attempts,
        # making the script resilient to delayed SMS messages or user typos.
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            print(f"\n--- OTP Attempt {attempt}/{max_attempts} ---")
            await expect(page.locator('text="OTP Verification"')).to_be_visible(timeout=10000)
            print("LOG: OTP Verification pop-up is visible.")

            otp = input("👉 Please enter the 4-digit OTP you received: ")
            if len(otp) != 4 or not otp.isdigit():
                print("❌ Invalid OTP format. The attempt will likely fail.")

            first_otp_input = page.locator('[data-test-id="otp-text-box"]').first
            await first_otp_input.click()

            # On retries, the input field must be cleared of the previous incorrect OTP.
            if attempt > 1:
                select_all = "Meta+A" if sys.platform == "darwin" else "Control+A"
                await page.keyboard.press(select_all)
                await page.keyboard.press("Backspace")

            # Simulate typing each digit individually to work with auto-advancing input fields.
            print(f"LOG: Entering OTP '{otp}' digit by digit...")
            for digit in otp:
                await page.keyboard.press(digit)
                await page.wait_for_timeout(100)
            print("LOG: Full OTP has been entered.")

            try:
                print("LOG: Waiting for final login confirmation...")
                account_button = page.get_by_text("Account", exact=True)
                # Increased timeout for slow logins, giving the backend more time to process the OTP.
                await expect(account_button).to_be_visible(timeout=20000)

                print("\n✅ LOGIN SUCCESSFUL!")
                print("   The 'Account' button is visible. We are ready to start scraping!")
                return # Exit the function on successful login.

            except TimeoutError:
                print("\nLOG: Login did not complete successfully. OTP may be incorrect or expired.")
                if attempt < max_attempts:
                    try:
                        # If login fails, check if the "Resend Code" button is available.
                        resend_button = page.get_by_text("Resend Code", exact=True)
                        await expect(resend_button).to_be_visible(timeout=5000)
                        user_choice = input("👉 Would you like to resend the OTP? (y/n): ").lower()
                        if user_choice == 'y':
                            await resend_button.click()
                            print("LOG: 'Resend Code' clicked. A new OTP will be sent.")
                            # Add a small pause after clicking resend to allow UI to update.
                            await page.wait_for_timeout(1000)
                            continue # Continue to the next iteration of the loop.
                        else:
                            raise Exception("User aborted the login process.")
                    except TimeoutError:
                        raise Exception("Login failed and the 'Resend Code' button was not found. Cannot proceed.")
                else:
                    print("\n❌ Maximum OTP attempts reached.")

        raise Exception("Failed to log in after multiple OTP attempts.")

    except TimeoutError as e:
        print(f"\nCRITICAL ERROR: A timeout occurred during the login process. Error: {e}")
        raise
    except ValueError as e:
        print(f"\nINPUT ERROR: {e}")
        raise
    except Exception as e:
        print(f"\n❌ An error occurred during login: {e}")
        raise

# ==============================================================================
# --- DATA PARSING AND SCRAPING FUNCTIONS ---
# ==============================================================================

def parse_order_date(date_str: str, previous_date: datetime = None) -> datetime:
    """
    Parses colloquial date/time formats from Blinkit into a standard datetime object.

    It intelligently handles year rollovers. If it parses a date that appears
    to be *newer* than the previously scraped date (e.g., parsing "Jan 2025" after
    "Dec 2024"), it correctly assumes the year has decremented.

    Args:
        date_str (str): The date string scraped from the website.
        previous_date (datetime, optional): The datetime of the previously parsed order.

    Returns:
        datetime: A standardized datetime object.
    """
    today = date.today()
    date_str_lower = date_str.lower()
    parsed_date = None
    try:
        if "today" in date_str_lower:
            time_part = date_str.split(',')[1].strip()
            parsed_date = datetime.strptime(f"{today.strftime('%Y-%m-%d')} {time_part}", "%Y-%m-%d %I:%M %p")
        elif "yesterday" in date_str_lower:
            yesterday = today - timedelta(days=1)
            time_part = date_str.split(',')[1].strip()
            parsed_date = datetime.strptime(f"{yesterday.strftime('%Y-%m-%d')} {time_part}", "%Y-%m-%d %I:%M %p")
        else:
            # Assume the current year initially for dates like "15 Aug, 10:30 PM".
            full_date_str = f"{date_str} {today.year}"
            parsed_date = datetime.strptime(full_date_str, "%d %b, %I:%M %p %Y")

        # If a previous date is known and the new date is newer, it means we've
        # crossed a year boundary (e.g., from Jan '25 to Dec '24). Decrement the year.
        if previous_date and parsed_date > previous_date:
            parsed_date = parsed_date.replace(year=parsed_date.year - 1)

        return parsed_date
    except (ValueError, IndexError):
        return datetime(1900, 1, 1) # Return a sentinel value on failure.

def get_start_date_from_user() -> date:
    """
    Prompts the user to enter a start date in YYYY-MM-DD format and validates it.

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

async def scrape_order_details(page: Page) -> dict:
    """
    Scrapes detailed information from a single order's page using a top-to-bottom strategy.

    Args:
        page (Page): The Playwright page object on an order details view.

    Returns:
        dict: A dictionary containing scraped details for one order.
    """
    details = {"summary": {}, "items": []}
    print("      LOG: Now on details page. Waiting for the page to become interactive...")
    await page.wait_for_load_state('networkidle', timeout=20000)
    print("      LOG: Network is idle. Beginning top-to-bottom scrape.")

    # --- PHASE A: Scrape the Top of the Page (Order Summary) ---
    summary_data = details["summary"]
    try:
        print("      LOG: Scraping header details...")
        await expect(page.get_by_text("Order summary", exact=True)).to_be_visible(timeout=15000)

        # Use regex to match both "item" and "items" for robustness.
        item_count_locator = page.locator("div.tw-text-400.tw-font-bold", has_text=re.compile(r'item(s)? in this order'))
        await expect(item_count_locator).to_be_visible(timeout=5000)
        summary_data['total_item_count'] = await item_count_locator.inner_text()
        summary_data['arrival_status'] = await page.locator("div:has-text('Order summary') + div").first.inner_text()
        summary_data['invoice_download_link'] = 'Yes' if await page.locator("button:has-text('Download Invoice')").count() > 0 else 'No'
        print("      LOG: Successfully scraped header details.")
    except Exception as e:
        print(f"      [!] Warning: Could not parse order summary section. Error: {e}")

    # --- PHASE B: Iteratively Scroll to Scrape All Items ---
    print("      LOG: Beginning iterative scroll to scrape all items...")
    processed_item_texts = set()
    while True:
        visible_items = await page.locator("div.tw-flex-row:has(img):has(div.tw-text-300.tw-font-medium)").all()
        new_items_found = False
        for item_element in visible_items:
            item_id = await item_element.inner_text()
            if item_id in processed_item_texts:
                continue
            new_items_found = True
            processed_item_texts.add(item_id)
            try:
                name = await item_element.locator("div.tw-text-300.tw-font-medium").first.inner_text()
                quantity = await item_element.locator("div.tw-text-200.tw-font-regular").first.inner_text()
                price_text = await item_element.locator("div.tw-text-200.tw-font-bold").first.inner_text()
                details["items"].append({
                    "product_name": name, "quantity": quantity, "price": int(re.sub(r'[^\d]', '', price_text))
                })
            except (TimeoutError, ValueError):
                continue
        if not new_items_found:
            print("      LOG: No new items found on scroll. Item list is complete.")
            break
        print(f"      LOG: Scraped {len(details['items'])} items so far. Scrolling down...")
        await page.keyboard.press("PageDown")
        await page.wait_for_timeout(1500)
    print(f"      LOG: Finished scraping all {len(details['items'])} items.")

    # --- PHASE C: Scrape the Bottom of the Page (Bill Details) ---
    print("      LOG: Scrolling to bottom to find order details...")
    await page.keyboard.press("End")
    await page.wait_for_timeout(1500)

    bill_data = details["summary"]
    try:
        order_id_locator = page.locator("button:has-text('ORD')")
        await expect(order_id_locator).to_be_visible(timeout=10000)
        bill_data['order_id'] = (await order_id_locator.inner_text()).strip()
        print(f"      LOG: Scraped Order ID: {bill_data['order_id']}")

        async def get_bill_value(label: str) -> str:
            try:
                container = page.locator(f"div.tw-flex.tw-w-full.tw-flex-row:has(div:text-is('{label}'))")
                await container.wait_for(state="visible", timeout=3000)
                return await container.locator("div").last.inner_text()
            except TimeoutError:
                return "0"
        bill_data['mrp'] = await get_bill_value('MRP')
        bill_data['product_discount'] = await get_bill_value('Product discount')
        bill_data['item_total'] = await get_bill_value('Item total')
        bill_data['handling_charge'] = await get_bill_value('Handling charge')
        bill_data['delivery_charges'] = await get_bill_value('Delivery charges')
        bill_data['bill_total'] = await get_bill_value('Bill total')
        print("      LOG: Bill details scraped successfully.")
    except Exception as e:
        print(f"      [!] Warning: Could not parse bill details section. Error: {e}")
    return details

async def _scrape_all_summaries(page: Page, start_date: date) -> list[dict]:
    """
    PHASE 1: Scrolls through the 'My Orders' list and scrapes summary data for all
    eligible orders, returning a list of dictionaries to be processed in Phase 2.
    """
    print("\n--- PHASE 1: Collecting all order summaries ---")
    summaries_to_process = []
    processed_unique_ids = set()
    stop_scraping = False
    last_known_date = None

    while not stop_scraping:
        order_cards_locator = page.locator('div.tw-flex.tw-flex-col:has(span.icon-right-arrow)')
        try:
            await expect(order_cards_locator.first).to_be_visible(timeout=10000)
        except TimeoutError:
            print("LOG: No order cards found on the page. Ending summary collection.")
            break
        for card in await order_cards_locator.all():
            try:
                details_locator = card.locator('div:has-text("•")')
                if await details_locator.count() == 0: continue
                details_text = await details_locator.first.inner_text()
                amount_match = re.search(r'₹([\d,]+)', details_text)
                total_amount_str = amount_match.group(1) if amount_match else "0"
                total_amount = int(total_amount_str.replace(',', ''))
                date_str = details_text.split('•')[1].strip()
                unique_key = f"{date_str}-{total_amount}"
                if unique_key in processed_unique_ids: continue
                processed_unique_ids.add(unique_key)
                order_datetime = parse_order_date(date_str, previous_date=last_known_date)
                last_known_date = order_datetime
                if order_datetime.date() < start_date:
                    print(f"\nLOG: Found an order from {order_datetime.strftime('%d %b, %Y')}, which is before the start date. Stopping.")
                    stop_scraping = True
                    break
                status_text = await card.locator('div.tw-text-500').first.inner_text()
                delivery_time_mins = 0
                if "arrived in" in status_text.lower():
                    delivery_match = re.search(r"(\d+)", status_text)
                    if delivery_match: delivery_time_mins = int(delivery_match.group(1))
                summaries_to_process.append({
                    "order_datetime": order_datetime, "bill_total_from_list": total_amount,
                    "delivery_time_minutes": delivery_time_mins, "unique_amount_str": f"₹{total_amount_str}",
                    "unique_date_str": date_str,
                })
            except Exception as e:
                print(f"  [!] Warning: Could not parse a summary card. Error: {e}")
                continue
        if stop_scraping: break
        card_count_before_scroll = await order_cards_locator.count()
        print(f"LOG: Scrolling down from {card_count_before_scroll} visible summaries...")
        await page.mouse.wheel(0, 10000)
        try:
            await order_cards_locator.nth(card_count_before_scroll).wait_for(timeout=7000)
        except TimeoutError:
            print("\nLOG: Scrolled, but no new summaries loaded. Reached the end of the history.")
            break
    return summaries_to_process

async def scrape_orders_since(page: Page, start_date: date) -> tuple[list[dict], list[dict]]:
    """
    Orchestrates the two-phase scraping process:
    1. Scrape all order summaries from the main list.
    2. Navigate to each order's detail page to scrape full data.
    """
    my_orders_url = "https://blinkit.com/account/orders"
    print(f"\n--- Navigating to 'My Orders' page at {my_orders_url} ---")
    await page.goto(my_orders_url)
    active_my_orders_link = page.locator('a.profile-nav__list-item.active:has-text("My Orders")')
    await expect(active_my_orders_link).to_be_visible(timeout=20000)
    print("LOG: 'My Orders' page loaded successfully.")
    orders_to_process = await _scrape_all_summaries(page, start_date)
    if not orders_to_process: return [], []

    print("\n--- PHASE 1 COMPLETE: The following orders will be processed ---")
    for order in orders_to_process:
        print(f"  - Timestamp: {order['order_datetime']}, Amount: ₹{order['bill_total_from_list']}")
    print("--------------------------------------------------------------------")
    print("\n--- PHASE 2: Processing each order for detailed information ---")
    all_final_summaries, all_final_items = [], []
    for index, summary_data in enumerate(orders_to_process):
        order_dt = summary_data['order_datetime']
        print(f"\n[+] Processing Order {index + 1}/{len(orders_to_process)}: Date='{order_dt.strftime('%Y-%m-%d %H:%M')}'")
        try:
            if not page.url == my_orders_url:
                await page.goto(my_orders_url)
                await expect(active_my_orders_link).to_be_visible(timeout=20000)
            amount_str, date_str = summary_data['unique_amount_str'], summary_data['unique_date_str']
            print(f"  LOG: Searching for an order card containing BOTH '{amount_str}' AND '{date_str}'...")
            order_card = page.locator('div.tw-flex.tw-flex-col').filter(has_text=re.compile(re.escape(amount_str))).filter(has_text=re.compile(re.escape(date_str))).first
            scroll_attempts, last_height = 0, await page.evaluate("document.body.scrollHeight")
            while not await order_card.is_visible() and scroll_attempts < 15:
                print(f"  LOG: Order not visible yet. Scrolling down (Attempt {scroll_attempts + 1})...")
                await page.keyboard.press("End")
                await page.wait_for_timeout(2500)
                new_height = await page.evaluate("document.body.scrollHeight")
                if new_height == last_height: break
                last_height = new_height
                scroll_attempts += 1
            if not await order_card.is_visible(): raise Exception(f"Could not find the order card after scrolling.")
            print("  LOG: Found unique order card. Clicking it now...")
            await order_card.locator('div.tw-flex-row:has(span.icon-right-arrow)').first.click()
            intermediate_page_locator = page.get_by_text("View Order Details", exact=True)
            final_page_locator = page.get_by_text("Bill details", exact=True)
            await expect(intermediate_page_locator.or_(final_page_locator)).to_be_visible(timeout=20000)
            if await intermediate_page_locator.is_visible():
                await intermediate_page_locator.click()
                await expect(final_page_locator).to_be_visible(timeout=15000)
            detailed_data = await scrape_order_details(page)
            final_summary = {**summary_data, **detailed_data["summary"]}
            if final_summary.get('delivery_time_minutes') == 0 and 'arrival_status' in final_summary:
                try:
                    arrival_time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:am|pm))', final_summary['arrival_status'], re.IGNORECASE)
                    if arrival_time_match:
                        arrival_datetime = datetime.strptime(f"{summary_data['order_datetime'].date()} {arrival_time_match.group(1)}", "%Y-%m-%d %I:%M %p")
                        if arrival_datetime < summary_data['order_datetime']: arrival_datetime += timedelta(days=1)
                        final_summary['delivery_time_minutes'] = round((arrival_datetime - summary_data['order_datetime']).total_seconds() / 60)
                        print(f"      LOG: Calculated delivery time: {final_summary['delivery_time_minutes']} minutes.")
                except Exception as e: print(f"      [!] Warning: Failed to calculate delivery time. Error: {e}")
            all_final_summaries.append(final_summary)
            order_id = final_summary.get("order_id")
            for item in detailed_data["items"]:
                item["order_id"] = order_id
                all_final_items.append(item)
        except Exception as e:
            print(f"  [!] CRITICAL FAILURE for order from {order_dt}: {e}")
            await page.screenshot(path=f"error_order_{order_dt.strftime('%Y%m%d_%H%M%S')}.png")
            continue
    return all_final_summaries, all_final_items

# ==============================================================================
# --- DATA EXPORT AND MAIN WORKFLOW ---
# ==============================================================================

def export_to_excel(summaries_data: list[dict], items_data: list[dict]):
    """
    Saves the scraped data to a formatted Excel file with two sheets.
    """
    if not summaries_data:
        print("\nNo data was scraped to export.")
        return
    print("\n--- Processing data for Excel export ---")
    df_summary = pd.DataFrame(summaries_data)
    df_summary.sort_values(by="order_datetime", ascending=False, inplace=True)
    df_summary['order_datetime'] = df_summary['order_datetime'].dt.strftime('%Y-%m-%d %I:%M %p')
    for col in ['mrp', 'product_discount', 'item_total', 'handling_charge', 'delivery_charges', 'bill_total']:
        if col in df_summary.columns:
            df_summary[col] = pd.to_numeric(df_summary[col].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').fillna(0)
    df_summary.rename(columns={
        'order_id': 'Order ID', 'order_datetime': 'Order Date & Time', 'bill_total': 'Bill Total (₹)',
        'delivery_time_minutes': 'Delivery Time (Minutes)', 'arrival_status': 'Arrival Status',
        'total_item_count': 'Total Item Count', 'mrp': 'MRP (₹)', 'product_discount': 'Product Discount (₹)',
        'item_total': 'Item Sub-Total (₹)', 'handling_charge': 'Handling Charge (₹)',
        'delivery_charges': 'Delivery Charge (₹)', 'invoice_download_link': 'Invoice Download Link'
    }, inplace=True)
    summary_cols = ['Order ID', 'Order Date & Time', 'Bill Total (₹)', 'Delivery Time (Minutes)', 'Arrival Status',
                    'Total Item Count', 'MRP (₹)', 'Product Discount (₹)', 'Item Sub-Total (₹)',
                    'Handling Charge (₹)', 'Delivery Charge (₹)', 'Invoice Download Link']
    df_summary = df_summary[[col for col in summary_cols if col in df_summary.columns]]
    df_items = pd.DataFrame(items_data)
    if not df_items.empty:
        df_items.rename(columns={
            'order_id': 'Order ID', 'product_name': 'Product Name',
            'quantity': 'Product Variant / Quantity', 'price': 'Item Price (₹)'
        }, inplace=True)
        items_cols = ['Order ID', 'Product Name', 'Product Variant / Quantity', 'Item Price (₹)']
        df_items = df_items[[col for col in items_cols if col in df_items.columns]]
    output_filename = "blinkit_orders_detailed.xlsx"
    try:
        with pd.ExcelWriter(output_filename, engine='openpyxl') as writer:
            df_summary.to_excel(writer, sheet_name='Orders Summary', index=False)
            if not df_items.empty:
                df_items.to_excel(writer, sheet_name='Order Items', index=False)
        print(f"\n✅ Success! Data for {len(df_summary)} orders saved to '{output_filename}'")
        print(f"   The file contains two sheets: 'Orders Summary' and 'Order Items'.")
    except Exception as e:
        print(f"\n❌ Failed to save Excel file. Error: {e}")

async def main():
    """
    The main function that orchestrates the entire scraping workflow.
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
        context = await browser.new_context(storage_state=AUTH_FILE if os.path.exists(AUTH_FILE) else None)
        page = await context.new_page()
        try:
            print("\n--- Starting Blinkit Scraper ---")
            await page.goto("https://blinkit.com/", timeout=60000)
            print("\nLOG: Determining current page state...")
            location_input = page.locator('input[placeholder="search delivery location"]')
            if await location_input.is_visible(timeout=10000):
                print("LOG: State Detected: Location needs to be set.")
                if os.path.exists(AUTH_FILE):
                    os.remove(AUTH_FILE)
                await set_location_and_login_prep(page)
                await login_to_blinkit(page)
                print("LOG: Login successful. Pausing for 3 seconds to ensure session is stable...")
                await page.wait_for_timeout(3000)
                print(f"LOG: Saving new session to '{AUTH_FILE}' for future runs...")
                await context.storage_state(path=AUTH_FILE)
                print("LOG: Session saved.")
            elif await page.get_by_text("Login", exact=True).is_visible():
                print("LOG: State Detected: Location is set, but session is expired.")
                await login_to_blinkit(page)
                print("LOG: Login successful. Pausing for 3 seconds to ensure session is stable...")
                await page.wait_for_timeout(3000)
                print(f"LOG: Overwriting session file '{AUTH_FILE}' with new login data...")
                await context.storage_state(path=AUTH_FILE)
                print("LOG: Session saved.")
            elif await page.get_by_text("Account", exact=True).is_visible():
                print("LOG: State Detected: Fully logged in ('Account' button is visible).")
                print("LOG: Proceeding directly to scraping.")
            print("\nLOG: Final check before scraping: Verifying 'Account' button is visible...")
            await expect(page.get_by_text("Account", exact=True)).to_be_visible(timeout=10000)
            print("LOG: Verification successful. Proceeding to scrape orders.")
            all_summaries, all_items = await scrape_orders_since(page, start_date)
            if all_summaries:
                export_to_excel(all_summaries, all_items)
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
