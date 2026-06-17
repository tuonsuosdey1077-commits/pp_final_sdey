from flask import Flask, render_template, request, make_response, redirect, url_for
from products import products
import json
import requests

app = Flask(__name__)

# --- TELEGRAM BOT Info ---
BOT_TOKEN = "8633332207:AAENKDOH3S9oP10b63VVHyvrfI9suZYgJlk"
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
CHAT_ID = "@pp_sdey_group"


@app.context_processor
def inject_cart_count():
    cart_cookie = request.cookies.get('cart')
    cart_data = {}
    if cart_cookie:
        try:
            cart_data = json.loads(cart_cookie)
        except json.JSONDecodeError:
            pass
    
    total_qty = 0
    if isinstance(cart_data, dict):
        for val in cart_data.values():
            try:
                total_qty += int(val)
            except (ValueError, TypeError):
                pass
    return dict(cart_count=total_qty)


@app.route('/')
def index():
    return render_template('front/index.html', products=products)


@app.route('/products_page')
def products_page():
    return render_template('front/products.html', products=products)


@app.route('/product-detail/<int:product_id>')
def product_detail(product_id):
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        return "Product not found", 404

    related_products = [
        p for p in products
        if p["category"] == product["category"] and p["id"] != product["id"]][:4]

    return render_template(
        'front/product_detail.html',
        product=product,
        related_products=related_products
    )


@app.route('/add-to-cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        return "Product not found", 404

    cart_cookie = request.cookies.get('cart')
    cart = json.loads(cart_cookie) if cart_cookie else {}

    quantity = int(request.form.get('quantity', 1))
    product_id_str = str(product_id)
    if product_id_str in cart:
        cart[product_id_str] += quantity
    else:
        cart[product_id_str] = quantity

    response = make_response(redirect(url_for('cart')))
    response.set_cookie('cart', json.dumps(cart), max_age=30 * 24 * 60 * 60, httponly=True)
    return response


@app.route('/cart')
def cart():
    cart_cookie = request.cookies.get('cart')
    cart_data = {}
    if cart_cookie:
        try:
            cart_data = json.loads(cart_cookie)
        except json.JSONDecodeError:
            pass

    cart_items = []
    total_price = 0

    for product_id_str, quantity in cart_data.items():
        product = next((p for p in products if str(p["id"]) == product_id_str), None)
        if product:
            item_total = product['price'] * quantity
            total_price += item_total
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'item_total': round(item_total, 2)
            })

    return render_template(
        'front/cart.html',
        cart_items=cart_items,
        total_price=round(total_price, 2)
    )


@app.route('/checkout')
def checkout():
    cart_cookie = request.cookies.get('cart')
    cart = json.loads(cart_cookie) if cart_cookie else {}

    cart_items = []
    total_price = 0

    for product_id_str, quantity in cart.items():
        product = next((p for p in products if str(p["id"]) == product_id_str), None)
        if product:
            item_total = product['price'] * quantity
            total_price += item_total
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'item_total': round(item_total, 2)
            })

    if not cart_items:
        return redirect(url_for('products_page'))

    return render_template(
        'front/checkout.html',
        cart_items=cart_items,
        total_price=round(total_price, 2)
    )


@app.route('/update-cart/<int:product_id>/<action>', methods=['POST'])
def update_cart(product_id, action):
    cart_cookie = request.cookies.get('cart')
    cart = json.loads(cart_cookie) if cart_cookie else {}

    product_id_str = str(product_id)

    if product_id_str in cart:
        if action == 'increase':
            cart[product_id_str] += 1
        elif action == 'decrease':
            cart[product_id_str] -= 1
            if cart[product_id_str] <= 0:
                cart.pop(product_id_str, None)

    response = make_response(redirect(url_for('cart')))
    response.set_cookie('cart', json.dumps(cart), max_age=30 * 24 * 60 * 60, httponly=True)
    return response


@app.route('/remove-from-cart/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    cart_cookie = request.cookies.get('cart')
    cart = json.loads(cart_cookie) if cart_cookie else {}

    product_id_str = str(product_id)
    cart.pop(product_id_str, None)

    response = make_response(redirect(url_for('cart')))
    response.set_cookie('cart', json.dumps(cart), max_age=30 * 24 * 60 * 60, httponly=True)
    return response


# --- FIXED: PLACE ORDER ROUTE ---
@app.route('/place_order', methods=['POST'])
def place_order():
    buyer_name = request.form.get('buyer_name')
    buyer_phone = request.form.get('buyer_phone')
    buyer_email = request.form.get('buyer_email')
    buyer_address = request.form.get('buyer_address')
    order_notes = request.form.get('order_notes', 'N/A')

    # Fallback to make sure buyer name is never empty text
    if not buyer_name or buyer_name.strip() == "":
         buyer_name = "Anonymous Buyer"

    cart_cookie = request.cookies.get('cart')
    cart = json.loads(cart_cookie) if cart_cookie else {}

    if not cart:
        return redirect(url_for('cart'))

    total_price = 0
    item_list_text = ""

    for item_id_str, quantity in cart.items():
        product = next((item for item in products if str(item['id']) == item_id_str), None)
        if product:
            item_total = product['price'] * quantity
            total_price += item_total

            item_list_text += f"📦 <b>{product['title'][:25]}...</b>\n"
            item_list_text += f"   └ Qty: {quantity} × ${product['price']:.2f} = <b>${item_total:.2f}</b>\n\n"

    final_grand_total = total_price + 120.00

    telegram_text = f"<b>🔔 NEW KHQR ORDER RECEIVED</b>\n"
    telegram_text += f"<b>----------------------------------</b>\n\n"
    telegram_text += f"👤 <b>Customer:</b> {buyer_name}\n"
    telegram_text += f"📞 <b>Phone:</b> <code>{buyer_phone}</code>\n"
    telegram_text += f"📧 <b>Email:</b> <code>{buyer_email}</code>\n"
    telegram_text += f"📍 <b>Address:</b> {buyer_address}\n"
    telegram_text += f"📝 <b>Notes:</b> <i>{order_notes}</i>\n\n"
    telegram_text += f"<b>🛒 ORDER ITEMS:</b>\n"
    telegram_text += item_list_text
    telegram_text += f"<b>----------------------------------</b>\n"
    telegram_text += f"💰 <b>TOTAL PAID (KHQR): ${final_grand_total:.2f} USD</b>"

    payload = {
        "text": telegram_text,
        "parse_mode": "HTML",
        "chat_id": CHAT_ID
    }

    headers = {
        "accept": "application/json",
        "content-type": "application/json"
    }

    try:
        telegram_response = requests.post(TELEGRAM_URL, json=payload, headers=headers)
        print(f"Telegram Bot Status: {telegram_response.status_code}")
    except Exception as e:
        print(f"Failed to push notification to Telegram: {e}")

    # Success output returns script redirection straight to base domain homepage root
    response = make_response(
        '<script>alert("KHQR Payment Received! Order sent to our team."); window.location="/";</script>')
    response.delete_cookie('cart')
    return response


@app.route('/login')
def login():
    return render_template('front/login.html')


@app.route('/create-user')
def create_user():
    return render_template('front/create-user.html')


@app.route('/forgot-password')
def forgot_password():
    return render_template('front/forgot-password.html')


@app.route('/account')
def account():
    return render_template('front/account.html')


@app.route('/about')
def about():
    return render_template('front/about.html')


@app.route('/contact')
def contact():
    return render_template('front/contact.html')


if __name__ == '__main__':
    app.run(debug=True)