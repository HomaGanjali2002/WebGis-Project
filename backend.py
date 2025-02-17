from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
import geopandas as gpd
import pandas as pd
from sqlalchemy.sql import text
from sqlalchemy import create_engine, MetaData, Table
import psycopg2

# Connect to database
DATABASE_URL = 'postgresql://postgres:13792000Sh@localhost/postgis_main'
engine = create_engine(DATABASE_URL)

# Function to load data from the database
def load_data_from_db():
    try:
        gdf = gpd.read_postgis("SELECT * FROM taxi_zones", engine, geom_col="geometry")
        forecast_df = pd.read_sql("SELECT * FROM forecast_data", engine, index_col="day_hour")
        return gdf, forecast_df

    except Exception as e:
        print(f"Database Error: {e}")
        return None, None

# Load data globally
gdf, forecast_df = load_data_from_db()

# Function to update taxi_demand in the taxi_zones table based on forecast data
def update_taxi_demand(day, hour):
    if gdf is None or forecast_df is None:
        return "Database not loaded"

    # Filter data based on day and hour
    selected_data = forecast_df[(forecast_df['day'] == day) & (forecast_df['hour'] == hour)]

    if selected_data.empty:
        return f"No data available for the selected date and time."

    forecast_data = {int(col.split("_")[1]): selected_data.iloc[0][col] for col in forecast_df.columns if col not in ['day_hour', 'day', 'hour']}
    print("Forecast data:", forecast_data)  # Debug: print the forecast data

    try:
        with engine.connect() as connection:
            updated_rows = 0
            for location_id, demand in forecast_data.items():
                demand_float = float(demand)
                query = text('''UPDATE public.taxi_zones SET taxi_demand = :demand WHERE "LocationID" = :location_id''')
                result = connection.execute(query, {"demand": demand_float, "location_id": location_id})
                updated_rows += result.rowcount
            connection.commit()
        return f"Updated successfully. Rows affected: {updated_rows}"
    except Exception as e:
        return f"Database update error: {e}"

# Function to get taxi demand aggregated by landuse from the database
def get_demand_by_landuse():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        query = """
        SELECT land_use, SUM(taxi_demand) AS total_demand
        FROM taxi_zones
        GROUP BY land_use
        """
        cursor.execute(query)
        results = cursor.fetchall()
        conn.close()
        return [{"landuse": row[0], "total_demand": row[1]} for row in results]
    except Exception as e:
        return f"Error fetching landuse data: {e}"

app = Flask(__name__)
app.secret_key = '13791381ShH'

# Home route: redirect to login page
@app.route('/')
def home():
    return redirect(url_for('login'))

# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if not username or not password:
            flash("Please enter a username and password.")
            return redirect(url_for('register'))
        password_hash = generate_password_hash(password)
        conn = engine.raw_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (%s, %s, %s)", (username, password_hash, False))
            conn.commit()
            flash("Registration successful. Please log in.")
        except Exception as e:
            flash(f"Error: {e}")
            return redirect(url_for('register'))
        finally:
            conn.close()
        return redirect(url_for('login'))
    return render_template('register.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = engine.raw_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        conn.close()
        if user:
            stored_password_hash = user[2]
            if check_password_hash(stored_password_hash, password):
                session['user_id'] = user[0]
                session['is_admin'] = user[3]
                return redirect(url_for('map'))
            else:
                flash("Invalid username or password. Please try again.")
                return redirect(url_for('login'))
        else:
            flash("No user found with that username. Please register first.")
            return redirect(url_for('register'))
    return render_template('login.html')

# Logout route
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('is_admin', None)
    flash("You have been logged out.")
    return redirect(url_for('login'))

# Admin route: manage users and database tables (for admins only)
@app.route('/admin')
def admin():
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Unauthorized access.")
        return redirect(url_for('login'))
    conn = engine.raw_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, is_admin FROM users")
    users = cursor.fetchall()
    conn.close()
    tables = get_all_tables()
    return render_template('admin.html', users=users, tables=tables)

# Delete user route (for admins only)
@app.route('/admin/delete_user/<int:user_id>')
def delete_user(user_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Unauthorized access.")
        return redirect(url_for('login'))
    conn = engine.raw_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()
    flash("User deleted successfully.")
    return redirect(url_for('admin'))

# Map route: render the map page (for authenticated users)
@app.route('/map')
def map():
    if 'user_id' not in session:
        flash("Please log in first.")
        return redirect(url_for('login'))
    return render_template('map.html')

# API route to update taxi_demand based on user input (day and hour)
@app.route('/api/update_taxi_demand', methods=['GET'])
def update_taxi_demand_api():
    day = request.args.get('day')
    hour = request.args.get('hour')
    result = update_taxi_demand(day, hour)
    return jsonify({"message": result})

# API route to get taxi demand aggregated by landuse
@app.route('/api/landuse_demand', methods=['GET'])
def landuse_demand_api():
    result = get_demand_by_landuse()
    if isinstance(result, str):
        return jsonify({"error": result}), 500
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=False)
