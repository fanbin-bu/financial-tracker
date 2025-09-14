 # Close all Chrome windows first (keeps your real profile untouched)
osascript -e 'quit app "Google Chrome"'

# Start a throwaway Chrome profile that you can safely automate
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome-costco-selenium