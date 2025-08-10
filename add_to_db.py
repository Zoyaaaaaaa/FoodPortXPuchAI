import uuid
import json
import sqlite3

# Define your role constants
RESTAURANT_ROLE = "restaurant"
NGO_ROLE = "ngo"

# Example database connection helper
class DBHelper:
    def __init__(self, db_path="DB_v2.db"):
        self.db_path = db_path

    def get_connection(self):
        return sqlite3.connect(self.db_path)

db = DBHelper()

async def populate_mumbai_data():
    """Add real Mumbai-based restaurants and NGOs to the database"""
    print("🌆 Populating Mumbai data...")
    
    # Real Mumbai restaurants with actual locations
    mumbai_restaurants = [
        {
            "name": "The Bombay Canteen",
            "phone": "+919876543210",
            "address": "Unit 1, Process House, Kamala Mills, SB Marg, Lower Parel, Mumbai 400013",
            "geo_lat": 19.0021,
            "geo_lng": 72.8277,
            "cuisine_types": ["Indian", "Contemporary"],
            "daily_capacity": 150,
            "avg_waste_percentage": 12.5
        },
        {
            "name": "Trishna Restaurant",
            "phone": "+919876543211",
            "address": "7 Sai Baba Marg, Kala Ghoda, Fort, Mumbai 400001",
            "geo_lat": 18.9286,
            "geo_lng": 72.8315,
            "cuisine_types": ["Seafood", "Mangalorean"],
            "daily_capacity": 120,
            "avg_waste_percentage": 10.0
        },
        {
            "name": "Gajalee",
            "phone": "+919876543212",
            "address": "16, CST Road, Near Vidyavihar Station, Vidyavihar West, Mumbai 400086",
            "geo_lat": 19.0775,
            "geo_lng": 72.8960,
            "cuisine_types": ["Seafood", "Malvani"],
            "daily_capacity": 200,
            "avg_waste_percentage": 15.0
        },
        {
            "name": "Shree Thaker Bhojanalay",
            "phone": "+919876543213",
            "address": "31, Dadiseth Agyari Lane, Kalbadevi, Mumbai 400002",
            "geo_lat": 18.9522,
            "geo_lng": 72.8324,
            "cuisine_types": ["Gujarati", "Vegetarian"],
            "daily_capacity": 180,
            "avg_waste_percentage": 8.0
        },
        {
            "name": "Britannia & Co. Restaurant",
            "phone": "+919876543214",
            "address": "Wakefield House, 11 Sprott Road, Ballard Estate, Fort, Mumbai 400001",
            "geo_lat": 18.9340,
            "geo_lng": 72.8348,
            "cuisine_types": ["Parsi", "Iranian"],
            "daily_capacity": 100,
            "avg_waste_percentage": 5.0
        }
    ]
    
    # Real Mumbai NGOs with actual locations
    mumbai_ngos = [
        {
            "name": "Akshaya Patra Foundation",
            "phone": "+919876543220",
            "address": "Plot No. 1, Sector 11, CBD Belapur, Navi Mumbai 400614",
            "geo_lat": 19.0236,
            "geo_lng": 73.0396,
            "beneficiary_count": 5000,
            "meal_capacity_per_day": 10000,
            "focus_areas": ["Child Nutrition", "Education"]
        },
        {
            "name": "Robin Hood Army",
            "phone": "+919876543221",
            "address": "Various locations across Mumbai",
            "geo_lat": 19.0760,
            "geo_lng": 72.8777,
            "beneficiary_count": 2000,
            "meal_capacity_per_day": 5000,
            "focus_areas": ["Homeless", "Hunger Relief"]
        },
        {
            "name": "Feeding India",
            "phone": "+919876543222",
            "address": "C-354, Defence Colony, Santacruz East, Mumbai 400055",
            "geo_lat": 19.0834,
            "geo_lng": 72.8431,
            "beneficiary_count": 3000,
            "meal_capacity_per_day": 7000,
            "focus_areas": ["Food Rescue", "Hunger Relief"]
        },
        {
            "name": "Yashodhan Charitable Trust",
            "phone": "+919876543223",
            "address": "Bldg No. 2, Flat No. 5, Shanti Nagar, Mira Road East, Thane 401107",
            "geo_lat": 19.2823,
            "geo_lng": 72.8674,
            "beneficiary_count": 800,
            "meal_capacity_per_day": 1500,
            "focus_areas": ["Elderly Care", "Community Meals"]
        },
        {
            "name": "No Food Waste",
            "phone": "+919876543224",
            "address": "Mumbai Central, Mumbai 400008",
            "geo_lat": 18.9700,
            "geo_lng": 72.8200,
            "beneficiary_count": 1500,
            "meal_capacity_per_day": 3000,
            "focus_areas": ["Food Recovery", "Hunger Relief"]
        }
    ]
    
    with db.get_connection() as conn:
        conn.execute('PRAGMA foreign_keys = ON;')
        
        # Add restaurants
        for restaurant in mumbai_restaurants:
            try:
                conn.execute('''
                    INSERT OR IGNORE INTO restaurants (
                        id, name, phone, address, geo_lat, geo_lng,
                        cuisine_types, daily_capacity, avg_waste_percentage
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    str(uuid.uuid4()),
                    restaurant["name"],
                    restaurant["phone"],
                    restaurant["address"],
                    restaurant["geo_lat"],
                    restaurant["geo_lng"],
                    json.dumps(restaurant["cuisine_types"]),
                    restaurant["daily_capacity"],
                    restaurant["avg_waste_percentage"]
                ))
                
                # Add restaurant role
                conn.execute('''
                    INSERT OR IGNORE INTO user_permissions (
                        id, phone, role, granted_by
                    )
                    VALUES (?, ?, ?, ?)
                ''', (
                    str(uuid.uuid4()),
                    restaurant["phone"],
                    RESTAURANT_ROLE,
                    "system"
                ))
            except sqlite3.IntegrityError:
                print(f"⚠️ Restaurant already exists: {restaurant['name']}")
        
        # Add NGOs
        for ngo in mumbai_ngos:
            try:
                conn.execute('''
                    INSERT OR IGNORE INTO ngos (
                        id, name, phone, address, geo_lat, geo_lng,
                        beneficiary_count, daily_meal_capacity, focus_areas
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    str(uuid.uuid4()),
                    ngo["name"],
                    ngo["phone"],
                    ngo["address"],
                    ngo["geo_lat"],
                    ngo["geo_lng"],
                    ngo["beneficiary_count"],
                    ngo["meal_capacity_per_day"],
                    json.dumps(ngo["focus_areas"])
                ))
                
                # Add NGO role
                conn.execute('''
                    INSERT OR IGNORE INTO user_permissions (
                        id, phone, role, granted_by
                    )
                    VALUES (?, ?, ?, ?)
                ''', (
                    str(uuid.uuid4()),
                    ngo["phone"],
                    NGO_ROLE,
                    "system"
                ))
            except sqlite3.IntegrityError:
                print(f"⚠️ NGO already exists: {ngo['name']}")
        
        conn.commit()
    
    print(f"✅ Added {len(mumbai_restaurants)} restaurants and {len(mumbai_ngos)} NGOs")

# Example usage:
import asyncio
asyncio.run(populate_mumbai_data())
