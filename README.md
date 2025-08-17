# Blinkit Order Scraper

## Overview

This project contains a Python script that automates the process of scraping your order history from [Blinkit](https://blinkit.com). The script uses browser automation to log into your account, navigate to your past orders, filter them by a specific month (e.g., August), and extract details like item name, price, and date into a structured CSV file.

This README serves as both a user guide for the script and a project plan (PRD) for its development.

## Features

-   Automated login to Blinkit using a phone number.
-   Handles 2FA by prompting the user to enter the OTP from their phone.
-   Navigates to the order history page.
-   Scrolls automatically to load all orders for a given month.
-   Scrapes order details: item name, price, and date of purchase.
-   Saves the scraped data into a clean `orders.csv` file.

## Prerequisites

Before you begin, ensure you have the following installed:

-   [Python 3.8+](https://www.python.org/downloads/)
-   [pip](https://pip.pypa.io/en/stable/installation/) (Python package installer)

## Installation

1.  **Clone the repository:**
    ```bash
    # Replace with the actual repository URL when available
    git clone https://github.com/your-username/blinkit-scraper.git
    cd blinkit-scraper
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    # For macOS and Linux
    python3 -m venv venv
    source venv/bin/activate

    # For Windows
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  **Install the required Python libraries from `requirements.txt`:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Install browser binaries for Playwright:**
    Playwright needs to download browser binaries for automation. This is a one-time setup step.
    ```bash
    playwright install
    ```

## Usage

1.  **Run the script from your terminal:**
    You must provide your 10-digit Blinkit phone number using the `--phone` argument.

    ```bash
    python scraper.py --phone YOUR_PHONE_NUMBER
    ```
    *(Replace `YOUR_PHONE_NUMBER` with your number.)*

2.  **Enter the OTP:**
    The script will run a browser **in the background** (headless mode), navigate to Blinkit, and enter your phone number. No browser window will appear on your screen. It will then pause and prompt you to enter the 4-digit OTP in your terminal.
    ```
    Please enter the 4-digit OTP you received:
    ```
    *(Note for developers: If you need to debug the script and see the browser window, you can change `headless=True` to `headless=False` in the `scraper.py` file.)*

3.  **Find your data:**
    The script will proceed to scrape your orders from August and save them. When it's finished, you will see a success message. An `orders.csv` file will be created in the project directory with your data.

## Output File (`orders.csv`)

The script will generate a CSV file with the following structure:

| Date          | Item Name     | Price  |
|---------------|---------------|--------|
| 23 Aug, 2023  | Sliced Bread  | 45.0   |
| 23 Aug, 2023  | Peanut Butter | 250.0  |
| 15 Aug, 2023  | Milk          | 30.0   |
| ...           | ...           | ...    |

---

## Project Development Plan (PRD)

This section outlines the plan that was followed to build the scraper.

### Core Technologies

-   **Language:** Python
-   **Browser Automation:** Playwright
-   **HTML Parsing:** Beautiful Soup
-   **Data Handling:** Pandas

### Development Phases

-   **Phase 1: Initial Setup and Login Automation**
    -   **Status:** ✅ Complete
    -   **Details:** Set up the project structure with `scraper.py`, `requirements.txt`, and `.gitignore`. Implemented argument parsing for the phone number and the full login flow using Playwright, including handling the OTP prompt.

-   **Phase 2: Navigation and Filtering**
    -   **Status:** ✅ Complete
    -   **Details:** Added logic to navigate from the main page to the "My Orders" section after login. Implemented an automatic scrolling mechanism to dynamically load the entire order history until orders from the month prior to August were detected.

-   **Phase 3: Data Scraping**
    -   **Status:** ✅ Complete
    -   **Details:** After loading the page, the script passes the HTML content to Beautiful Soup. It then parses the page to find all order cards, filters for those in August, and loops through each item to extract its name and price.

-   **Phase 4: Data Storage and Finalization**
    -   **Status:** ✅ Complete
    -   **Details:** The scraped data is collected and stored in a Pandas DataFrame. The DataFrame is then exported to `orders.csv`. The script was finalized with headless mode, robust error handling, and clear user feedback messages.

## License

This project is licensed under the MIT License.
