"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
from pathlib import Path
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# MongoDB configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = "mergington_high_school"
ACTIVITIES_COLLECTION = "activities"

# MongoDB client
client = None
database = None
activities_collection = None

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# Sample activities data to populate MongoDB
SAMPLE_ACTIVITIES = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    # Sport-related activities
    "Soccer Team": {
        "description": "Join the school soccer team and compete in local leagues",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["lucas@mergington.edu", "mia@mergington.edu"]
    },
    "Basketball Club": {
        "description": "Practice basketball skills and play friendly matches",
        "schedule": "Wednesdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["liam@mergington.edu", "ava@mergington.edu"]
    },  
    # Artistic activities
    "Art Club": {
        "description": "Explore painting, drawing, and other visual arts",
        "schedule": "Mondays, 3:30 PM - 5:00 PM",
        "max_participants": 18,
        "participants": ["noah@mergington.edu", "isabella@mergington.edu"]
    },
    "Drama Society": {
        "description": "Participate in acting, stage production, and school plays",
        "schedule": "Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ethan@mergington.edu", "charlotte@mergington.edu"]
    },
    # Intellectual activities
    "Debate Club": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 16,
        "participants": ["amelia@mergington.edu", "jack@mergington.edu"]
    },
    "Math Olympiad": {
        "description": "Prepare for math competitions and solve challenging problems",
        "schedule": "Wednesdays, 3:30 PM - 5:00 PM",
        "max_participants": 14,
        "participants": ["benjamin@mergington.edu", "harper@mergington.edu"]
    }
}


@app.on_event("startup")
async def startup_event():
    """Initialize MongoDB connection and populate with sample data"""
    global client, database, activities_collection
    
    try:
        # Try to connect to MongoDB with a timeout
        client = AsyncIOMotorClient(MONGODB_URL, serverSelectionTimeoutMS=3000)
        database = client[DATABASE_NAME]
        activities_collection = database[ACTIVITIES_COLLECTION]
        
        # Test the connection with timeout
        await asyncio.wait_for(client.admin.command('ping'), timeout=3.0)
        logger.info("Successfully connected to MongoDB")
        
        # Check if collection is empty and populate with sample data
        count = await asyncio.wait_for(activities_collection.count_documents({}), timeout=3.0)
        if count == 0:
            logger.info("Populating MongoDB with sample activities...")
            # Convert dictionary to list of documents
            activities_docs = []
            for name, data in SAMPLE_ACTIVITIES.items():
                doc = {"name": name, **data}
                activities_docs.append(doc)
            
            await asyncio.wait_for(activities_collection.insert_many(activities_docs), timeout=5.0)
            logger.info(f"Inserted {len(activities_docs)} sample activities")
        else:
            logger.info("MongoDB already contains activities data")
            
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        logger.info("Falling back to in-memory storage")
        # Fall back to in-memory storage
        client = None
        database = None
        activities_collection = None


@app.on_event("shutdown")
async def shutdown_event():
    """Close MongoDB connection"""
    global client
    if client:
        client.close()
        logger.info("MongoDB connection closed")


async def get_activities_from_db():
    """Get all activities from MongoDB or fallback to in-memory"""
    if activities_collection is not None:
        try:
            activities_cursor = activities_collection.find({})
            activities_list = await activities_cursor.to_list(length=None)
            # Convert back to dictionary format expected by frontend
            activities_dict = {}
            for activity in activities_list:
                name = activity.pop("name")
                activity.pop("_id", None)  # Remove MongoDB's _id field
                activities_dict[name] = activity
            return activities_dict
        except Exception as e:
            logger.error(f"Error fetching from MongoDB: {e}")
            # Fall back to sample data
            return SAMPLE_ACTIVITIES
    else:
        # Use in-memory data when MongoDB is not available
        return SAMPLE_ACTIVITIES


async def update_activity_in_db(activity_name: str, email: str):
    """Add participant to activity in MongoDB"""
    if activities_collection is not None:
        try:
            result = await activities_collection.update_one(
                {"name": activity_name},
                {"$addToSet": {"participants": email}}  # $addToSet prevents duplicates
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating MongoDB: {e}")
            return False
    else:
        # Fall back to in-memory update
        if activity_name in SAMPLE_ACTIVITIES:
            if email not in SAMPLE_ACTIVITIES[activity_name]["participants"]:
                SAMPLE_ACTIVITIES[activity_name]["participants"].append(email)
                return True
        return False


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
async def get_activities():
    """Get all available activities"""
    return await get_activities_from_db()


@app.post("/activities/{activity_name}/signup")
async def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity"""
    # Get current activities to validate
    activities = await get_activities_from_db()
    
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]
    
    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(status_code=400, detail="Student is already signed up")
    
    # Check if activity is full
    if len(activity["participants"]) >= activity["max_participants"]:
        raise HTTPException(status_code=400, detail="Activity is full")

    # Add student to activity
    success = await update_activity_in_db(activity_name, email)
    
    if success:
        return {"message": f"Signed up {email} for {activity_name}"}
    else:
        raise HTTPException(status_code=500, detail="Failed to sign up for activity")
