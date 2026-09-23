# Browser Automation Scaling Architecture

## Problem Statement

The Chrome Remote Debugging approach (localhost:9222) works for **single users on their local machine**, but **does NOT scale** for a server with many concurrent users.

## Why Local Browser Control Doesn't Scale

### Architecture Limitation
```
❌ DOES NOT WORK AT SCALE:

User 1 (New York)  ──┐
User 2 (London)    ──┼──> Server (localhost:9222) ──> ONE Chrome instance
User 3 (Tokyo)     ──┘
```

**Problems:**
1. `localhost:9222` is the **server's** localhost, not the user's
2. All users would share ONE browser instance (security nightmare)
3. Users can't connect their home browser to your server
4. NAT/firewall blocks direct browser-to-server connections

### Resource Requirements Per User

| Resource | Per Browser Instance | 100 Users | 1000 Users |
|----------|---------------------|-----------|------------|
| RAM | 300-500 MB | 30-50 GB | 300-500 GB |
| CPU | 0.5-1 core | 50-100 cores | 500-1000 cores |
| Disk | 100 MB (profile) | 10 GB | 100 GB |
| Network | 5-10 Mbps (live) | 500 Mbps-1 Gbps | 5-10 Gbps |

**Conclusion:** Running 1000 concurrent browser instances on one server is **not feasible**.

---

## Scalable Architecture Options

### Option 1: Hybrid Model (Recommended)

**Keep current headless Playwright for most operations + User browser for sensitive tasks**

```
┌─────────────────────────────────────────────────────────────────┐
│ User's Local Browser (via Helper App)                           │
│ - LinkedIn login (preserves cookies)                            │
│ - Job applications (uses real session)                          │
│ - Manual review/approval steps                                  │
└─────────────────────────────────────────────────────────────────┘
                          ↓ WebSocket (optional)
┌─────────────────────────────────────────────────────────────────┐
│ Server: Headless Browser Pool (Current Architecture)            │
│ - Job search (browser-use + Playwright)                         │
│ - Resume generation                                              │
│ - Email drafting                                                 │
│ - Data extraction                                                │
└─────────────────────────────────────────────────────────────────┘
```

**Pros:**
- ✅ Scales to thousands of users (headless browsers are lightweight)
- ✅ Users can optionally use their real browser for sensitive operations
- ✅ No architectural changes needed
- ✅ Best of both worlds

**Cons:**
- ⚠️ Users without helper app use separate browser instances (current behavior)

**Implementation:**
```python
# backend/app/services/browser_control_service.py

async def run_browser_task(
    llm: BaseChatModel,
    task: str,
    user_id: str,
    max_steps: int = 15,
    prefer_user_browser: bool = False,  # NEW
    run_id: str | None = None,
) -> str:
    """Run browser task with fallback strategy."""
    
    # Try user's browser first if they have helper app running
    if prefer_user_browser:
        try:
            user_ws = get_user_websocket(user_id)  # Check if connected
            if user_ws:
                return await run_task_on_user_browser(user_ws, task)
        except Exception:
            logger.info("User browser unavailable, falling back to server browser")
    
    # Fallback: Use server-side headless browser (current behavior)
    return await run_task_on_server_browser(llm, task, user_id, max_steps, run_id)
```

---

### Option 2: Browserless.io / Chrome-as-a-Service

**Use managed browser infrastructure**

```
Your Backend ──> Browserless.io API ──> Browser Pool (auto-scaling)
```

**Services:**
- [Browserless.io](https://browserless.io) - $99-$499/month for 10-100 concurrent browsers
- [BrowserStack](https://browserstack.com) - Enterprise browser testing
- [Selenium Grid Cloud](https://www.selenium.dev/documentation/grid/) - Self-hosted

**Pros:**
- ✅ Managed scaling (they handle infrastructure)
- ✅ Pay per usage
- ✅ Global CDN (low latency)

**Cons:**
- ❌ Monthly cost scales with users
- ❌ Still uses separate browser instances (no user cookies)
- ❌ Vendor lock-in

**Cost Estimate:**
- 100 concurrent users: ~$500/month
- 1000 concurrent users: ~$5000/month

---

### Option 3: Kubernetes + Browser Pods

**Self-hosted browser pool with auto-scaling**

```yaml
# k8s/browser-pool-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: chrome-browser-pool
spec:
  replicas: 10  # Auto-scale based on load
  template:
    spec:
      containers:
      - name: chrome
        image: browserless/chrome:latest
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        env:
        - name: MAX_CONCURRENT_SESSIONS
          value: "5"
```

**Architecture:**
```
Load Balancer
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Browser Pod 1 (5 sessions) │ Browser Pod 2 (5 sessions)    │
│ Browser Pod 3 (5 sessions) │ Browser Pod 4 (5 sessions)    │
└─────────────────────────────────────────────────────────────┘
```

**Pros:**
- ✅ Auto-scaling based on demand
- ✅ Self-hosted (no per-user fees)
- ✅ Isolated browser sessions

**Cons:**
- ❌ Complex infrastructure (K8s expertise required)
- ❌ High server costs (need powerful nodes)
- ❌ Still no user cookies/sessions

**Cost Estimate:**
- 100 concurrent users: ~$500-1000/month (AWS/GCP)
- 1000 concurrent users: ~$5000-10000/month

---

### Option 4: Browser Extension + WebSocket Bridge

**Extension runs in user's browser, connects to your server**

```
User's Browser (with extension)
    ↓ WebSocket over HTTPS
Your Server (FastAPI WebSocket endpoint)
    ↓
Agent sends commands → Extension executes → Returns results
```

**Architecture:**
```python
# backend/app/api/v1/browser_ws.py

from fastapi import WebSocket, WebSocketDisconnect

class BrowserConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
    
    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
    
    async def send_command(self, user_id: str, command: dict):
        ws = self.active_connections.get(user_id)
        if ws:
            await ws.send_json(command)
            result = await ws.receive_json()
            return result
        raise Exception("User browser not connected")

manager = BrowserConnectionManager()

@router.websocket("/ws/browser/{user_id}")
async def browser_websocket(websocket: WebSocket, user_id: str):
    await manager.connect(user_id, websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        del manager.active_connections[user_id]
```

**Extension (manifest.json):**
```json
{
  "manifest_version": 3,
  "name": "CareerCraft Browser Control",
  "version": "1.0.0",
  "permissions": ["tabs", "activeTab", "scripting", "storage"],
  "background": {
    "service_worker": "background.js"
  },
  "host_permissions": [
    "https://www.linkedin.com/*",
    "https://www.naukri.com/*"
  ]
}
```

**Extension (background.js):**
```javascript
let ws = null;
let userId = null;

// Connect to server
async function connect() {
  const { userId: storedUserId } = await chrome.storage.local.get('userId');
  userId = storedUserId;
  
  ws = new WebSocket(`wss://api.careercraft.ai/ws/browser/${userId}`);
  
  ws.onmessage = async (event) => {
    const command = JSON.parse(event.data);
    const result = await executeCommand(command);
    ws.send(JSON.stringify({ success: true, result }));
  };
  
  ws.onerror = () => setTimeout(connect, 5000); // Reconnect
}

async function executeCommand(command) {
  const [tab] = await chrome.tabs.query({ active: true });
  
  switch (command.type) {
    case 'navigate':
      await chrome.tabs.update(tab.id, { url: command.url });
      return { navigated: true };
    
    case 'click':
      return await executeScript(tab.id, (sel) => {
        document.querySelector(sel)?.click();
      }, [command.selector]);
    
    case 'fill':
      return await executeScript(tab.id, (sel, val) => {
        const el = document.querySelector(sel);
        if (el) el.value = val;
      }, [command.selector, command.value]);
    
    case 'extract':
      return await executeScript(tab.id, (sel) => {
        return document.querySelector(sel)?.innerText;
      }, [command.selector]);
  }
}

async function executeScript(tabId, func, args) {
  const [result] = await chrome.scripting.executeScript({
    target: { tabId },
    func,
    args
  });
  return result.result;
}

connect();
```

**Pros:**
- ✅ Uses user's real browser with cookies/sessions
- ✅ Scales infinitely (no server-side browsers)
- ✅ Low server resource usage (just WebSocket connections)
- ✅ Works from anywhere (not localhost-only)

**Cons:**
- ❌ Users must install extension
- ❌ Chrome Web Store approval (2-4 weeks)
- ❌ Can't use Playwright's AI vision features
- ❌ Limited to basic DOM operations
- ❌ Extension must be open for automation to work

**Cost:**
- Server: ~$50-100/month (just WebSocket connections)
- Development: 2-3 weeks for extension + backend integration

---

## Recommended Architecture for Scale

### **Hybrid Model with Optional Extension**

```
┌─────────────────────────────────────────────────────────────────┐
│ Tier 1: Server-Side Headless Browsers (Default)                 │
│ - Job search, resume generation, email drafting                  │
│ - 95% of operations                                              │
│ - Current architecture (browser-use + Playwright)                │
│ - Scales to 1000+ users with proper resource management          │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ Tier 2: User Browser via Extension (Optional Premium Feature)   │
│ - LinkedIn login, job applications                               │
│ - Uses real cookies/sessions                                     │
│ - 5% of operations (sensitive tasks only)                        │
│ - Zero server resources (runs in user's browser)                 │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation Strategy

**Phase 1: Optimize Current Architecture (Do This First)**
```python
# backend/app/services/browser_pool.py

from asyncio import Semaphore
from contextlib import asynccontextmanager

class BrowserPool:
    def __init__(self, max_concurrent: int = 50):
        self.semaphore = Semaphore(max_concurrent)
        self.active_sessions = {}
    
    @asynccontextmanager
    async def get_browser(self, user_id: str):
        async with self.semaphore:  # Limit concurrent browsers
            browser = await self._create_browser(user_id)
            try:
                yield browser
            finally:
                await browser.close()
    
    async def _create_browser(self, user_id: str):
        from browser_use import Browser
        return Browser(
            headless=True,
            user_data_dir=f".browser_data/{user_id}",
            # Optimize for low resource usage
            args=[
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        )

# Global pool instance
browser_pool = BrowserPool(max_concurrent=50)

# Usage in agents
async def run_browser_task(...):
    async with browser_pool.get_browser(user_id) as browser:
        # Run task
        ...
```

**Phase 2: Add Browser Extension (Optional Premium)**
- Build extension for users who want real browser control
- Offer as premium feature ($10/month extra)
- Falls back to server browsers if extension not installed

**Phase 3: Horizontal Scaling**
```yaml
# docker-compose.scale.yml
services:
  backend:
    deploy:
      replicas: 5  # Multiple backend instances
  
  redis:
    # Shared session state
  
  nginx:
    # Load balancer
```

---

## Resource Planning

### Server Specifications by User Count

| Concurrent Users | CPU Cores | RAM | Monthly Cost (AWS) |
|-----------------|-----------|-----|-------------------|
| 10 | 4 | 8 GB | $50-100 |
| 50 | 8 | 32 GB | $200-400 |
| 100 | 16 | 64 GB | $500-800 |
| 500 | 64 | 256 GB | $2000-4000 |
| 1000 | 128 | 512 GB | $5000-10000 |

### Optimization Strategies

1. **Browser Pooling** - Reuse browser instances (max 50 concurrent)
2. **Headless Mode** - 40% less RAM than headed browsers
3. **Lazy Loading** - Only launch browsers when needed
4. **Session Timeout** - Close idle browsers after 5 minutes
5. **Horizontal Scaling** - Multiple backend servers behind load balancer
6. **CDN for Static Assets** - Reduce server load
7. **Database Connection Pooling** - Reduce DB overhead

---

## Final Recommendation

### For 10-100 Users (Current Scale)
✅ **Keep current architecture** (browser-use + Playwright headless)
- Add browser pooling with max 50 concurrent
- Optimize Docker container resources
- Cost: $100-500/month

### For 100-1000 Users (Growth Phase)
✅ **Hybrid Model:**
1. Server-side headless browsers (default)
2. Optional browser extension (premium feature)
3. Horizontal scaling with load balancer
- Cost: $500-2000/month

### For 1000+ Users (Enterprise Scale)
✅ **Multi-tier Architecture:**
1. Kubernetes cluster with auto-scaling browser pods
2. Browser extension for premium users
3. Browserless.io for overflow capacity
4. Global CDN + edge caching
- Cost: $5000-10000/month

---

## Next Steps

1. **Measure current usage:**
   ```bash
   # Add metrics to track concurrent browser sessions
   docker stats
   ```

2. **Implement browser pooling** (Phase 1)

3. **Load test** with 50-100 concurrent users:
   ```bash
   locust --host=http://localhost:8000 --users=100 --spawn-rate=10
   ```

4. **Decide on extension** based on user feedback

5. **Plan horizontal scaling** when you hit 50+ concurrent users

**Start with optimization, scale horizontally when needed, add extension as premium feature.**
