from __future__ import annotations

import base64
import json
import os
import re
from typing import Generator, Optional, List, Dict, Any
from urllib.parse import urljoin, urlparse

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.responses import StreamingResponse

load_dotenv()

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
BROWSERLESS_TOKEN = os.getenv("BROWSERLESS_TOKEN")

if not (NVIDIA_API_KEY and BROWSERLESS_TOKEN):
    raise RuntimeError(
        "NVIDIA_API_KEY or BROWSERLESS_TOKEN missing. "
        "Add them to a `.env` file or export before running FastAPI."
    )

BROWSERLESS_BASE = f"https://production-sfo.browserless.io"

app = FastAPI(title="A Website Cloner")



def extract_design_context(url: str) -> Dict[str, Any]:
    
    extract_script = """
        () => {
            const isElementVisible = (el) => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return (
                    rect.width > 5 &&
                    rect.height > 5 &&
                    style.display !== 'none' &&
                    style.visibility !== 'hidden' &&
                    style.opacity !== '0'
                );
            };

            const getElementDetails = (el) => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                const attrs = {};
                for (let attr of el.attributes) {
                    attrs[attr.name] = attr.value;
                }

                return {
                    tagName: el.tagName.toLowerCase(),
                    attributes: attrs,
                    textContent: el.innerText?.trim() || "",
                    boundingClientRect: {
                        x: rect.x,
                        y: rect.y,
                        width: rect.width,
                        height: rect.height
                    },
                    computedStyle: {
                        color: style.color,
                        backgroundColor: style.backgroundColor,
                        fontSize: style.fontSize,
                        fontWeight: style.fontWeight,
                        fontFamily: style.fontFamily,
                        textAlign: style.textAlign,
                        display: style.display,
                        position: style.position,
                        margin: style.margin,
                        padding: style.padding,
                        border: style.border,
                        borderRadius: style.borderRadius,
                        boxShadow: style.boxShadow,
                        zIndex: style.zIndex,
                        opacity: style.opacity,
                        overflow: style.overflow,
                        flexDirection: style.flexDirection,
                        justifyContent: style.justifyContent,
                        alignItems: style.alignItems,
                        gap: style.gap
                    },
                    htmlSnippet: el.cloneNode(false).outerHTML
                };
            };

            const elements = Array.from(document.querySelectorAll('body *'));
            const elementMap = elements
                .filter(isElementVisible)
                .map(getElementDetails);

            return {
                title: document.title,
                elementMap,
                viewport: {
                    width: window.innerWidth,
                    height: window.innerHeight
                },
                meta: {
                    description: document.querySelector('meta[name="description"]')?.content || "",
                    keywords: document.querySelector('meta[name="keywords"]')?.content || ""
                }
            };
        }
        """

    
    endpoint = f"{BROWSERLESS_BASE}/function?token={BROWSERLESS_TOKEN}"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "url": url,
        "function": extract_script
    }
    
    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": f"Failed to extract design context: {str(e)}"}


def extract_dom_structure(url: str) -> Dict[str, Any]:
    
    endpoint = f"{BROWSERLESS_BASE}/content?token={BROWSERLESS_TOKEN}"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "url": url,
        "elements": [
            {"selector": "head"},
            {"selector": "body"},
            {"selector": "style"},
            {"selector": "link[rel='stylesheet']"}
        ]
    }
    
    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        content = resp.json()
        
        # Extract CSS from style tags and linked stylesheets
        css_content = []
        if 'data' in content:
            for item in content['data']:
                if item.get('selector') == 'style':
                    css_content.append(item.get('text', ''))
        
        return {
            "html": content,
            "extracted_css": "\n".join(css_content)
        }
    except Exception as e:
        return {"error": f"Failed to extract DOM: {str(e)}"}


def grab_screenshot(
    url: str,
    *,
    add_script_tag: list[dict] | None = None,
    add_style_tag: list[dict] | None = None,
    timeout: int = 30,
) -> bytes:
    
    endpoint = f"{BROWSERLESS_BASE}/screenshot?token={BROWSERLESS_TOKEN}"
    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
    }

    payload: dict = {
        "url": url,
        "options": {
            "fullPage": True, 
            "type": "png",
            "quality": 90
        },
    }
    if add_script_tag:
        payload["addScriptTag"] = add_script_tag
    if add_style_tag:
        payload["addStyleTag"] = add_style_tag

    resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def capture_responsive_views(url: str) -> Dict[str, str]:
    
    #various screen sizes
    viewports = {
        "mobile": {"width": 375, "height": 667},
        "tablet": {"width": 768, "height": 1024}, 
        "desktop": {"width": 1440, "height": 900}
    }
    
    screenshots = {}
    endpoint = f"{BROWSERLESS_BASE}/screenshot?token={BROWSERLESS_TOKEN}"
    headers = {"Content-Type": "application/json"}
    
    for device, viewport in viewports.items():
        payload = {
            "url": url,
            "options": {
                "fullPage": True,
                "type": "png"
            },
            "viewport": viewport
        }
        
        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            screenshots[device] = base64.b64encode(resp.content).decode()
        except Exception as e:
            screenshots[device] = f"Error: {str(e)}"
    
    return screenshots


def stream_clone_html_enhanced(
    url: str,
    design_context: Dict[str, Any],
    dom_structure: Dict[str, Any],
    screenshots: Dict[str, str],
    *,
    add_script_tag: Optional[List[Dict]] = None,
    add_style_tag: Optional[List[Dict]] = None,
) -> Generator[str, None, None]:
    
    # Use main desktop screenshot
    main_screenshot = screenshots.get("desktop", "")
    if not main_screenshot:
        # Fallback to regular screenshot
        png_b64 = base64.b64encode(
            grab_screenshot(url, add_script_tag=add_script_tag, add_style_tag=add_style_tag)
        ).decode()
    else:
        png_b64 = main_screenshot

    title = design_context.get('title', 'Untitled')
    element_count = len(design_context.get('elementMap', []))
    viewport = design_context.get('viewport', {})
    # Enhanced system prompt with comprehensive context
    system_prompt = f"""You are an expert front-end developer...
Your task is to generate a single, self-contained `<!doctype html>` document that visually and structurally replicates the provided screenshot.

**KEY INFORMATION:**
- **Page Title**: "{title}"
- **Element Count**: The page has roughly {element_count} significant elements.
- **Viewport**: The screenshot was taken at {viewport.get('width')}x{viewport.get('height')} pixels.

**YOUR INSTRUCTIONS:**
1.  **Analyze the Screenshot**: The screenshot is your primary source of truth. Replicate the layout, colors, typography, and spacing you see.
2.  **Use Tailwind CSS**: You MUST use Tailwind CSS for all styling.
3.  **Structure**: Recreate the HTML structure (divs, headings, paragraphs, images) to match the visual hierarchy in the image.
4.  **Content**: Use placeholder text where necessary but try to infer headings and button text from the image.
5.  **Self-Contained HTML**: The final output must be a single HTML file with the Tailwind CDN script.

**GOAL**:
Produce a high-fidelity clone based on the visual information in the screenshot.
"""

    invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Accept": "text/event-stream",
    }

    payload = {
        "model": "mistralai/mistral-medium-3-instruct",
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{png_b64}"
                        },
                    },
                    {
                        "type": "text",
                        "text": f"Please clone this website: {url}. Use all the provided design context to make it as accurate as possible.",
                    },
                ],
            },
        ],
        "stream": True,
        "max_tokens": 4096,
        "temperature": 0.3,  # Lower temperature for more consistent output
        "top_p": 0.9,
    }

    # Stream delta tokens to the caller
    with requests.post(
        invoke_url, headers=headers, json=payload, stream=True, timeout=None
    ) as resp:
        if resp.status_code != 200:
            raise HTTPException(resp.status_code, resp.text)

        for raw in resp.iter_lines():
            if not raw:
                continue
            line = raw.decode("utf-8")
            if line.startswith("data: "):
                data = line[6:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                    delta = obj["choices"][0]["delta"]
                    if (text := delta.get("content")) is not None:
                        yield text
                except (KeyError, json.JSONDecodeError):
                    continue

    yield "\n</html>" #incase llm forgets to close html tag


@app.get("/")
def read_root():
    return {"message": " Orchids Website Cloner"}


@app.post("/analyze")
def analyze_website(url: str = Query(..., pattern="https?://.*")):
    """Analyze website and return comprehensive design context"""
    
    design_context = extract_design_context(url)
    dom_structure = extract_dom_structure(url)
    screenshots = capture_responsive_views(url)
    
    return {
        "url": url,
        "design_context": design_context,
        "dom_structure": dom_structure, 
        "screenshots": screenshots
    }


@app.post("/clone", response_class=StreamingResponse)
def clone_site_enhanced(
    url: str = Query(..., pattern="https?://.*", description="Public webpage URL"),
    add_script_tag: Optional[List[Dict]] = Body(None),
    add_style_tag: Optional[List[Dict]] = Body(None),
):
    """Enhanced cloning with comprehensive design context"""
    
    # Filter out invalid entries
    if add_script_tag:
        add_script_tag = [tag for tag in add_script_tag if tag and any(tag.values())]
    if add_style_tag:
        add_style_tag = [tag for tag in add_style_tag if tag and any(tag.values())]
    
    def generator():
        try:
            # Extract comprehensive design context first
            design_context = extract_design_context(url)
            dom_structure = extract_dom_structure(url)
            screenshots = capture_responsive_views(url)
            
            # Generate enhanced clone
            yield from stream_clone_html_enhanced(
                url,
                design_context,
                dom_structure,
                screenshots,
                add_script_tag=add_script_tag or None,
                add_style_tag=add_style_tag or None,
            )
        except Exception as exc:
            yield f"<!-- Error: {exc} -->"

    return StreamingResponse(generator(), media_type="text/html")


@app.post("/clone-complete")
def clone_site_complete(
    url: str = Query(..., pattern="https?://.*"),
    add_script_tag: Optional[List[Dict]] = Body(None),
    add_style_tag: Optional[List[Dict]] = Body(None),
):
    """Non-streaming version that returns everything at once"""
    
    try:
        # Extract all design context
        design_context = extract_design_context(url)
        dom_structure = extract_dom_structure(url)
        screenshots = capture_responsive_views(url)
        
        # Generate HTML (collecting all streamed content)
        html_parts = []
        for chunk in stream_clone_html_enhanced(
            url, design_context, dom_structure, screenshots,
            add_script_tag=add_script_tag, add_style_tag=add_style_tag
        ):
            html_parts.append(chunk)
        
        html_content = "".join(html_parts)
        
        return {
            "html": html_content,
            "design_context": design_context,
            "dom_structure": dom_structure,
            "screenshots": screenshots,
            "analysis": {
                "colors_found": len(design_context.get('colors', [])),
                "fonts_found": len(design_context.get('fonts', [])),
                "headings_count": len(design_context.get('textContent', {}).get('headings', [])),
                "images_count": len(design_context.get('images', []))
            }
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to clone website: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)


