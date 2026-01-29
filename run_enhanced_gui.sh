#!/bin/bash

# Script to run the enhanced GUI with rules extraction

echo "🚀 Document Parser - Enhanced GUI with AI Rules"
echo "================================================"
echo

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "⚠️  Virtual environment not found. Creating..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate venv
echo "Activating virtual environment..."
source venv/bin/activate

# Check dependencies
echo "Checking dependencies..."
if ! python -c "import openai" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip install -q openai python-dotenv python-docx
    echo "✓ Dependencies installed"
fi

# Check for .env
if [ ! -f ".env" ]; then
    echo
    echo "⚠️  .env file not found!"
    echo "Rules extraction requires OpenAI API key."
    echo
    read -p "Do you want to create .env file now? (y/n): " response
    if [ "$response" = "y" ]; then
        read -p "Enter your OpenAI API key: " api_key
        echo "OPENAI_API_KEY=$api_key" > .env
        echo "✓ .env file created"
    else
        echo "⚠️  Rules extraction will not be available"
    fi
fi

echo
echo "🎨 Starting Enhanced GUI..."
echo
python document_parser_gui_enhanced.py

deactivate
