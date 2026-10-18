# Gardevoir Campus Second-Hand Marketplace

## Product vision statement

Gardevoir helps students buy and sell second-hand items on campus through a simple mobile-friendly marketplace.

## Current status

The shared Flask and MongoDB foundation, account flow, and route contracts are ready. Public browsing and search read active listings from MongoDB and share the same item cards. Item details show listing information and seller contact; sold items have a sold notice, and missing or deleted items return a helpful 404 page. Search supports combined keyword, category, and price filters. Publishing and management still use temporary pages until their owners implement them. See [team handoff](docs/TEAM_HANDOFF.md).

## User stories and task boards

- [User stories in GitHub Issues](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/issues)
- [Sprint task boards in GitHub Projects](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/projects)

The team still needs to enable Issues and create the stories and two sprint boards in GitHub.

## Run locally

1. Clone the team repository and enter it:

   ```bash
   git clone https://github.com/software-students-fall2026/web-app-exercise-Gardevoir.git
   cd web-app-exercise-Gardevoir
   ```

2. Run the course setup once in this clone and follow its prompts to approve the coding-tool hooks:

   ```bash
   python3 .automations/setup.py
   ```

   On Windows, use `python .automations/setup.py`.

3. Start Docker Desktop (or provide an existing MongoDB server), then choose one Python environment setup from the repository root.

   **Conda (optional):** With Miniconda or Anaconda installed, run the following in a terminal where `conda` is available. On Windows, use Anaconda Prompt or a PowerShell terminal initialized for Conda:

   ```bash
   conda env create -f environment.yml
   conda activate gardevoir
   ```

   This creates the `gardevoir` environment with Python 3.12 and installs the application and test dependencies from `requirements-dev.txt`. Keep this environment active for the remaining commands.

   **Alternatively, use venv:** Install Python 3.10 or newer, then create a virtual environment and install the application dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

   On Windows, use `python -m venv .venv`, then activate with `.\.venv\Scripts\Activate.ps1` in PowerShell or `.venv\Scripts\activate.bat` in Command Prompt. Run the same `python -m pip install -r requirements.txt` command after activation.

4. Copy `env.example` to `.env`. Replace `SECRET_KEY` with a random value and change `MONGO_PASSWORD`. Update the password in `MONGODB_URI` to match. If your team uses an existing MongoDB server, replace `MONGODB_URI` with that server's connection string. Keep `.env` private and share it only through the team's messenger channel.

   ```bash
   cp env.example .env
   ```

   On Windows, use `copy env.example .env`. A random secret can be generated with `python -c "import secrets; print(secrets.token_hex(32))"`.

5. If using the included local MongoDB service, start it from the repository root:

   ```bash
   docker compose up -d mongo
   ```

6. Check the database, create indexes, and add three sample items:

   ```bash
   flask --app app db-check
   flask --app app db-init
   flask --app app seed-demo
   ```

7. Start the web application:

   ```bash
   flask --app app run --debug
   ```

   Open `http://127.0.0.1:5000`. Register an account to access the protected pages. To give the sample items to that account for management testing, run `flask --app app seed-demo --owner-email your-email@example.edu` after registering.

To stop the local database, run `docker compose down`. The named volume preserves data between runs.

## Test and try browsing and search

With the `gardevoir` Conda environment active, run `python -m pytest -q`. If using venv, first install the test dependencies with `python -m pip install -r requirements-dev.txt`. The tests use in-memory MongoDB fixtures and do not require a running database server.

After seeding the live database and starting Flask, open [Browse](http://127.0.0.1:5000/items) and select a listing to see its details and contact information. Open [search with combined filters](http://127.0.0.1:5000/search?q=lamp&category=Furniture&min_price=10&max_price=20) to find the demo Desk lamp and follow its card to the same detail page. Try an unmatched keyword to see the empty state, then use **Clear filters** to restore all active listings. Open `/items/not-an-id` to check the missing-item page.
