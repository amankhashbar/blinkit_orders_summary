# Blinkit Order Scraper

## Overview

This project contains a professional-grade Python script that automates the process of scraping your order history from [Blinkit](https://blinkit.com). The script uses modern, robust automation techniques to handle complex login flows, dynamic content, and session management, saving the cleaned data to a user-friendly Excel file.

This README serves as a comprehensive guide for using and understanding the script.

## Key Features

-   **Persistent Login Sessions:** After the first manual login, the script saves your session state to an `auth.json` file. Subsequent runs will use this file to log you in automatically, bypassing the need for OTP entry.
-   **Forced Re-Login:** Includes a `--relogin` command-line flag to easily delete the saved session and perform a fresh manual login when needed (e.g., if the session expires).
-   **Interactive Date Input:** Instead of a fixed month, the script prompts you to enter a start date, allowing you to scrape all orders from that date to the present.
-   **Robust Automation:** Built with asynchronous Playwright (`asyncio`) and modern `expect` waits to handle pop-ups, dynamic content, and infinite scrolling reliably. It uses precise, user-vetted selectors to minimize errors.
-   **Smart Data Cleaning:** Parses and cleans data at the source (e.g., removing currency symbols, standardizing dates), handles different order statuses (ignoring returns), and uses a unique key to prevent duplicate entries during scraping.
-   **Clean Excel Export:** Saves the final, cleaned data to a formatted `blinkit_orders_cleaned.xlsx` file, sorted with the newest orders first.

## Prerequisites

-   [Python 3.8+](https://www.python.org/downloads/)
-   [pip](https://pip.pypa.io/en/stable/installation/)

## Installation

1.  **Clone the repository:**
    ```bash
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

3.  **Install the required Python libraries:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Install Playwright's browser binaries (one-time setup):**
    ```bash
    playwright install
    ```

## Usage

The script is designed to be run interactively from your terminal. It manages your login session to make repeated use fast and easy.

### Step 1: First-Time Login

The very first time you run the script, you will need to perform a full manual login.

1.  **Run the script:**
    ```bash
    python scraper.py
    ```
2.  **Enter Start Date:** The script will first ask for a start date.
    ```
    👉 Please enter the start date to scrape orders from (YYYY-MM-DD):
    ```
3.  **Follow Browser Instructions:** A browser window will open. The script will handle pop-ups and set the location automatically.
4.  **Enter Phone & OTP:** The script will prompt you in the terminal to enter your phone number and then your OTP.
5.  **Session Saved:** After a successful login, the script will create an `auth.json` file. This file stores your session so you don't have to log in again.

### Step 2: Subsequent Runs

On every subsequent run, the script will automatically use the `auth.json` file to log you in.

1.  **Run the script:**
    ```bash
    python scraper.py
    ```
2.  **Enter Start Date:** Provide the start date for the scrape.
3.  **Automatic Login:** The script will open the browser and should start from a logged-in state, proceeding directly to the scraping process.

### Forcing a New Login

If your saved session expires or you want to use a different account, you can force a new manual login using the `--relogin` flag.

```bash
python scraper.py --relogin
```
This command will delete the `auth.json` file before starting, triggering the first-time login workflow again.

## Output File (`blinkit_orders_cleaned.xlsx`)

The script generates a clean Excel file with one row for each order, sorted with the most recent order first.

| Order Date & Time   | Total Amount (₹) | Delivery Time (Minutes) |
|---------------------|------------------|-------------------------|
| 2025-08-15 10:30 PM | 550              | 8                       |
| 2025-08-14 08:15 AM | 120              | 12                      |
| ...                 | ...              | ...                     |
