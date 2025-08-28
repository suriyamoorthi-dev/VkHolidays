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
        products = supabase.table("tours").select("*").eq("is_active", True).execute()
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
    try:
        # Fetch the product
        product = supabase.table("tours").select("*").eq("id", product_id).single().execute().data
        if not product:
            return "Product not found", 404

        if request.method == "POST":
            # Grab form values
            name = request.form.get("name")
            email = request.form.get("email")
            phone = request.form.get("phone")
            travel_date = request.form.get("travel_date")
            people = request.form.get("people")

            # Save booking
            supabase.table("bookings").insert({
                "product_id": product_id,
                "name": name,
                "email": email,
                "phone": phone,
                "travel_date": travel_date,
                "people": people
            }).execute()

            return render_template("success.html", product=product, name=name)

        return render_template("product.html", product=product)

    except Exception as e:
        # Print error in console for debugging
        import traceback
        traceback.print_exc()
        return f"Error loading product {product_id}: {e}", 500

@app.route("/memory-game")
def memory_game():
    return render_template("memory_game.html")  # save your HTML as templates/memory_game.html


# -------------------- Admin Dashboard --------------------

@app.route("/admin")
def admin_dashboard():
    try:
        tours_resp = supabase.table("tours").select("*").execute()
        print("RAW TOURS RESPONSE:", tours_resp)
        tours = tours_resp.data if tours_resp.data else []
        print("PARSED TOURS:", tours)

        total_tours = len(tours)
        total_price = 0.0

        for tour in tours:
            # Handle price safely
            try:
                if tour.get("price") is None:
                    tour["price"] = 0.0
                else:
                    tour["price"] = float(tour["price"])
            except:
                tour["price"] = 0.0

            total_price += tour["price"]

            # Handle images
            if tour.get("images") and isinstance(tour["images"], list):
                tour["images_list"] = tour["images"]
            elif tour.get("image_url"):
                tour["images_list"] = [tour["image_url"]]
            else:
                tour["images_list"] = ["https://via.placeholder.com/150"]

        stats = {
            "total_tours": total_tours,
            "total_price": total_price
        }

        return render_template("admin_tours.html", tours=tours, stats=stats)

    except Exception as e:
        print("Error loading admin dashboard:", e)
        return "Error loading admin dashboard"

@app.route("/emi")
def emi_page():
    try:
        # Fetch all tours
        tours_resp = supabase.table("tours").select("*").execute()
        tours = tours_resp.data if tours_resp.data else []

        # Calculate EMI options for each tour
        for tour in tours:
            price = tour.get("price") or 0
            try:
                price = float(price)
            except:
                price = 0

            tour["emi_options"] = {
                "3 months": round(price / 3, 2),
                "6 months": round(price / 6, 2),
                "12 months": round(price / 12, 2),
            }

        return render_template("emi.html", tours=tours)

    except Exception as e:
        print("Error loading EMI page:", e)
        return "Error loading EMI page"

# -------------------- All Bookings --------------------
@app.route("/admin/bookings")
def admin_bookings():
    try:
        bookings_resp = supabase.table("bookings").select("*").order("created_at", desc=True).execute()
        bookings_data = []

        tours_resp = supabase.table("tours").select("*").execute()
        tours_map = {t["id"]: t for t in tours_resp.data} if tours_resp.data else {}

        if bookings_resp.data:
            for booking in bookings_resp.data:
                items_resp = supabase.table("booking_items").select("*").eq("booking_id", booking["id"]).execute()
                booking_items_list = []
                total_amount = 0

                if items_resp.data:
                    for item in items_resp.data:
                        tour = tours_map.get(item["tour_id"])
                        if tour:
                            price = float(tour.get("price", 0))
                            people = int(item.get("people", 1))
                            subtotal = price * people
                            total_amount += subtotal
                            booking_items_list.append({
                                "tour_name": tour.get("name", "Unknown Tour"),
                                "people": people,
                                "price": price,
                                "subtotal": subtotal
                            })

                bookings_data.append({
                    "booking": booking,
                    "booking_items": booking_items_list,
                    "total_amount": total_amount
                })

        return render_template("bookings.html", bookings=bookings_data)

    except Exception as e:
        print(f"Error fetching bookings: {e}")
        return render_template("bookings.html", bookings=[], error=str(e))

# -------------------- Add Tour --------------------

@app.route("/admin/add-tour", methods=["GET", "POST"])
def add_tour():
    if request.method == "POST":
        try:
            # Safe price conversion
            price = request.form.get("price")
            price = float(price) if price else 0.0

            # Handle multiple images (comma-separated from form)
            images = request.form.get("images", "")
            images_list = [img.strip() for img in images.split(",") if img.strip()]
            if not images_list:
                images_list = ["https://via.placeholder.com/150"]

            # Insert into tours table
            supabase.table("tours").insert({
                "name": request.form.get("name", "Unnamed Tour"),
                "location": request.form.get("location", ""),
                "duration": request.form.get("duration", ""),
                "price": price,
                "images": images_list,        # match DB column
                "description": request.form.get("description", ""),
                "is_active": "is_active" in request.form
            }).execute()

            return redirect(url_for("admin_dashboard"))

        except Exception as e:
            print(f"Error adding tour: {e}")
            return f"Error adding tour: {e}", 500

    return render_template("add_tour.html")

# -------------------- Edit Tour --------------------
@app.route("/admin/edit-tour/<int:tour_id>", methods=["GET", "POST"])
def edit_tour(tour_id):
    if request.method == "POST":
        try:
            supabase.table("tours").update({
                "name": request.form["name"],
                "location": request.form["location"],
                "duration": request.form["duration"],
                "price": float(request.form["price"]),
                "image_urls": request.form["image_urls"],
                "description": request.form["description"],
                "is_active": "is_active" in request.form
            }).eq("id", tour_id).execute()
            return redirect(url_for("admin_dashboard"))
        except Exception as e:
            print(f"Error editing tour: {e}")
            return "Error editing tour", 500

    try:
        tour_resp = supabase.table("tours").select("*").eq("id", tour_id).single().execute()
        return render_template("edit_tour.html", tour=tour_resp.data)
    except Exception as e:
        print(f"Error fetching tour: {e}")
        return "Tour not found", 404

# -------------------- Delete Tour --------------------
@app.route("/admin/delete-tour/<int:tour_id>")
def delete_tour(tour_id):
    try:
        supabase.table("tours").delete().eq("id", tour_id).execute()
        return redirect(url_for("admin_dashboard"))
    except Exception as e:
        print(f"Error deleting tour: {e}")
        return "Error deleting tour", 500

# -------------------- Update Booking Status --------------------
@app.route("/admin/bookings/update/<int:booking_id>/<string:new_status>")
def update_booking_status(booking_id, new_status):
    try:
        supabase.table("bookings").update({"status": new_status}).eq("id", booking_id).execute()
        return redirect(url_for("admin_bookings"))
    except Exception as e:
        print(f"Error updating booking status: {e}")
        return redirect(url_for("admin_bookings"))

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


@app.route("/tours")
def tours():
    # return tours page
    return render_template("tours.html")

@app.route("/bookings")
def bookings():
    # return bookings page
    return render_template("bookings.html")


# ---------------- Run App ----------------

if __name__ == "__main__":
    app.run(debug=True)