import subprocess
import time
import json
import urllib.request
import asyncio
import websockets
import base64
import os
from PIL import Image

async def capture_modules():
    chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    user_data = r"C:\Users\vivek\AppData\Local\Temp\chrome_dev_modules"
    
    proc = subprocess.Popen([
        chrome_exe,
        "--headless=new",
        "--disable-gpu",
        f"--user-data-dir={user_data}",
        "--remote-debugging-port=9222",
        "--window-size=1400,1050",
        "about:blank"
    ])
    
    await asyncio.sleep(2)
    
    try:
        tabs = json.loads(urllib.request.urlopen("http://localhost:9222/json").read())
        ws_url = tabs[0]["webSocketDebuggerUrl"]
        
        async with websockets.connect(ws_url, max_size=25*1024*1024) as ws:
            msg_id = 1
            
            async def send_cmd(method, params=None):
                nonlocal msg_id
                cid = msg_id
                msg_id += 1
                msg = {"id": cid, "method": method, "params": params or {}}
                await ws.send(json.dumps(msg))
                while True:
                    resp_str = await ws.recv()
                    resp = json.loads(resp_str)
                    if resp.get("id") == cid:
                        return resp.get("result", {})
            
            # Enable domains
            await send_cmd("Page.enable")
            await send_cmd("Runtime.enable")
            await send_cmd("DOM.enable")
            
            # Navigate to app
            print("Navigating to http://13.238.255.197:8000...")
            await send_cmd("Page.navigate", {"url": "http://13.238.255.197:8000"})
            await asyncio.sleep(3)
            
            # Trigger pipeline run to get full data
            print("Triggering executePipeline()...")
            await send_cmd("Runtime.evaluate", {
                "expression": "executePipeline();"
            })
            await asyncio.sleep(4)
            
            modules = [
                ("mod1", "module1_monitoring.png", "tab-mod1"),
                ("mod2", "module2_waste_detection.png", "tab-mod2"),
                ("mod3", "module3_cost_estimation.png", "tab-mod3"),
                ("mod4", "module4_ai_advisor.png", "tab-mod4"),
                ("mod5", "module5_remediation.png", "tab-mod5"),
                ("mod6", "module6_terraform.png", "tab-mod6"),
                ("mod7", "module7_gitops.png", "tab-mod7"),
            ]
            
            for mod_id, filename, elem_id in modules:
                print(f"Capturing {mod_id} ({elem_id})...")
                # Switch tab and scroll element into view
                await send_cmd("Runtime.evaluate", {
                    "expression": f"""
                    switchTab('{mod_id}');
                    const el = document.getElementById('{elem_id}');
                    if (el) el.scrollIntoView({{ behavior: 'instant', block: 'start' }});
                    """
                })
                await asyncio.sleep(0.8)
                
                # Get bounding rect of the element
                rect_res = await send_cmd("Runtime.evaluate", {
                    "expression": f"""
                    (() => {{
                        const el = document.getElementById('{elem_id}');
                        if (!el) return null;
                        const r = el.getBoundingClientRect();
                        return {{
                            x: Math.max(0, Math.round(r.x)),
                            y: Math.max(0, Math.round(r.y)),
                            width: Math.round(r.width),
                            height: Math.min(850, Math.round(r.height))
                        }};
                    }})()
                    """,
                    "returnByValue": True
                })
                
                clip = rect_res.get("result", {}).get("value")
                if clip and clip.get("height", 0) > 50:
                    clip["scale"] = 1
                    shot_res = await send_cmd("Page.captureScreenshot", {
                        "format": "png",
                        "clip": clip
                    })
                else:
                    shot_res = await send_cmd("Page.captureScreenshot", {"format": "png"})
                
                img_data = base64.b64decode(shot_res["data"])
                with open(filename, "wb") as f:
                    f.write(img_data)
                
                im = Image.open(filename)
                print(f"Saved {filename}: {im.size}")
                
    finally:
        proc.terminate()
        print("Chrome terminated.")

if __name__ == "__main__":
    asyncio.run(capture_modules())
