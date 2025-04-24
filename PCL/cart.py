import streamlit as st
import cv2
import numpy as np
from PIL import Image
from pyzbar.pyzbar import decode
import requests
from bs4 import BeautifulSoup
from serpapi import GoogleSearch

# API Keys
SERPAPI_KEY = "adc1b9e08ef3c152297452ab527f36497e519d0e3ee5852ea040de8a2c8d9fd6"

def search_google_product(barcode):
    """Fetch product details from Google using SerpAPI"""
    params = {
        "engine": "google",
        "q": barcode,  
        "api_key": SERPAPI_KEY
    }
    
    search = GoogleSearch(params)
    results = search.get_dict()  
    
    if "organic_results" in results:
        for result in results["organic_results"]:
            title = result.get("title", "Unknown Product")
            link = result.get("link", "#")
            return {"name": title, "link": link}
    
    return {"name": "Unknown Product", "link": "#"}

def get_flipkart_price(product_name):
    """Fetch product price from Flipkart"""
    search_url = f"https://www.flipkart.com/search?q={product_name.replace(' ', '+')}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    response = requests.get(search_url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    
    price_tag = soup.find("div", {"class": "_30jeq3 _1_WHN1"})  # Flipkart price class
    if price_tag:
        return price_tag.text.strip().replace("₹", "").replace(",", "")
    
    return "N/A"

def decode_barcode(image):
    """Detect and decode barcode from the image"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    barcodes = decode(gray)

    if not barcodes:
        st.error("No barcode detected.")
        return None
    
    for barcode in barcodes:
        barcode_data = barcode.data.decode("utf-8")
        st.success(f"Scanned Barcode: {barcode_data}")

        # Fetch product details
        product = search_google_product(barcode_data)

        if product:
            product_name = product["name"]
            price = get_flipkart_price(product_name)

            st.write(f"**Product:** {product_name}")
            st.write(f"**Price:** ₹{price}")
            st.write(f"[🔗 View on Google]({product['link']})")

            if st.button(f"Add {product_name} to Cart"):
                st.session_state.cart.append({"name": product_name, "price": price})
                st.success(f"Added {product_name} to cart!")

        return barcode_data

# Streamlit UI
st.title("📦 SmartCart - Barcode Scanner")
st.markdown("Scan or upload a barcode to fetch product details from Google & Flipkart.")

# Shopping Cart (Session State)
if "cart" not in st.session_state:
    st.session_state.cart = []

# Webcam Capture
capture = st.camera_input("Scan Barcode using Webcam")

# Upload Image Option
uploaded_file = st.file_uploader("Or Upload a Barcode Image", type=["jpg", "png", "jpeg"])

# Process Uploaded Image
if uploaded_file:
    img = Image.open(uploaded_file)
    img = np.array(img)
    decode_barcode(img)

# Process Webcam Image
if capture:
    img = Image.open(capture)
    img = np.array(img)
    decode_barcode(img)

# Show Shopping Cart
if st.session_state.cart:
    st.subheader("🛒 Shopping Cart")
    total_price = 0
    
    for item in st.session_state.cart:
        st.write(f"**{item['name']}** - ₹{item['price']}")
        try:
            total_price += float(item['price']) if item['price'] != "N/A" else 0
        except ValueError:
            pass
    
    st.write(f"**Total Price:** ₹{total_price}")

    # Remove items option
    if st.button("Clear Cart"):
        st.session_state.cart = []
        st.success("Cart cleared!")

