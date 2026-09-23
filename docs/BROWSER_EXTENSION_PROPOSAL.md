# Browser Integration: User's Real Browser Control

## Problem
Currently, the app launches separate browser instances. Users want the app to control their **actual browser** with their real cookies/sessions.

## Recommended Solution: Chrome Remote Debugging + Helper App

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ User's Chrome Browser (launched with --remote-debugging)    │
│ - Real cookies, sessions, logins                            │
│ - Port 9222 exposed locally                                 │
└─────────────────────────────────────────────────────────────┘
                          ↓ Chrome DevTools Protocol
┌─────────────────────────────────────────────────────────────┐
│ Helper App (Electron/Tauri)                                 │
│ - Launches Chrome with correct flags                        │
│ - Manages connection                                         │
│ - System tray icon                                           │
└─────────────────────────────────────────────────────────────┘
                          ↓ WebSocket
┌─────────────────────────────────────────────────────────────┐
│ Backend (FastAPI)                                            │
│ - Connects via Playwright CDP                                │
│ - Sends browser-use AI commands                              │
│ - Full vision + automation capabilities                      │
└─────────────────────────────────────────────────────────────┘
```

### Implementation Steps

#### 1. Update Backend to Support CDP Connection

**File: `backend/app/services/browser_control_service.py`**

Add new function:

```python
async def connect_to_user_browser(
    user_id: str,
    cdp_url: str = "http://localhost:9222",
) -> Browser:
    """Connect to user's existing Chrome instance via CDP.
    
    User must launch Chrome with:
    chrome --remote-debugging-port=9222
    """
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(cdp_url)
        return browser
```

Modify `run_browser_task` to accept `use_user_browser` flag:

```python
async def run_browser_task(
    llm: BaseChatModel,
    task: str,
    user_id: str,
    max_steps: int = 15,
    live_browser: bool = False,
    use_user_browser: bool = False,  # NEW
    cdp_url: str = "http://localhost:9222",  # NEW
    run_id: str | None = None,
) -> str:
    """Run browser task on user's actual browser or separate instance."""
    
    if use_user_browser:
        # Connect to user's existing browser
        browser = await connect_to_user_browser(user_id, cdp_url)
    else:
        # Launch separate browser (current behavior)
        user_dir = BROWSER_DATA_DIR / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        browser = Browser(headless=not live_browser, user_data_dir=str(user_dir))
    
    # Rest of the function remains the same
    ...
```

#### 2. Create Helper App (Electron)

**Purpose:** Makes it easy for users to launch Chrome with debugging enabled.

**File: `helper-app/main.js`**

```javascript
const { app, BrowserWindow, Tray, Menu } = require('electron');
const { spawn } = require('child_process');
const path = require('path');

let tray = null;
let chromeProcess = null;

app.whenReady().then(() => {
  // Create system tray icon
  tray = new Tray(path.join(__dirname, 'icon.png'));
  
  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Start Browser Control',
      click: () => launchChrome()
    },
    {
      label: 'Stop Browser Control',
      click: () => stopChrome()
    },
    {
      label: 'Quit',
      click: () => app.quit()
    }
  ]);
  
  tray.setContextMenu(contextMenu);
  tray.setToolTip('CareerCraft Browser Helper');
});

function launchChrome() {
  const chromePath = process.platform === 'win32'
    ? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
    : '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  
  chromeProcess = spawn(chromePath, [
    '--remote-debugging-port=9222',
    '--user-data-dir=' + path.join(app.getPath('userData'), 'chrome-profile')
  ]);
  
  tray.setTitle('🟢 Connected');
}

function stopChrome() {
  if (chromeProcess) {
    chromeProcess.kill();
    chromeProcess = null;
  }
  tray.setTitle('🔴 Disconnected');
}
```

#### 3. Add User Settings Toggle

**File: `frontend/src/app/(app)/settings/browser/page.tsx`**

```tsx
export default function BrowserSettingsPage() {
  const [useRealBrowser, setUseRealBrowser] = useState(false);
  const [cdpUrl, setCdpUrl] = useState('http://localhost:9222');
  
  return (
    <div className="space-y-6">
      <h1>Browser Settings</h1>
      
      <div className="space-y-4">
        <label className="flex items-center space-x-2">
          <input
            type="checkbox"
            checked={useRealBrowser}
            onChange={(e) => setUseRealBrowser(e.target.checked)}
          />
          <span>Use my actual browser (requires helper app)</span>
        </label>
        
        {useRealBrowser && (
          <div>
            <label>Chrome DevTools URL</label>
            <input
              type="text"
              value={cdpUrl}
              onChange={(e) => setCdpUrl(e.target.value)}
              className="w-full px-3 py-2 border rounded"
            />
            <p className="text-sm text-gray-500 mt-1">
              Download helper app: <a href="/downloads/helper-app">CareerCraft Browser Helper</a>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
```

#### 4. Security Considerations

**IMPORTANT:**
- CDP port (9222) should ONLY be accessible from localhost
- Add authentication token to CDP connection
- Validate all commands before execution
- User must explicitly enable this feature

**Add to `.env.example`:**
```bash
# Browser Control
ALLOW_USER_BROWSER_CONTROL=false
CDP_AUTH_TOKEN=your-secret-token-here
```

### Alternative: Browser Extension (More Complex)

If you want a pure extension approach:

#### Extension Manifest (manifest.json)
```json
{
  "manifest_version": 3,
  "name": "CareerCraft Browser Control",
  "version": "1.0.0",
  "permissions": [
    "tabs",
    "activeTab",
    "scripting",
    "storage"
  ],
  "background": {
    "service_worker": "background.js"
  },
  "action": {
    "default_popup": "popup.html"
  }
}
```

#### Background Script (background.js)
```javascript
let ws = null;

// Connect to backend
function connect() {
  ws = new WebSocket('ws://localhost:8000/ws/browser-control');
  
  ws.onmessage = async (event) => {
    const command = JSON.parse(event.data);
    
    switch (command.type) {
      case 'navigate':
        await chrome.tabs.update({ url: command.url });
        break;
      case 'click':
        await executeScript(command.selector, 'click');
        break;
      case 'fill':
        await executeScript(command.selector, 'fill', command.value);
        break;
    }
  };
}

async function executeScript(selector, action, value) {
  const [tab] = await chrome.tabs.query({ active: true });
  
  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: (sel, act, val) => {
      const el = document.querySelector(sel);
      if (act === 'click') el.click();
      if (act === 'fill') el.value = val;
    },
    args: [selector, action, value]
  });
}

connect();
```

**Cons of Extension Approach:**
- Can't use Playwright's AI vision features
- Limited to basic DOM manipulation
- Chrome Web Store approval required
- Users must install manually

## Recommendation

**Start with Chrome Remote Debugging + Helper App:**

1. ✅ Works immediately (no store approval)
2. ✅ Full Playwright/browser-use capabilities
3. ✅ Uses user's real browser profile
4. ✅ Minimal code changes
5. ✅ Better security (localhost only)

**Build extension later** if users demand it, but CDP approach is superior for automation.

## Next Steps

1. Implement CDP connection in `browser_control_service.py`
2. Build simple Electron helper app
3. Add settings toggle in frontend
4. Test with LinkedIn/Naukri automation
5. Document setup process for users

## User Experience

**With Helper App:**
1. User downloads CareerCraft Browser Helper
2. Clicks "Start Browser Control" in system tray
3. Chrome opens with their real profile
4. App can now control their browser
5. All cookies/sessions preserved

**Without Helper App (Manual):**
1. User runs: `chrome --remote-debugging-port=9222`
2. Enters `http://localhost:9222` in app settings
3. App connects and controls browser

Both approaches use the same backend code.
