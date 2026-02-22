#!/bin/bash
# WebReaper Blogwatcher Hook
# Automatically scrapes RSS-less sites using WebReaper

# Check if URL has RSS feed
url="$1"
name="$2"

# Try to detect RSS
rss_url=$(curl -s "$url" | grep -oE 'href="[^"]*\.xml"[^>]*type="application/rss\+xml"' | head -1 | sed 's/href="//;s/".*//')

if [ -n "$rss_url" ]; then
    # RSS found, use standard blogwatcher
    echo "RSS feed found: $rss_url"
    exit 0
fi

# No RSS, use WebReaper
echo "No RSS feed found. Using WebReaper to scrape..."

# Run WebReaper integration
python3 "$(dirname "$0")/webreaper.py" integration "$url" --name "$name" --output ~/.config/blogwatcher/feeds/

exit 0
