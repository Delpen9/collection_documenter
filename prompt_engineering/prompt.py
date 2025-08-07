import base64
import json
import requests
import re

from urllib.parse import quote_plus
from bs4 import BeautifulSoup

from openai import OpenAI
import streamlit as st

# 1) create one client for your app
client = OpenAI(api_key=st.secrets.openai["OPENAI_API_KEY"])

def analyze_item(image_input):
    # normalize to bytes
    if hasattr(image_input, "getvalue"):
        image_bytes = image_input.getvalue()
    elif hasattr(image_input, "read"):
        image_bytes = image_input.read()
    elif isinstance(image_input, (bytes, bytearray)):
        image_bytes = image_input
    else:
        raise TypeError(f"Expected bytes or file-like, got {type(image_input)}")

    # base64 → data URI
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_uri = f"data:image/png;base64,{b64}"

    # 1) CALL VISION MODEL
    try:
        vision_resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content":
                    "You are an assistant that extracts Pokémon card details from an image. "
                    "Output only the raw JSON object with no markdown fences or extra text."},
                {"role": "user", "content":
                    [
                        {"type": "text", "text":
                            "Analyze the image and return JSON with keys 'card_name' and 'set_name'."},
                        {"type": "image_url", "image_url": {"url": data_uri}}
                    ]
                }
            ]
        )
    except RateLimitError:
        st.error("⚠️ OpenAI quota exceeded. Check your plan at platform.openai.com and try again later.")
        return None
    except OpenAIError as e:
        st.error(f"OpenAI API error: {e}")
        return None

    # 2) PARSE JSON SAFELY (strip fences/prefix)
    raw = (vision_resp.choices[0].message.content or "").strip()
    raw = re.sub(r"^```+|```+$", "", raw).strip()
    raw = re.sub(r"^json\s*", "", raw, flags=re.IGNORECASE).strip()
    m = re.search(r"(\{.*\})", raw, flags=re.DOTALL)
    if m:
        raw = m.group(1)
    try:
        card = json.loads(raw)
    except json.JSONDecodeError:
        st.error("Failed to parse JSON from vision model response.")
        st.write("Raw response was:", raw)
        return None

    # 3) SCRAPE EBAY
    query = quote_plus(f"{card['card_name']} {card['set_name']}")
    resp = requests.get(f"https://www.ebay.com/sch/i.html?_nkw={query}&LH_Complete=1&LH_Sold=1")
    soup = BeautifulSoup(resp.text, "html.parser")
    sold = []
    for item in soup.select(".s-item")[:5]:
        sold.append({
            "title": item.select_one(".s-item__title").text,
            "price": item.select_one(".s-item__price").text,
            "date": item.select_one(".s-item__subtitle").text,
            "url": item.select_one(".s-item__link")["href"]
        })

    # 4) FINAL GPT CALL WITH SAME GUARDING
    prompt = (
        f"Card: {card['card_name']} ({card['set_name']}); "
        f"Sold listings: {sold}. "
        "Suggest an eBay title (≤60 chars), estimate a selling price, "
        "and list any important notes. Return exactly one JSON object "
        "with keys 'suggested_item_title', 'ai_suggested_price', and 'item_notes', "
        "and no additional text."
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

    final_raw = (final.choices[0].message.content or "").strip()
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

    return {
        "suggested_item_title": result["suggested_item_title"],
        "last_5_sold_listings": sold,
        "ai_suggested_price": result["ai_suggested_price"],
        "item_notes": result["item_notes"]
    }