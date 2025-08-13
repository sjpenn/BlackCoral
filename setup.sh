#!/bin/bash

echo "BLACK CORAL Setup Script"
echo "========================"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies (basic Django only for now)
echo "Installing basic dependencies..."
pip install Django==5.2.* django-environ==0.11.*

# Run migrations
echo "Running database migrations..."
python manage.py migrate

# Create superuser if needed
echo "Creating superuser..."
python create_superuser.py

# Check system
echo "Running system checks..."
python manage.py check

echo ""
echo "Setup complete! To start the development server:"
echo "1. source venv/bin/activate"
echo "2. python manage.py runserver"
echo ""
echo "Admin credentials:"
echo "Username: admin"
echo "Password: admin123"
echo ""
echo "Visit: http://localhost:8000/"