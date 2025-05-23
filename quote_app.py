import streamlit as st
from fpdf import FPDF
import pandas as pd
import json
import re
from collections import defaultdict

# --- Load Machine Configurations ---
with open("all_machine_configs.json") as f:
    machine_configs = json.load(f)

# --- Helper to clean standard options ---
def clean_standard_options(options):
    cleaned = []
    for opt in options:
        if not opt:
            continue
        text = str(opt)
        text = re.sub(r'\bnan\b', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+', ' ', text).strip()
        if text:
            cleaned.append(text)
    return cleaned

# --- Group optional options and extract base price if present ---
def group_optional_options(options):
    categories = defaultdict(list)
    cleaned_options = []

    for opt in options:
        opt['description'] = re.sub(r'\bnan\b', '', str(opt['description'])).strip()
        if not opt['description']:
            continue
        cleaned_options.append(opt)

    base_price = 0
    if cleaned_options and (
        "base price" in cleaned_options[0]['description'].lower()
        or "model" in cleaned_options[0]['description'].lower()
        or (cleaned_options[0]['price'] > 100000 and len(cleaned_options[0]['description'].split()) < 3)
    ):
        base_price = cleaned_options[0]['price']
        cleaned_options = cleaned_options[1:]

    for opt in cleaned_options:
        desc = opt['description'].lower()
        if 'spindle' in desc:
            categories['Spindle Options'].append(opt)
        elif 'probe' in desc or 'renishaw' in desc:
            categories['Probing & Measurement'].append(opt)
        elif 'coolant' in desc:
            categories['Coolant Systems'].append(opt)
        elif 'table' in desc or 'pallet' in desc:
            categories['Table & Pallet Systems'].append(opt)
        elif 'tool' in desc and ('storage' in desc or 'magazine' in desc or 'changer' in desc):
            categories['Tool Storage'].append(opt)
        elif 'control' in desc:
            categories['Control Options'].append(opt)
        else:
            categories['Other Options'].append(opt)

    return categories, base_price

# --- PDF Generator ---
class QuotePDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Mitsui Seiki USA - Machine Quote', ln=True, align='C')
        self.ln(10)

    def add_quote(self, customer_name, machine_type, base_price, discount, std_opts, selected_opts, total):
    	self.set_font("Arial", size=12)
    	self.cell(0, 10, f"Customer: {customer_name}", ln=True)
    	self.cell(0, 10, f"Machine: {machine_type}", ln=True)
    	self.cell(0, 10, f"Base Machine Price: ${base_price:,.2f}", ln=True)
    	self.cell(0, 10, f"Standard Discount: -${discount:,.2f}", ln=True)
    	self.ln(5)

    	self.set_font("Arial", 'B', 12)
    	self.cell(0, 10, "Standard Options:", ln=True)
    	self.set_font("Arial", size=12)
    	for opt in std_opts:
        	self.multi_cell(0, 10, f"- {opt}")
    	self.ln(5)

    	self.set_font("Arial", 'B', 12)
    	self.cell(0, 10, "Selected Optional Upgrades:", ln=True)
    	self.set_font("Arial", size=12)
    	grouped, _ = group_optional_options(selected_opts)
    	for group, items in grouped.items():
        	self.set_font("Arial", 'B', 11)
        	self.cell(0, 10, f"{group}:", ln=True)
        	self.set_font("Arial", size=12)
        	for opt in items:
            		self.cell(0, 10, f"- {opt['description']} (${opt['price']:,.2f})", ln=True)
        	self.ln(2)

    	self.ln(5)
    	self.cell(0, 10, f"Total Quote: ${total:,.2f}", ln=True)


# --- Streamlit UI ---
st.set_page_config(page_title="Quote Builder", layout="centered")
st.title("Mitsui Seiki - Quote Builder")

customer_name = st.text_input("Customer Name")
machine_type = st.selectbox("Select Machine Type", sorted(machine_configs.keys()))

standard_options = clean_standard_options(machine_configs[machine_type]['standard_options'])
optional_options = machine_configs[machine_type]['optional_options']

# Re-group with base price extraction
grouped_options, extracted_base_price = group_optional_options(optional_options)
base_price = extracted_base_price if extracted_base_price > 0 else machine_configs[machine_type]['base_price']

# --- Discount Input Controls ---
st.subheader("Discount Options")
with st.expander("Apply Discount"):
    desired_price = st.number_input("Enter Desired Final Price (Optional)", min_value=0.0, format="%.2f")
    percent_discount = st.number_input("Discount Percentage (%)", min_value=0.0, max_value=100.0, format="%.2f")
    flat_discount = st.number_input("Flat Discount Amount ($)", min_value=0.0, format="%.2f")

# Calculate effective discount
if desired_price > 0:
    discount = max(0, base_price - desired_price)
elif percent_discount > 0:
    discount = (percent_discount / 100) * base_price
elif flat_discount > 0:
    discount = flat_discount
else:
    discount = machine_configs[machine_type]['discount']

custom_price = base_price - discount

# --- Standard Features Display ---
st.subheader("Standard Features (Included)")
for item in standard_options:
    st.markdown(f"- {item}")

# --- Optional Upgrades ---
st.subheader("Optional Upgrades")
selected_addons = []
for group, options in grouped_options.items():
    st.markdown(f"**{group}**")
    for i, opt in enumerate(options):
        key = f"{machine_type}_{group}_{i}"
        if st.checkbox(f"{opt['description']} (+${opt['price']:,.2f})", key=key):
            selected_addons.append(opt)
            custom_price += opt['price']

# --- Generate PDF ---
if st.button("Generate Quote PDF"):
    pdf = QuotePDF()
    pdf.add_page()
    pdf.add_quote(customer_name or "[Customer Name]", machine_type, base_price, discount, standard_options, selected_addons, custom_price)

    pdf_output_path = "quote_output.pdf"
    pdf.output(pdf_output_path)
    st.success("Quote generated successfully!")
    st.download_button("Download Quote PDF", open(pdf_output_path, "rb"), file_name="Mitsui_Quote.pdf")
