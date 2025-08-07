#!/usr/bin/env python3
"""
Backend Test Suite for Data Analyst Agent
Tests all backend functionality including API endpoints, LLM integration, 
file processing, code execution, and visualization generation.
"""

import requests
import json
import time
import tempfile
import os
import pandas as pd
import base64
from io import BytesIO
from pathlib import Path

# Get backend URL from frontend .env
BACKEND_URL = "https://6e29e858-c0aa-4254-8f4b-48a71736359d.preview.emergentagent.com/api"

class DataAnalystTester:
    def __init__(self):
        self.backend_url = BACKEND_URL
        self.test_results = []
        
    def log_test(self, test_name, success, details, execution_time=None):
        """Log test results"""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "execution_time": execution_time
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {details}")
        if execution_time:
            print(f"   Execution time: {execution_time:.2f}s")
        print()

    def test_health_endpoint(self):
        """Test the health check endpoint"""
        try:
            response = requests.get(f"{self.backend_url}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    self.log_test("Health Check", True, "Backend is healthy and responding")
                    return True
                else:
                    self.log_test("Health Check", False, f"Unexpected health response: {data}")
                    return False
            else:
                self.log_test("Health Check", False, f"Health endpoint returned {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Health Check", False, f"Health endpoint failed: {str(e)}")
            return False

    def create_test_csv(self):
        """Create a test CSV file for analysis"""
        data = {
            'Name': ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve'],
            'Age': [25, 30, 35, 28, 32],
            'Salary': [50000, 60000, 70000, 55000, 65000],
            'Department': ['Engineering', 'Marketing', 'Engineering', 'HR', 'Marketing']
        }
        df = pd.DataFrame(data)
        
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        df.to_csv(temp_file.name, index=False)
        temp_file.close()
        return temp_file.name

    def create_test_questions_file(self, question):
        """Create a questions.txt file with the given question"""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
        temp_file.write(question)
        temp_file.close()
        return temp_file.name

    def test_simple_analysis(self):
        """Test simple text analysis without files"""
        try:
            start_time = time.time()
            
            # Create questions file
            questions_file = self.create_test_questions_file("What is 2 + 2? Store the result as an integer.")
            
            with open(questions_file, 'rb') as qf:
                files = {
                    'questions': ('questions.txt', qf, 'text/plain')
                }
                
                response = requests.post(f"{self.backend_url}/", files=files, timeout=180)
            
            execution_time = time.time() - start_time
            
            # Clean up
            os.unlink(questions_file)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "completed" and data.get("result") == 4:
                    self.log_test("Simple Analysis", True, 
                                f"Successfully computed 2+2=4, task_id: {data.get('task_id')}", 
                                execution_time)
                    return True
                else:
                    self.log_test("Simple Analysis", False, 
                                f"Unexpected result: {data.get('result')}, status: {data.get('status')}")
                    return False
            else:
                self.log_test("Simple Analysis", False, 
                            f"API returned {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Simple Analysis", False, f"Test failed with error: {str(e)}")
            return False

    def test_csv_analysis(self):
        """Test CSV file processing and analysis"""
        try:
            start_time = time.time()
            
            # Create test files
            csv_file = self.create_test_csv()
            questions_file = self.create_test_questions_file(
                "Analyze the CSV data. Calculate the average salary and return it as a number."
            )
            
            with open(questions_file, 'rb') as qf, open(csv_file, 'rb') as cf:
                files = {
                    'questions': ('questions.txt', qf, 'text/plain'),
                    'files': ('test_data.csv', cf, 'text/csv')
                }
                
                response = requests.post(f"{self.backend_url}/", files=files, timeout=180)
            
            execution_time = time.time() - start_time
            
            # Clean up
            os.unlink(questions_file)
            os.unlink(csv_file)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "completed":
                    result = data.get("result")
                    # Expected average salary: (50000+60000+70000+55000+65000)/5 = 60000
                    if isinstance(result, (int, float)) and 59000 <= result <= 61000:
                        self.log_test("CSV Analysis", True, 
                                    f"Successfully calculated average salary: {result}", 
                                    execution_time)
                        return True
                    else:
                        self.log_test("CSV Analysis", False, 
                                    f"Unexpected result: {result} (expected ~60000)")
                        return False
                else:
                    self.log_test("CSV Analysis", False, 
                                f"Analysis failed with status: {data.get('status')}, error: {data.get('error')}")
                    return False
            else:
                self.log_test("CSV Analysis", False, 
                            f"API returned {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("CSV Analysis", False, f"Test failed with error: {str(e)}")
            return False

    def test_web_scraping(self):
        """Test web scraping capabilities"""
        try:
            start_time = time.time()
            
            questions_file = self.create_test_questions_file(
                "Scrape the first table from https://en.wikipedia.org/wiki/List_of_countries_by_population and return the number of rows as an integer."
            )
            
            with open(questions_file, 'rb') as qf:
                files = {
                    'questions': ('questions.txt', qf, 'text/plain')
                }
                
                response = requests.post(f"{self.backend_url}/", files=files, timeout=180)
            
            execution_time = time.time() - start_time
            
            # Clean up
            os.unlink(questions_file)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "completed":
                    result = data.get("result")
                    if isinstance(result, int) and result > 0:
                        self.log_test("Web Scraping", True, 
                                    f"Successfully scraped Wikipedia table with {result} rows", 
                                    execution_time)
                        return True
                    else:
                        self.log_test("Web Scraping", False, 
                                    f"Unexpected result: {result} (expected positive integer)")
                        return False
                else:
                    self.log_test("Web Scraping", False, 
                                f"Scraping failed with status: {data.get('status')}, error: {data.get('error')}")
                    return False
            else:
                self.log_test("Web Scraping", False, 
                            f"API returned {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Web Scraping", False, f"Test failed with error: {str(e)}")
            return False

    def test_visualization(self):
        """Test visualization generation and base64 encoding"""
        try:
            start_time = time.time()
            
            # Create test CSV for visualization
            csv_file = self.create_test_csv()
            questions_file = self.create_test_questions_file(
                "Create a bar chart showing the salary by department from the CSV data. Return the plot as a base64 encoded image using create_plot_base64()."
            )
            
            with open(questions_file, 'rb') as qf, open(csv_file, 'rb') as cf:
                files = {
                    'questions': ('questions.txt', qf, 'text/plain'),
                    'files': ('salary_data.csv', cf, 'text/csv')
                }
                
                response = requests.post(f"{self.backend_url}/", files=files, timeout=180)
            
            execution_time = time.time() - start_time
            
            # Clean up
            os.unlink(questions_file)
            os.unlink(csv_file)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "completed":
                    result = data.get("result")
                    if isinstance(result, str) and result.startswith("data:image/"):
                        # Verify it's a valid base64 image
                        try:
                            base64_data = result.split(',')[1]
                            base64.b64decode(base64_data)
                            self.log_test("Visualization", True, 
                                        f"Successfully generated base64 encoded chart", 
                                        execution_time)
                            return True
                        except:
                            self.log_test("Visualization", False, 
                                        "Result appears to be base64 image but is invalid")
                            return False
                    else:
                        self.log_test("Visualization", False, 
                                    f"Unexpected result format: {type(result)} - {str(result)[:100]}...")
                        return False
                else:
                    self.log_test("Visualization", False, 
                                f"Visualization failed with status: {data.get('status')}, error: {data.get('error')}")
                    return False
            else:
                self.log_test("Visualization", False, 
                            f"API returned {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Visualization", False, f"Test failed with error: {str(e)}")
            return False

    def test_error_handling(self):
        """Test error handling with invalid inputs"""
        try:
            # Test with missing questions file
            response = requests.post(f"{self.backend_url}/", files={}, timeout=30)
            
            if response.status_code == 422:  # FastAPI validation error
                self.log_test("Error Handling", True, 
                            "Correctly returned validation error for missing questions file")
                return True
            else:
                self.log_test("Error Handling", False, 
                            f"Expected 422 validation error, got {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Error Handling", False, f"Test failed with error: {str(e)}")
            return False

    def test_database_storage(self):
        """Test database storage of analysis requests"""
        try:
            # First perform an analysis to create a database entry
            questions_file = self.create_test_questions_file("Simple test for database storage: return 'stored'")
            
            with open(questions_file, 'rb') as qf:
                files = {
                    'questions': ('questions.txt', qf, 'text/plain')
                }
                
                response = requests.post(f"{self.backend_url}/", files=files, timeout=180)
            
            os.unlink(questions_file)
            
            if response.status_code == 200:
                data = response.json()
                task_id = data.get("task_id")
                
                # Now check if we can retrieve tasks
                tasks_response = requests.get(f"{self.backend_url}/tasks", timeout=30)
                
                if tasks_response.status_code == 200:
                    tasks = tasks_response.json()
                    if isinstance(tasks, list) and len(tasks) > 0:
                        # Check if our task is in the list
                        task_found = any(task.get("task_id") == task_id for task in tasks)
                        if task_found:
                            self.log_test("Database Storage", True, 
                                        f"Successfully stored and retrieved task {task_id}")
                            return True
                        else:
                            self.log_test("Database Storage", False, 
                                        f"Task {task_id} not found in database")
                            return False
                    else:
                        self.log_test("Database Storage", False, 
                                    "Tasks endpoint returned empty or invalid data")
                        return False
                else:
                    self.log_test("Database Storage", False, 
                                f"Tasks endpoint returned {tasks_response.status_code}")
                    return False
            else:
                self.log_test("Database Storage", False, 
                            f"Initial analysis failed with {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Database Storage", False, f"Test failed with error: {str(e)}")
            return False

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting Data Analyst Agent Backend Tests")
        print(f"Backend URL: {self.backend_url}")
        print("=" * 60)
        
        # Test in order of priority
        tests = [
            ("Health Check", self.test_health_endpoint),
            ("Simple Analysis (LLM Integration)", self.test_simple_analysis),
            ("CSV File Processing", self.test_csv_analysis),
            ("Visualization Generation", self.test_visualization),
            ("Web Scraping", self.test_web_scraping),
            ("Error Handling", self.test_error_handling),
            ("Database Storage", self.test_database_storage),
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            print(f"Running: {test_name}")
            if test_func():
                passed += 1
        
        print("=" * 60)
        print(f"📊 Test Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! Backend is working correctly.")
        else:
            print(f"⚠️  {total - passed} tests failed. Check the details above.")
        
        return self.test_results

if __name__ == "__main__":
    tester = DataAnalystTester()
    results = tester.run_all_tests()