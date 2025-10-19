pip install -r requirements.txt

npm init -y
npm install @playwright/test
npx playwright install-deps
npx playwright install
playwright install chromium

# To create a symlink from newer chromium to the version MCP wants as it was giving some unwanted version error. This was the fix.
cd ~/.cache/ms-playwright/
ln -s chromium-1194 chromium-1179
ln -s chromium_headless_shell-1194 chromium_headless_shell-1179

