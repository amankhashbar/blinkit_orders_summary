# Blinkit Order Scraper

## Overview

This project contains a Python script that automates the process of scraping your order history from [Blinkit](https://blinkit.com). The script uses browser automation to log into your account, navigate to your past orders, filter them by a specific month (e.g., August), and extract details like item name, price, and date into a structured CSV file.

This README serves as both a user guide for the script and a project plan (PRD) for its development.

## Features

-   Automated login to Blinkit using a phone number.
-   Handles 2FA by prompting the user to enter the OTP from their phone.
-   Navigates to the order history page.
-   Scrolls automatically to load all orders for a given month.
-   Navigates into each order's detail page to scrape comprehensive data.
-   Scrapes Order ID, Order Date, Total Amount, and all individual items with their prices.
-   Saves the scraped data into a clean, wide-format Excel file (`orders.xlsx`).

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

The script automates the entire process of logging in and navigating the Blinkit website. Here is a step-by-step breakdown of what the script will do automatically in the browser window that opens:

1.  **Set Location:** The script will first handle the location pop-up. It will automatically type "nirvana country in sector 50" into the search bar and select the first suggestion.
2.  **Initiate Login:** It will then find the "Login" button on the top right of the homepage and click it.
3.  **Enter Phone Number:** It will enter the phone number you provide via the command line.
4.  **Handle Popups:** It will automatically close any "Open in App" popups that might appear after login.

Your only manual step is to provide the OTP when prompted in your terminal.

### Running the Script

1.  **Execute from your terminal:**
    You must provide your 10-digit Blinkit phone number using the `--phone` argument.
    ```bash
    python scraper.py --phone YOUR_PHONE_NUMBER
    ```
    *(Replace `YOUR_PHONE_NUMBER` with your number.)*

2.  **Enter the OTP:**
    A browser window will open and perform the steps above. When it reaches the OTP screen, your terminal will prompt you:
    ```
    Please enter the 4-digit OTP you received:
    ```
    Enter the OTP and press Enter.

3.  **Find your data:**
    The script will complete the login, navigate to your order history, scrape the data, and save it to `orders.xlsx`.

## Output File (`orders.xlsx`)

The script generates an Excel file where each row represents a single order. Because each order can have a different number of items, the number of columns will vary from row to row.

The structure is as follows:

| Order ID | Order Date | Total Order Amount | Item 1                 | Item 2                  | Item 3      | ... |
|----------|------------|--------------------|------------------------|-------------------------|-------------|-----|
| 12345    | 15 Aug 2023| ₹550.00            | Sliced Bread (₹45.00)  | Peanut Butter (₹250.00) | Milk (₹30.00)| ... |
| 67890    | 21 Aug 2023| ₹120.00            | Instant Noodles (₹120.00)|                         |             |     |

---

## Troubleshooting

### Cloudflare Block: "The page you are trying to access has blocked you"

Some websites, including Blinkit, use security services like Cloudflare to prevent automated scraping. If you run the script and get an error page that mentions you are "blocked," it's because the website has detected the automation.

To avoid this, the script is configured to run in "headful" mode (`headless=False`), which means it opens a visible browser window and performs actions at a slightly slower, more human-like pace. This makes the script much less likely to be detected as a bot.

If you still encounter issues, it's possible the site has updated its security measures further.

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
