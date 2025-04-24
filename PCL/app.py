# SmartCart Application 

import streamlit as st
import pandas as pd
import requests
from pyzbar import pyzbar
import cv2
import numpy as np
import os
#hi i'm samith 
# --- Constants ---
DB_FILE = 'products.csv'
OFF_API_URL = "https://world.openfoodfacts.org/api/v2/product/{}.json"

# --- Database Functions ---
def load_db():
    """Loads the product database from CSV."""
    if os.path.exists(DB_FILE):
        try:
            return pd.read_csv(DB_FILE).set_index('barcode')
        except pd.errors.EmptyDataError:
            return pd.DataFrame(columns=['name', 'price']).set_index(pd.Index([], name='barcode'))
        except Exception as e:
            st.error(f"Error loading database: {e}")
            return pd.DataFrame(columns=['name', 'price']).set_index(pd.Index([], name='barcode'))
    else:
        # Create the file with header if it doesn't exist
        df = pd.DataFrame(columns=['barcode', 'name', 'price'])
        df.to_csv(DB_FILE, index=False)
        return df.set_index('barcode')

def save_product_to_db(barcode, name, price):
    """Saves or updates a product in the CSV database."""
    db = load_db().reset_index() # Load and reset index to treat barcode as a column
    product_data = {'barcode': barcode, 'name': name, 'price': float(price)}

    # Check if barcode exists
    if barcode in db['barcode'].values:
        # Update existing product
        db.loc[db['barcode'] == barcode, ['name', 'price']] = [name, float(price)]
    else:
        # Add new product - use pd.concat instead of append
        new_product_df = pd.DataFrame([product_data])
        db = pd.concat([db, new_product_df], ignore_index=True)

    try:
        db.to_csv(DB_FILE, index=False)
        st.session_state.product_db = load_db() # Reload db in session state
        st.success(f"Product '{name}' saved to local database.")
    except Exception as e:
        st.error(f"Error saving product to database: {e}")


# --- API Function ---
def fetch_product_from_off(barcode):
    """Fetches product details from OpenFoodFacts API."""
    try:
        response = requests.get(OFF_API_URL.format(barcode))
        response.raise_for_status() # Raise an exception for bad status codes
        data = response.json()
        if data.get("status") == 1 and data.get("product"):
            product = data["product"]
            name = product.get("product_name", "N/A")
            # Price is not reliably available in OFF
            # We will prioritize manual entry or leave price blank
            return {"name": name, "price": None}
        else:
            return None
    except requests.exceptions.RequestException as e:
        st.warning(f"Could not connect to OpenFoodFacts API: {e}")
        return None
    except Exception as e:
        st.error(f"Error fetching data from OpenFoodFacts: {e}")
        return None

# --- Barcode Decoding ---
def decode_barcode(image):
    """Decodes barcodes from an uploaded image or camera frame."""
    try:
        if isinstance(image, np.ndarray):
            # If image is already a numpy array (from webcam)
            img = image
        else:
            # Convert the uploaded file buffer to a NumPy array
            filestr = image.read()
            npimg = np.frombuffer(filestr, np.uint8)
            # Decode the image using OpenCV
            img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
            if img is None:
                st.error("Could not decode image. Please ensure it's a valid image file.")
                return None

        barcodes = pyzbar.decode(img)
        if barcodes:
            # Return the data of the first detected barcode
            return barcodes[0].data.decode('utf-8')
        else:
            return None
    except Exception as e:
        st.error(f"Error processing image: {e}")
        return None

# --- Streamlit App ---
st.set_page_config(page_title="SmartCart", layout="wide")
st.title("🛒 SmartCart")

# Initialize session state
if 'cart' not in st.session_state:
    st.session_state.cart = []
if 'product_db' not in st.session_state:
    st.session_state.product_db = load_db()
if 'last_scanned_barcode' not in st.session_state:
    st.session_state.last_scanned_barcode = None
if 'last_product_info' not in st.session_state:
    st.session_state.last_product_info = None
if 'show_manual_entry' not in st.session_state:
    st.session_state.show_manual_entry = False
if 'use_camera' not in st.session_state:
    st.session_state.use_camera = False

# --- Layout ---
col1, col2 = st.columns([2, 1]) # Scanner/Product Info | Cart

with col1:
    st.header("Scan Product")
    
    # Toggle between camera and file upload
    st.session_state.use_camera = st.checkbox("Use Webcam", value=st.session_state.use_camera)
    
    product_info_placeholder = st.empty()
    
    if st.session_state.use_camera:
        # Webcam input
        FRAME_WINDOW = st.image([])
        cap = cv2.VideoCapture(0)
        
        if st.button("Scan Barcode"):
            ret, frame = cap.read()
            if ret:
                # Convert BGR to RGB
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                FRAME_WINDOW.image(frame)
                
                barcode = decode_barcode(frame)
                if barcode:
                    st.session_state.last_scanned_barcode = barcode
                    st.session_state.last_product_info = None
                    st.session_state.show_manual_entry = False
                    st.info(f"Detected Barcode: {barcode}")
                    
                    # Process barcode (same logic as file upload)
                    if barcode in st.session_state.product_db.index:
                        product_info = st.session_state.product_db.loc[barcode].to_dict()
                        product_info['source'] = 'Local DB'
                        st.session_state.last_product_info = product_info
                        st.session_state.show_manual_entry = False
                    else:
                        with st.spinner("Searching OpenFoodFacts..."):
                            product_info = fetch_product_from_off(barcode)
                        if product_info:
                            product_info['source'] = 'OpenFoodFacts'
                            if product_info.get('price') is None:
                                st.warning("Product found on OpenFoodFacts, but price is missing. Please enter manually if needed.")
                                st.session_state.show_manual_entry = True
                            else:
                                st.session_state.show_manual_entry = False
                            st.session_state.last_product_info = product_info
                        else:
                            st.warning(f"Product with barcode {barcode} not found in local DB or OpenFoodFacts.")
                            st.session_state.show_manual_entry = True
                else:
                    st.error("No barcode detected. Please try again.")
            else:
                st.error("Failed to access webcam")
        
        cap.release()
    else:
        # File uploader
        uploaded_file = st.file_uploader("Upload Barcode Image", type=["png", "jpg", "jpeg"], key="file_uploader")
        
        if uploaded_file is not None:
            barcode = decode_barcode(uploaded_file)
            st.session_state.last_scanned_barcode = barcode
            st.session_state.last_product_info = None
            st.session_state.show_manual_entry = False

            if barcode:
                st.info(f"Detected Barcode: {barcode}")
                
                # 1. Check Local DB
                if barcode in st.session_state.product_db.index:
                    product_info = st.session_state.product_db.loc[barcode].to_dict()
                    product_info['source'] = 'Local DB'
                    st.session_state.last_product_info = product_info
                    st.session_state.show_manual_entry = False
                
                # 2. Check OpenFoodFacts API
                else:
                    with st.spinner("Searching OpenFoodFacts..."):
                        product_info = fetch_product_from_off(barcode)
                    if product_info:
                        product_info['source'] = 'OpenFoodFacts'
                        if product_info.get('price') is None:
                            st.warning("Product found on OpenFoodFacts, but price is missing. Please enter manually if needed.")
                            st.session_state.show_manual_entry = True
                        else:
                            st.session_state.show_manual_entry = False
                        st.session_state.last_product_info = product_info
                    else:
                        st.warning(f"Product with barcode {barcode} not found in local DB or OpenFoodFacts.")
                        st.session_state.show_manual_entry = True
            else:
                st.error("No barcode detected in the uploaded image.")
                st.session_state.last_scanned_barcode = None
                st.session_state.last_product_info = None
                st.session_state.show_manual_entry = False


    # --- Display Product Info / Manual Entry ---
    with product_info_placeholder.container():
        if st.session_state.last_product_info:
            st.subheader("Product Details")
            info = st.session_state.last_product_info
            st.markdown(f"**Name:** {info.get('name', 'N/A')}")
            st.markdown(f"**Price:** {f'${info.get("price"):.2f}' if info.get('price') is not None else 'N/A'}")
            st.markdown(f"**Source:** {info.get('source', 'N/A')}")

            if st.button("Add to Cart", key="add_cart_button"):
                if info.get('price') is not None:
                    cart_item = {
                        "barcode": st.session_state.last_scanned_barcode,
                        "name": info.get('name', 'N/A'),
                        "price": float(info.get('price')),
                        "quantity": 1 # Start with quantity 1
                    }
                    # Check if item already in cart
                    found = False
                    for item in st.session_state.cart:
                        if item['barcode'] == cart_item['barcode']:
                            item['quantity'] += 1
                            found = True
                            break
                    if not found:
                        st.session_state.cart.append(cart_item)
                    st.success(f"Added {info.get('name', 'N/A')} to cart.")
                    # Clear last scan info to prevent re-adding on refresh
                    # st.session_state.last_product_info = None
                    # st.session_state.last_scanned_barcode = None
                    st.rerun() # Rerun to update cart display immediately
                else:
                    st.error("Cannot add item to cart without a price. Please enter manually.")
                    st.session_state.show_manual_entry = True # Show manual entry if trying to add without price


        # --- Manual Entry Form ---
        if st.session_state.show_manual_entry and st.session_state.last_scanned_barcode:
            st.subheader(f"Add/Update Product: {st.session_state.last_scanned_barcode}")
            with st.form(key="manual_entry_form"):
                manual_name = st.text_input("Product Name", value=st.session_state.last_product_info.get('name', '') if st.session_state.last_product_info else '')
                manual_price = st.number_input("Product Price ($)", min_value=0.0, format="%.2f", value=st.session_state.last_product_info.get('price') if st.session_state.last_product_info and st.session_state.last_product_info.get('price') is not None else 0.0)
                submit_manual = st.form_submit_button("Save to Local DB")

                if submit_manual:
                    if manual_name and manual_price > 0:
                        save_product_to_db(st.session_state.last_scanned_barcode, manual_name, manual_price)
                        # Update last_product_info with manually entered data
                        st.session_state.last_product_info = {
                             'name': manual_name,
                             'price': manual_price,
                             'source': 'Manual Entry'
                        }
                        st.session_state.show_manual_entry = False # Hide form after saving
                        st.rerun() # Rerun to show updated product info and hide form
                    else:
                        st.error("Please enter both name and a valid price.")


with col2:
    st.header("Shopping Cart")
    cart_placeholder = st.empty()

    if not st.session_state.cart:
        cart_placeholder.info("Your cart is empty.")
    else:
        cart_df = pd.DataFrame(st.session_state.cart)
        cart_df['Total'] = cart_df['price'] * cart_df['quantity']

        # Display Cart Items with +/- buttons and remove button
        new_cart = []
        items_to_remove = [] # Keep track of indices to remove

        for i, item in enumerate(st.session_state.cart):
            item_cols = st.columns([3, 1, 1, 1, 1, 1]) # Name, Price, Qty-, Qty, Qty+, Remove
            item_cols[0].write(f"{item['name']}")
            item_cols[1].write(f"${item['price']:.2f}")
            if item_cols[2].button("-", key=f"dec_{i}"):
                if item['quantity'] > 1:
                    item['quantity'] -= 1
                    st.rerun()
                else:
                    # Mark for removal if quantity becomes 0
                    items_to_remove.append(i)

            item_cols[3].write(f"{item['quantity']}")

            if item_cols[4].button("+", key=f"inc_{i}"):
                item['quantity'] += 1
                st.rerun()

            if item_cols[5].button("🗑️", key=f"rem_{i}"):
                items_to_remove.append(i)

        # Process removals after iterating
        if items_to_remove:
             # Remove items in reverse order to avoid index issues
            for index in sorted(items_to_remove, reverse=True):
                 del st.session_state.cart[index]
            st.rerun()


        # Recalculate cart total after potential updates
        if st.session_state.cart: # Check if cart is not empty after removals
            cart_df = pd.DataFrame(st.session_state.cart)
            cart_df['Total'] = cart_df['price'] * cart_df['quantity']
            total_price = cart_df['Total'].sum()
            st.subheader(f"Total: ${total_price:.2f}")
        else:
            cart_placeholder.info("Your cart is empty.") # Update placeholder if cart becomes empty


    if st.session_state.cart:
        if st.button("Clear Cart", key="clear_cart"):
            st.session_state.cart = []
            st.rerun()

st.divider()
st.subheader("Local Product Database")
st.dataframe(st.session_state.product_db, use_container_width=True)

st.caption("Powered by Streamlit, OpenFoodFacts, pyzbar, OpenCV") 
