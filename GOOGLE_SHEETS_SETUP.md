This guide will walk you through setting up the necessary credentials to allow your Python application to securely access and modify a Google Sheet.

### Step 1: Create a Google Cloud Platform (GCP) Project

1.  **Navigate to the Google Cloud Console:**
    *   Go to [https://console.cloud.google.com/](https://console.cloud.google.com/).
    *   If you don't have an account, you'll need to create one.

2.  **Create a New Project:**
    *   In the top navigation bar, click the project selection dropdown (it might say "Select a project").
    *   In the dialog that appears, click **"New Project"**.
    *   Enter a **Project Name** (e.g., "Telegram Bot Integration").
    *   Select an organization or leave it as "No organization".
    *   Click **"Create"**. Wait for the project to be provisioned.

3.  **Select Your Project:**
    *   Once created, ensure your new project is selected in the top dropdown menu.

### Step 2: Enable Required APIs

Your project needs permission to use the Google Drive and Google Sheets services.

1.  **Go to the API Library:**
    *   In the navigation menu (☰), go to **"APIs & Services" -> "Library"**.

2.  **Enable the Google Drive API:**
    *   In the search bar, type "Google Drive API" and select it from the results.
    *   Click the **"Enable"** button.

3.  **Enable the Google Sheets API:**
    *   Go back to the API Library.
    *   Search for "Google Sheets API" and select it.
    *   Click the **"Enable"** button.

### Step 3: Create a Service Account

A service account is a special type of Google account for an application (not a person).

1.  **Navigate to Service Accounts:**
    *   In the navigation menu (☰), go to **"IAM & Admin" -> "Service Accounts"**.

2.  **Create the Service Account:**
    *   Click **"+ Create Service Account"** at the top.
    *   **Service account name:** Give it a descriptive name (e.g., `telegram-bot-editor`).
    *   The **Service account ID** will be generated automatically.
    *   Click **"Create and Continue"**.

3.  **Grant Permissions (Role):**
    *   In the "Grant this service account access to project" step, click the **"Role"** dropdown.
    *   Select **"Basic" -> "Editor"**. This role provides broad permissions to edit project resources, which includes Google Sheets owned by the project.
    *   Click **"Continue"**.

4.  **Finish Creation:**
    *   You can skip the "Grant users access to this service account" step.
    *   Click **"Done"**.

### Step 4: Generate a JSON Key

This key is a credentials file that your Python script will use to authenticate as the service account.

1.  **Open Your New Service Account:**
    *   From the list of service accounts, click on the email address of the one you just created.

2.  **Navigate to the Keys Tab:**
    *   Click on the **"Keys"** tab.

3.  **Create a New Key:**
    *   Click **"Add Key" -> "Create new key"**.

4.  **Select JSON and Create:**
    *   Choose **JSON** as the key type.
    *   Click **"Create"**.
    *   A JSON file will be automatically downloaded to your computer.

5.  **Secure Your Key:**
    *   **Treat this file like a password!** Do not share it publicly or commit it to version control.
    *   Rename the downloaded file to `service_account.json` for simplicity and place it in your project folder.

### Step 5: Create a Google Sheet and Share It

1.  **Create a New Sheet:**
    *   Go to [https://sheets.google.com/](https://sheets.google.com/) and create a new, blank spreadsheet.
    *   Give it a name, for example, "Telegram Bot Users".

2.  **Get the Service Account Email:**
    *   Open your downloaded `service_account.json` file in a text editor.
    *   Find the value for the `"client_email"` key. It will look something like this:
        `"telegram-bot-editor@your-project-id.iam.gserviceaccount.com"`
    *   Copy this entire email address.

3.  **Share the Sheet:**
    *   In your Google Sheet, click the **"Share"** button in the top-right corner.
    *   Paste the service account's email address into the "Add people and groups" field.
    *   Ensure it has **"Editor"** permissions.
    *   Click **"Share"**.

### Step 6: Get Your Spreadsheet ID

1.  **Look at the URL of your spreadsheet.** It will be in this format:
    `https://docs.google.com/spreadsheets/d/THIS_IS_THE_SPREADSHEET_ID/edit#gid=0`

2.  **Copy the Spreadsheet ID.** It's the long string of characters between `/d/` and `/edit`.

**Action Complete!**

Once you have completed these steps, you will have:
1.  A `service_account.json` file in your bot's folder.
2.  Your unique **Spreadsheet ID**.

**Please let me know once you have both of these items ready.** I will then proceed with Part 2, where I will write the Python code to connect your bot to the sheet.
