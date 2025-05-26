import xml.etree.ElementTree as ET
import os

# Define project_root for robust path calculation
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir)) # Assumes script is in src/log_analyzer_mcp

# Path to coverage.xml based on pyproject.toml
coverage_file_path = os.path.join(project_root, 'logs', 'tests', 'coverage', 'coverage.xml')

def parse_coverage():
    if not os.path.exists(coverage_file_path):
        print(f"Error: Coverage file not found at {coverage_file_path}")
        return

    tree = ET.parse(coverage_file_path)
    root = tree.getroot()
    line_rate_attrib = root.attrib.get('line-rate')
    if line_rate_attrib is not None:
        overall_coverage = float(line_rate_attrib) * 100
        print(f"Overall coverage: {overall_coverage:.2f}%")
    else:
        print("Warning: Could not determine overall coverage from XML.")
    
    # Find all healthcheck.py files and their coverage
    found_healthcheck = False
    for package in root.findall('.//package'):
        for cls in package.findall('.//class'):
            filename = cls.attrib.get('filename')
            if filename and 'healthcheck.py' in filename:
                found_healthcheck = True
                class_line_rate = cls.attrib.get('line-rate')
                if class_line_rate is not None:
                    line_rate_val = float(class_line_rate) * 100
                    print(f"{filename}: {line_rate_val:.2f}%")
                else:
                    print(f"{filename}: Coverage data not available.")
    if not found_healthcheck:
        print("No healthcheck.py files found in coverage report.")

if __name__ == "__main__":
    parse_coverage() 