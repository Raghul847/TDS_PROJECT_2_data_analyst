#!/usr/bin/env python3
"""
Test web scraping functionality specifically
"""

import requests
import tempfile
import os

BACKEND_URL = "https://6e29e858-c0aa-4254-8f4b-48a71736359d.preview.emergentagent.com/api"

def create_test_questions_file(question):
    """Create a questions.txt file with the given question"""
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    temp_file.write(question)
    temp_file.close()
    return temp_file.name

def test_web_scraping():
    """Test web scraping capabilities"""
    try:
        questions_file = create_test_questions_file(
            "Scrape the first table from https://en.wikipedia.org/wiki/List_of_countries_by_population and return the number of rows as an integer."
        )
        
        with open(questions_file, 'rb') as qf:
            files = {
                'questions': ('questions.txt', qf, 'text/plain')
            }
            
            response = requests.post(f"{BACKEND_URL}/", files=files, timeout=180)
        
        # Clean up
        os.unlink(questions_file)
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {data}")
            print(f"Status: {data.get('status')}")
            print(f"Result: {data.get('result')}")
            print(f"Error: {data.get('error')}")
        else:
            print(f"Response text: {response.text}")
            
    except Exception as e:
        print(f"Test failed with error: {str(e)}")

if __name__ == "__main__":
    test_web_scraping()