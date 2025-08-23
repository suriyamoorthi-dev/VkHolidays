from flask import Flask, render_template, request, redirect, url_for, jsonify
from supabase import create_client
import os
from datetime import datetime

app = Flask(__name__)

# ---------------- Supabase Config ----------------
SUPABASE_URL = "https://mmhvljqdyzskxnzkrgql.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1taHZsanFkeXpza3huemtyZ3FsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTEyMTAwOTcsImV4cCI6MjA2Njc4NjA5N30.gtVE8Dg4fdf37xEAAghgrMjyIpOZOTnIuOFn0qk59uM"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- DEBUG ROUTES ----------------
@app.route("/debug/orders")
def debug_orders():
    """Debug route to check orders data"""
    try:
        # Check if orders table has data
        orders = supabase.table("orders").select("*").execute()
        orders_count = len(orders.data) if orders.data else 0
        
        # Check if order_items table has data  
        items = supabase.table("order_items").select("*").execute()
        items_count = len(items.data) if items.data else 0
        
        return jsonify({
            "orders_count": orders_count,
            "items_count": items_count,
            "orders": orders.data,
            "items": items.data,
            "status": "success"
        })
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"})

@app.route("/debug/test-insert")
def test_insert():
    """Test inserting a dummy order"""
    try:
        # Insert test order
        order = supabase.table("orders").insert({
            "customer_name": "Test Customer",
            "phone": "1234567890",
            "address": "Test Address",
            "total": 100.0,
            "status": "Pending"
        }).execute()
        
        if order.data:
            order_id = order.data[0]["id"]
            
            # Insert test item
            item = supabase.table("order_items").insert({
                "order_id": order_id,
                "product_id": 1,
                "product_name": "Test Product",
                "grams": "250g",
                "price": 50.0,
                "quantity": 2
            }).execute()
            
            return jsonify({
                "status": "success",
                "order": order.data,
                "item": item.data
            })
        else:
            return jsonify({"status": "error", "message": "Order insert failed"})
            
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"})

# ---------------- USER SIDE ----------------

@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/home")
def home():
    """Show only active products to customers"""
    try:
        products = supabase.table("products").select("*").eq("is_active", True).execute()
        return render_template("index.html", products=products.data or [])
    except Exception as e:
        print(f"Error in home: {e}")
        return render_template("index.html", products=[])

@app.route("/order", methods=["POST"])
def place_order():
    """Place new order"""
    try:
        data = request.get_json()
        print(f"📦 Order data received: {data}")

        # ✅ Validate required fields
        required_fields = ["name", "phone", "address", "items"]
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    "success": False,
                    "error": f"Missing required field: {field}"
                }), 400

        name = data.get("name")
        phone = data.get("phone")
        address = data.get("address")
        items = data.get("items", [])

        if not items:
            return jsonify({
                "success": False,
                "error": "No items in order"
            }), 400

        # 🧮 Auto calculate total
        total = 0
        for item in items:
            price = float(item.get("price") or 0)
            qty = int(item.get("qty") or 1)
            total += price * qty

        print(f"🧮 Calculated total: {total}")

        # 1️⃣ Insert into orders table
        order_data = {
            "customer_name": name,
            "phone": phone,
            "address": address,
            "total": total,
            "status": "Pending"
        }

        print(f"📝 Inserting order: {order_data}")
        order = supabase.table("orders").insert(order_data).execute()

        if not order.data:
            print("❌ Order insert failed")
            return jsonify({
                "success": False,
                "error": "Order insert failed"
            }), 400

        order_id = order.data[0]["id"]
        print(f"✅ Order created with ID: {order_id}")

        # 2️⃣ Insert each item into order_items
        for item in items:
            item_data = {
                "order_id": order_id,
                "product_id": item.get("id"),
                "grams": float(item.get("grams") or 0),
                "price": float(item.get("price") or 0),
                "quantity": int(item.get("qty") or 1)
            }

            print(f"📦 Inserting item: {item_data}")
            result = supabase.table("order_items").insert(item_data).execute()

            if result.data:
                print(f"✅ Item inserted: {result.data[0]['id']}")
            else:
                print(f"❌ Item insert failed for: {item_data}")

        return jsonify({
            "success": True,
            "order_id": order_id,
            "total": total,
            "message": "Order placed successfully!"
        }), 200

    except Exception as e:
        print(f"❌ Error in place_order: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500

@app.route("/product/<int:product_id>", methods=["GET", "POST"])
def product_page(product_id):
    """Public product page with reviews"""
    try:
        product = supabase.table("products").select("*").eq("id", product_id).single().execute()
        if not product.data:
            return "Product not found", 404

        if request.method == "POST":
            name = request.form.get("name")
            rating = int(request.form.get("rating", 5))
            comment = request.form.get("comment", "")

            supabase.table("reviews").insert({
                "product_id": product_id,
                "name": name,
                "rating": rating,
                "comment": comment
            }).execute()

            return redirect(f"/product/{product_id}")

        # Fetch reviews
        reviews = (
            supabase.table("reviews")
            .select("*")
            .eq("product_id", product_id)
            .order("created_at", desc=True)
            .execute()
        )

        return render_template(
            "product_page.html",
            product=product.data,
            reviews=reviews.data or []
        )
    except Exception as e:
        print(f"Error in product_page: {e}")
        return "Error loading product", 500

@app.route("/memory-game")
def memory_game():
    return render_template("memory_game.html")  # save your HTML as templates/memory_game.html

# ---------------- ADMIN SIDE ----------------

@app.route("/admin")
def admin_dashboard():
    try:
        # Fetch all products at once
        products_resp = supabase.table("products").select("*").execute()
        products = products_resp.data if products_resp.data else []

        # Ensure every product has a valid image_url
        for product in products:
            image_url = product.get("image_url")
            if not image_url or not image_url.strip():
                # Fallback to safe online placeholder
                product["image_url"] = "https://via.placeholder.com/150"

        # Create a lookup dict for faster access by product ID
        products_map = {p["id"]: p for p in products}

        # Fetch recent orders
        orders_resp = supabase.table("orders").select("*").order("created_at", desc=True).limit(10).execute()
        orders_data = []

        if orders_resp.data:
            for order in orders_resp.data:
                order_id = order["id"]

                # Fetch items for this order
                order_items_resp = supabase.table("order_items").select("*").eq("order_id", order_id).execute()
                order_items_list = []
                order_total = 0

                if order_items_resp.data:
                    for item in order_items_resp.data:
                        product = products_map.get(item["product_id"])
                        if product:
                            price = float(product.get("price", 0))
                            qty = int(item.get("quantity", 1))
                            subtotal = price * qty
                            order_total += subtotal

                            order_items_list.append({
                                "product_name": product.get("name", "Unknown Product"),
                                "grams": item.get("grams", ""),
                                "price": price,
                                "quantity": qty,
                                "subtotal": subtotal
                            })

                orders_data.append({
                    "order": order,
                    "order_items": order_items_list,
                    "order_total": order_total
                })

        # Calculate stats
        stats = {
            "total_products": len(products),
            "pending_orders": sum(1 for o in orders_data if o["order"].get("status", "").lower() == "pending"),
            "completed_orders": sum(1 for o in orders_data if o["order"].get("status", "").lower() == "completed"),
            "total_revenue": sum(o["order_total"] for o in orders_data if o["order"].get("status", "").lower() == "completed")
        }

        return render_template("admin.html", products=products, orders=orders_data, stats=stats)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return render_template(
            "admin.html",
            products=[],
            orders=[],
            stats={
                "total_products": 0,
                "pending_orders": 0,
                "completed_orders": 0,
                "total_revenue": 0
            }
        )

@app.route("/admin/orders")
def admin_orders():
    """Show all orders with items"""
    try:
        print("🔍 Fetching orders...")
        
        # Fetch all orders
        orders = supabase.table("orders") \
            .select("*") \
            .order("created_at", desc=True) \
            .execute()

        print(f"📊 Orders found: {len(orders.data) if orders.data else 0}")

        orders_data = []

        if orders.data:
            for order in orders.data:
                print(f"🔄 Processing order ID: {order['id']}")
                
                # Fetch items for this order
                items = supabase.table("order_items") \
                    .select("*") \
                    .eq("order_id", order["id"]) \
                    .execute()

                print(f"📦 Items found for order {order['id']}: {len(items.data) if items.data else 0}")

                formatted_items = []
                calculated_total = 0

                if items.data:
                    for item in items.data:
                        price = float(item.get("price", 0))
                        quantity = int(item.get("quantity", 1))
                        subtotal = price * quantity
                        calculated_total += subtotal

                        formatted_items.append({
                            "name": item.get("product_name", "Unknown Product"),
                            "grams": item.get("grams", ""),
                            "price": price,
                            "quantity": quantity,
                            "subtotal": subtotal
                        })

                # Use stored total or calculated total
                final_total = order.get("total", calculated_total)

                orders_data.append({
                    "order": order,
                    "items": formatted_items,
                    "total": final_total
                })

        print(f"✅ Final orders processed: {len(orders_data)}")
        return render_template("orders.html", orders=orders_data)
        
    except Exception as e:
        print(f"❌ Error in admin_orders: {str(e)}")
        return render_template("orders.html", orders=[], error=str(e))

@app.route("/admin/add", methods=["GET", "POST"])
def add_product():
    """Add new product"""
    if request.method == "POST":
        try:
            supabase.table("products").insert({
                "name": request.form["name"],
                "description": request.form["description"],
                "grams": request.form["grams"],
                "price": float(request.form["price"]),
                "image_url": request.form["image_url"],
                "is_active": True
            }).execute()
            return redirect(url_for("admin_dashboard"))
        except Exception as e:
            print(f"Error adding product: {e}")
            return "Error adding product", 500

    return render_template("add_product.html")

@app.route("/admin/edit/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):
    """Edit product"""
    if request.method == "POST":
        try:
            supabase.table("products").update({
                "name": request.form["name"],
                "description": request.form["description"],
                "grams": request.form["grams"],
                "price": float(request.form["price"]),
                "image_url": request.form["image_url"],
                "is_active": "is_active" in request.form
            }).eq("id", product_id).execute()
            return redirect(url_for("admin_dashboard"))
        except Exception as e:
            print(f"Error editing product: {e}")
            return "Error editing product", 500

    try:
        product = supabase.table("products").select("*").eq("id", product_id).single().execute()
        return render_template("edit_product.html", product=product.data)
    except Exception as e:
        print(f"Error fetching product: {e}")
        return "Product not found", 404

@app.route("/admin/delete/<int:product_id>")
def delete_product(product_id):
    """Delete product"""
    try:
        supabase.table("products").delete().eq("id", product_id).execute()
        return redirect(url_for("admin_dashboard"))
    except Exception as e:
        print(f"Error deleting product: {e}")
        return "Error deleting product", 500
    
@app.route("/admin/orders/update/<int:order_id>/<string:new_status>")
def update_order_status(order_id, new_status):
    """Update order status (Pending → Shipped → Completed)"""
    try:
        # Only update the status, do not delete order or items
        supabase.table("orders").update({"status": new_status}).eq("id", order_id).execute()
        print(f"✅ Order {order_id} status updated to {new_status}")

        return redirect(url_for("admin_orders"))
    except Exception as e:
        print(f"❌ Error updating order status: {e}")
        return redirect(url_for("admin_orders"))

# ---------------- API ROUTES ----------------
@app.route("/api/orders")
def api_orders():
    """API endpoint to get orders as JSON"""
    try:
        orders = supabase.table("orders").select("*").execute()
        return jsonify({
            "success": True,
            "count": len(orders.data) if orders.data else 0,
            "orders": orders.data or []
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })

@app.route("/contact")
def contact():
    # You can add emails or contact info here
    contacts = {
        "Support": "support@example.com",
        "Sales": "sales@example.com",
        "General": "info@example.com"
    }
    return render_template("contact.html", contacts=contacts)

@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/course")
def course():
    return render_template("course.html")


# ---------------- Run App ----------------

if __name__ == "__main__":
    app.run(debug=True)