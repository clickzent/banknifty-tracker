name: Bank Nifty Daily Tracker

on:
  schedule:
    # Runs at 3:15 PM IST = 9:45 AM UTC
    - cron: '45 9 * * 1-5'
  workflow_dispatch:  # allows manual trigger too, for testing

jobs:
  run-tracker:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install requests pandas

      - name: Run tracker script
        run: python tracker.py

      - name: Commit updated CSV back to repo
        run: |
          git config --global user.name "github-actions"
          git config --global user.email "actions@github.com"
          git add banknifty_paper_trades.csv
          git commit -m "Daily update $(date)" || echo "No changes to commit"
          git push
