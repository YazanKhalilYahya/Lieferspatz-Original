from flask import Flask, request, jsonify
from datetime import datetime
from classes import Customer, Restaurant, MenuItem, Order
from db import init_db, insert_data  # Import the functions from db.py

app = Flask(__name__)

# Initialize the database and insert sample data when the app starts
init_db()
# insert_data()

# In-memory storage (replace with real DB in production)
restaurants = {}
customers = {}
orders = []
menu_items = {}
notifications = []
lieferspatz_balance = 0  # Global balance for Lieferspatz


@app.route('/customer', methods=['POST'])
def create_customer():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid or missing JSON payload'}), 400

        # Validate required fields
        required_fields = ['first_name', 'last_name', 'address', 'zip_code', 'password']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400

        # Extract data
        first_name = data['first_name']
        last_name = data['last_name']
        address = data['address']
        zip_code = data['zip_code']
        password = data['password']

        # Generate the customer ID dynamically
        customer_id = len(customers) + 1

        # Create and store new customer
        customer = Customer(customer_id, first_name, last_name, address, zip_code, password)
        customers[customer_id] = customer

        return jsonify({'success': True, 'customer_id': customer.id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500



# Customer Login (authenticate)
@app.route('/customer/login', methods=['POST'])
def login_customer():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid or missing JSON payload'}), 400

        # Extract credentials
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        password = data.get('password')

        # Validate credentials
        for customer in customers.values():
            if (
                customer.first_name == first_name
                and customer.last_name == last_name
                and customer.password == password
            ):
                return jsonify({'success': True, 'customer_id': customer.id})

        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Create a new restaurant account
@app.route('/restaurant', methods=['POST'])
def create_restaurant():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid or missing JSON payload'}), 400

        # Extract restaurant data
        name = data.get('name')
        address = data.get('address')
        description = data.get('description')
        password = data.get('password')

        if not all([name, address, description, password]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Create new restaurant
        restaurant_id = len(restaurants) + 1
        restaurant = Restaurant(name, address, description, password)
        restaurant.id = restaurant_id
        restaurants[restaurant_id] = restaurant

        return jsonify({'success': True, 'restaurant_id': restaurant.id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Add an item to the restaurant's menu
@app.route('/restaurant/<int:restaurant_id>/menu', methods=['POST'])
def add_menu_item(restaurant_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid or missing JSON payload'}), 400

        # Extract menu item data
        name = data.get('name')
        description = data.get('description')
        price = data.get('price')
        image = data.get('image', None)

        if not all([name, description, price]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Find the restaurant
        restaurant = restaurants.get(restaurant_id)
        if not restaurant:
            return jsonify({'success': False, 'message': 'Restaurant not found'}), 404

        # Create menu item
        menu_item = MenuItem(name, description, price, image)
        restaurant.menu.append(menu_item)
        menu_items[menu_item.id] = menu_item

        return jsonify({'success': True, 'item_id': menu_item.id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Create a new order (from a customer)
@app.route('/order', methods=['POST'])
def create_order():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid or missing JSON payload'}), 400

        # Extract order data
        customer_id = data.get('customer_id')
        restaurant_id = data.get('restaurant_id')
        items = data.get('items')

        customer = customers.get(customer_id)
        restaurant = restaurants.get(restaurant_id)

        if not customer:
            return jsonify({'success': False, 'message': 'Customer not found'}), 404
        if not restaurant:
            return jsonify({'success': False, 'message': 'Restaurant not found'}), 404

        # Create the order with status 'in Bearbeitung'
        order = Order(customer_id, restaurant_id, items)
        customer.orders.append(order)
        restaurant.orders.append(order)
        orders.append(order)

        # Process the payment for the order
        if not order.process_payment():
            return jsonify({'success': False, 'message': 'Insufficient balance to complete the payment.'}), 400

        return jsonify({'success': True, 'order_id': len(orders)}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# View a customer's order history
@app.route('/customer/<int:customer_id>/orders', methods=['GET'])
def view_order_history(customer_id):
    try:
        customer = customers.get(customer_id)

        if not customer:
            return jsonify({'success': False, 'message': 'Customer not found'}), 404

        # Sort orders by status (pending first)
        sorted_orders = sorted(
            customer.orders, key=lambda x: (x.status != 'in Bearbeitung', x.timestamp)
        )

        order_details = []
        for i, order in enumerate(sorted_orders, start=1):  # Fix for 1-based indexing
            order_details.append({
                'order_id': i,
                'restaurant_name': restaurants[order.restaurant_id].name,
                'items': order.items,
                'total_price': order.total_price(),
                'status': order.status,
                'timestamp': order.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            })

        return jsonify({'orders': order_details})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Get the status of a specific order (customer's view)
@app.route('/customer/<int:customer_id>/order/<int:order_id>', methods=['GET'])
def get_order_status(customer_id, order_id):
    try:
        customer = customers.get(customer_id)

        if not customer:
            return jsonify({'success': False, 'message': 'Customer not found'}), 404

        if order_id > len(customer.orders) or order_id <= 0:
            return jsonify({'success': False, 'message': 'Order not found'}), 404

        order = customer.orders[order_id - 1]  # 1-based order ID

        return jsonify({
            'order_id': order_id,
            'status': order.status,
            'restaurant_name': restaurants[order.restaurant_id].name,
            'items': order.items,
            'total_price': order.total_price(),
            'timestamp': order.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Get customer's wallet balance
@app.route('/customer/<int:customer_id>/wallet', methods=['GET'])
def get_wallet_balance(customer_id):
    try:
        customer = customers.get(customer_id)
        if not customer:
            return jsonify({'success': False, 'message': 'Customer not found'}), 404

        return jsonify({'wallet_balance': customer.wallet_balance})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Get restaurant's wallet balance
@app.route('/restaurant/<int:restaurant_id>/wallet', methods=['GET'])
def get_restaurant_wallet_balance(restaurant_id):
    try:
        restaurant = restaurants.get(restaurant_id)
        if not restaurant:
            return jsonify({'success': False, 'message': 'Restaurant not found'}), 404

        return jsonify({'wallet_balance': restaurant.wallet_balance})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Get global Lieferspatz wallet balance
@app.route('/lieferspatz/wallet', methods=['GET'])
def get_lieferspatz_wallet_balance():
    return jsonify({'lieferspatz_wallet_balance': lieferspatz_balance})


if __name__ == '__main__':
    app.run(debug=True)
