import base64
import json
import requests
import re

from urllib.parse import quote_plus
from bs4 import BeautifulSoup

from openai import OpenAI, OpenAIError, RateLimitError
import streamlit as st

# 1) create one client for your app
client = OpenAI(api_key=st.secrets.openai["OPENAI_API_KEY"])

def analyze_item(image_input):
    # ——————————————
    # 1) Normalize to bytes
    if hasattr(image_input, "getvalue"):
        image_bytes = image_input.getvalue()
    elif hasattr(image_input, "read"):
        image_bytes = image_input.read()
    elif isinstance(image_input, (bytes, bytearray)):
        image_bytes = image_input
    else:
        raise TypeError(f"Expected bytes or file-like, got {type(image_input)}")

    # 2) Base64 → data URI
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_uri = f"data:image/png;base64,{b64}"

    # 3) CALL VISION MODEL (now asking for an optional 'grade')
    try:
        vision_resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content":
                    "You are an assistant that extracts item details from an image. "
                    "Output only the raw JSON object with no markdown or extra text."},
                {"role": "user", "content": [
                    {"type": "text", "text":
                        "Analyze the image and return JSON with keys:\n"
                        "- 'item_name'\n"
                        "- 'item_type'\n"
                        "- if applicable 'set_name'\n"
                        "- if applicable 'grade' (e.g. 'PSA 10', 'BGS 9.6', 'CGC 9')."},
                    {"type": "image_url", "image_url": {"url": data_uri}}
                ]}
            ]
        )
    except RateLimitError:
        st.error("⚠️ OpenAI quota exceeded. Try again later.")
        return None
    except OpenAIError as e:
        st.error(f"OpenAI API error: {e}")
        return None

    # 4) Parse JSON safely
    raw = vision_resp.choices[0].message.content or ""
    raw = re.sub(r"^```+|```+$", "", raw).strip()
    raw = re.sub(r"^json\s*", "", raw, flags=re.IGNORECASE).strip()
    m = re.search(r"(\{.*\})", raw, flags=re.DOTALL)
    if m:
        raw = m.group(1)
    try:
        item = json.loads(raw)
    except json.JSONDecodeError:
        st.error("Failed to parse JSON from vision model response.")
        st.write("Raw response was:", raw)
        return None

    # 5) SCRAPE EBAY for last 5 sold listings
    query_str = " ".join(filter(None, [
        item["item_name"],
        item.get("set_name", "")
    ]))
    resp = requests.get(
        f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(query_str)}&LH_Complete=1&LH_Sold=1"
    )
    soup = BeautifulSoup(resp.text, "html.parser")
    sold = []
    for listing in soup.select(".s-item")[:5]:
        sold.append({
            "title": listing.select_one(".s-item__title").text,
            "price": listing.select_one(".s-item__price").text,
            "date": listing.select_one(".s-item__subtitle").text,
            "url": listing.select_one(".s-item__link")["href"]
        })

    # ——————————————
    # 6) Compute ai_estimated_price (weighted toward higher values)
    prices = []
    for s in sold:
        m_price = re.search(r"[\d,]+\.?\d*", s["price"])
        if m_price:
            prices.append(float(m_price.group(0).replace(",", "")))

    if prices:
        numerator   = sum(p * p for p in prices)
        denominator = sum(prices)
        ai_price    = round(numerator / denominator, 2)
    else:
        ai_price = None

    # ——————————————
    # 7) FINAL GPT CALL for documentation title & rich notes
    #    Include grade in the title if present.
    title_prefix = item["item_name"]
    if item.get("set_name"):
        title_prefix += f" ({item['set_name']})"
    if item.get("grade"):
        title_prefix += f" — {item['grade']}"

    prompt = (
        f"Item: {title_prefix}; Sold listings: {sold}. "
        "Provide:\n"
        "1) A concise title for documentation (≤100 chars),\n"
        "2) Detailed notes about this collectible (≤500 chars) covering historical context, "
        "apparent condition, and any other observations visible in the image.\n"
        "Return exactly one JSON object with keys 'suggested_item_title' and 'item_notes', "
        "and no extra text or listing instructions."
    )
    try:
        final = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
    except RateLimitError:
        st.error("⚠️ OpenAI quota exceeded on final call.")
        return None
    except OpenAIError as e:
        st.error(f"OpenAI API error: {e}")
        return None

    # 8) Parse final JSON
    final_raw = final.choices[0].message.content or ""
    final_raw = re.sub(r"^```+|```+$", "", final_raw).strip()
    final_raw = re.sub(r"^json\s*", "", final_raw, flags=re.IGNORECASE).strip()
    m = re.search(r"(\{.*\})", final_raw, flags=re.DOTALL)
    if m:
        final_raw = m.group(1)
    try:
        result = json.loads(final_raw)
    except json.JSONDecodeError:
        st.error("Failed to parse JSON from final model response.")
        st.write("Raw response was:", final_raw)
        return None

    # 9) Return enriched output
    return {
        "suggested_item_title": result["suggested_item_title"],
        "last_5_sold_listings": sold,
        "ai_estimated_price": ai_price,
        "item_notes": result["item_notes"]
    }