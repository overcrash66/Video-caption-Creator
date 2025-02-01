import os
import sys
import unittest

def run_tests():
    # Determine the project root directory (where this script is located)
    project_root = os.path.abspath(os.path.dirname(__file__))
    print("Project root:", project_root)
    sys.path.insert(0, project_root)
    
    # Set the tests directory explicitly
    tests_dir = os.path.join(project_root, 'tests')
    print("Tests directory:", tests_dir)
    
    # Use the naming pattern to find test files
    pattern = 'test_*.py'
    
    loader = unittest.TestLoader()
    # Discover tests in the 'tests' directory
    tests = loader.discover(start_dir=tests_dir, pattern=pattern)
    
    # Print the number of test cases found
    num_tests = tests.countTestCases()
    print("Discovered tests count:", num_tests)
    
    if num_tests == 0:
        print("No tests found. Check your tests directory, file naming, and ensure test cases inherit from unittest.TestCase.")
    
    # Run the tests with verbosity for detailed output
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(tests)
    
    # Exit with a non-zero status if tests failed
    sys.exit(not result.wasSuccessful())

if __name__ == '__main__':
    run_tests()
