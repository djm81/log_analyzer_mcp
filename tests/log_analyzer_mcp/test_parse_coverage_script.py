import os
import sys
import pytest
from unittest import mock
import io

# Add project root to allow importing from src
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.log_analyzer_mcp import parse_coverage as pc_module

@pytest.fixture
def sample_xml_path():
    return os.path.join(script_dir, "sample_coverage.xml")

@pytest.fixture
def mock_coverage_file_path(monkeypatch, sample_xml_path):
    """Mocks the coverage_file_path global in the parse_coverage module."""
    monkeypatch.setattr(pc_module, 'coverage_file_path', sample_xml_path)

@mock.patch('sys.stdout', new_callable=io.StringIO)
def test_parse_coverage_with_sample_xml(mock_stdout, mock_coverage_file_path):
    """Test the parse_coverage function with a sample XML file."""
    pc_module.parse_coverage()
    output = mock_stdout.getvalue()

    assert "Overall coverage: 80.00%" in output
    assert "my_module/utils/healthcheck.py: 50.00%" in output
    assert "my_module/another_healthcheck.py: 70.00%" in output
    assert "No healthcheck.py files found" not in output # Make sure it finds them

@mock.patch('sys.stdout', new_callable=io.StringIO)
def test_parse_coverage_file_not_found(mock_stdout, monkeypatch):
    """Test parse_coverage when the XML file does not exist."""
    non_existent_path = "/tmp/non_existent_coverage.xml"
    monkeypatch.setattr(pc_module, 'coverage_file_path', non_existent_path)
    pc_module.parse_coverage()
    output = mock_stdout.getvalue()
    assert f"Error: Coverage file not found at {non_existent_path}" in output

@mock.patch('sys.stdout', new_callable=io.StringIO)
@mock.patch('xml.etree.ElementTree.parse')
def test_parse_coverage_xml_no_line_rate(mock_et_parse, mock_stdout, mock_coverage_file_path):
    """Test parse_coverage when the root coverage element is missing line-rate."""
    # Mock the root element to not have 'line-rate'
    mock_root = mock.Mock()
    mock_root.attrib = {} # Set attrib to an empty dict to ensure no 'line-rate'
    mock_root.findall.return_value = [] # No packages/classes to avoid further errors

    mock_tree = mock.Mock()
    mock_tree.getroot.return_value = mock_root
    mock_et_parse.return_value = mock_tree

    pc_module.parse_coverage()
    output = mock_stdout.getvalue()
    assert "Warning: Could not determine overall coverage from XML." in output
    assert "No healthcheck.py files found in coverage report." in output # Because findall returns empty


# To make this runnable with `python tests/log_analyzer_mcp/test_parse_coverage_script.py` for quick checks
if __name__ == "__main__":
    pytest.main([__file__]) 