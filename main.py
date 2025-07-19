from flask import Flask, render_template, request, send_from_directory, redirect, url_for, flash, session
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import img_to_array, load_img
import numpy as np
import os
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import datetime
from bson.objectid import ObjectId

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev')
# MongoDB connection
try:
    MONGO_URI = os.environ.get('MONGO_URI')
    client = MongoClient(MONGO_URI)
    # Test the connection
    client.admin.command('ping')
    print("Successfully connected to MongoDB")
    db = client['brainbuddy']
    users = db['users']
    analysis_results = db['analysis_results']  # New collection for storing analysis results
except Exception as e:
    print(f"Error connecting to MongoDB: {str(e)}")
    raise  # Re-raise the exception to prevent the app from starting with a broken database connection

# Load the trained model
model = load_model('models/model.h5')

# Class labels
class_labels = ['pituitary', 'glioma', 'notumor', 'meningioma']

# Define the uploads folder
UPLOAD_FOLDER = './uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('signin'))
        return f(*args, **kwargs)
    return decorated_function

# Helper function to predict tumor type
def predict_tumor(image_path):
    image_size = 128
    img = load_img(image_path, target_size=(image_size, image_size))
    img_array = img_to_array(img) / 255.0  # Normalize pixel values
    img_array = np.expand_dims(img_array, axis=0)  # Add batch dimension

    predictions = model.predict(img_array)
    predicted_class_index = np.argmax(predictions, axis=1)[0]
    confidence_score = np.max(predictions, axis=1)[0]

    if class_labels[predicted_class_index] == 'notumor':
        return "No Tumor", confidence_score
    else:
        return f"Tumor: {class_labels[predicted_class_index]}", confidence_score

# Authentication routes
@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = users.find_one({'email': email})
        
        if user and check_password_hash(user['password'], password):
            session['user'] = {
                'id': str(user['_id']),
                'name': user['name'],
                'email': user['email']
            }
            return redirect(url_for('landing'))
        else:
            return render_template('signin.html', error='Invalid email or password')
    
    return render_template('signin.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            return render_template('signup.html', error='Passwords do not match')
        
        if users.find_one({'email': email}):
            return render_template('signup.html', error='Email already registered')
        
        hashed_password = generate_password_hash(password)
        user = {
            'name': name,
            'email': email,
            'password': hashed_password
        }
        
        users.insert_one(user)
        return redirect(url_for('signin'))
    
    return render_template('signup.html')

@app.route('/signout')
def signout():
    session.pop('user', None)
    return redirect(url_for('landing'))

# Route for the landing page (homepage)
@app.route('/', methods=['GET'])
def landing():
    return render_template('landing.html')

# Route for the About page
@app.route('/about', methods=['GET'])
def about():
    return render_template('about.html')

# Route for the Blog page
@app.route('/blog', methods=['GET'])
def blog():
    return render_template('blog.html')

# Route for individual blog posts
@app.route('/blog/1')
def blog1():
    return render_template('blog1.html')

@app.route('/blog/2')
def blog2():
    return render_template('blog2.html')

@app.route('/blog/3')
def blog3():
    return render_template('blog3.html')

# Route for the MRI Tumor Detection System (upload form)
@app.route('/detect', methods=['GET', 'POST'])
@login_required
def detect():
    if request.method == 'POST':
        # Handle file upload
        file = request.files['file']
        if file:
            # Save the file
            file_location = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_location)

            # Predict the tumor
            result, confidence = predict_tumor(file_location)

            # Store the analysis result in the database
            try:
                analysis_data = {
                    'user_id': session['user']['id'],
                    'image_path': file_location,
                    'result': result,
                    'confidence': float(confidence),
                    'timestamp': datetime.datetime.utcnow()
                }
                insert_result = analysis_results.insert_one(analysis_data)
                if not insert_result.acknowledged:
                    print("Warning: Analysis result insertion was not acknowledged by MongoDB")
                else:
                    print(f"Successfully saved analysis result with ID: {insert_result.inserted_id}")
            except Exception as e:
                print(f"Error saving analysis result to MongoDB: {str(e)}")
                # Continue with the response even if saving fails
                pass

            # Return result along with image path for display
            return render_template('index.html', result=result, confidence=f"{confidence*100:.2f}%", file_path=f'/uploads/{file.filename}')

    return render_template('index.html', result=None)

# Route to serve uploaded files
@app.route('/uploads/<filename>')
def get_uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/privacy', methods=['GET'])
def privacy():
    return render_template('privacy.html')

# Route for viewing past analyses
@app.route('/my-analyses', methods=['GET'])
@login_required
def my_analyses():
    # Get all analyses for the current user, sorted by timestamp (newest first)
    user_analyses = list(analysis_results.find(
        {'user_id': session['user']['id']}
    ).sort('timestamp', -1))
    
    # Convert ObjectId to string for JSON serialization
    for analysis in user_analyses:
        analysis['_id'] = str(analysis['_id'])
        # Convert timestamp to string for display
        analysis['timestamp'] = analysis['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        # Get just the filename from the full path
        analysis['image_path'] = os.path.basename(analysis['image_path'])
    
    return render_template('my_analyses.html', analyses=user_analyses)

# Route for deleting an analysis
@app.route('/delete-analysis/<analysis_id>', methods=['POST'])
@login_required
def delete_analysis(analysis_id):
    # Find the analysis and verify it belongs to the current user
    analysis = analysis_results.find_one({
        '_id': ObjectId(analysis_id),
        'user_id': session['user']['id']
    })
    
    if analysis:
        # Delete the image file
        try:
            os.remove(analysis['image_path'])
        except:
            pass  # Ignore if file doesn't exist
        
        # Delete the analysis from database
        analysis_results.delete_one({'_id': ObjectId(analysis_id)})
        flash('Analysis deleted successfully', 'success')
    else:
        flash('Analysis not found or unauthorized', 'error')
    
    return redirect(url_for('my_analyses'))

if __name__ == '__main__':
    app.run(debug=True)