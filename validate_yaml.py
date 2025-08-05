#!/usr/bin/env python3
"""
Validate YAML files for syntax errors.
"""
import yaml
import sys
import os

def validate_yaml_file(file_path):
    """Validate a YAML file."""
    try:
        with open(file_path, 'r') as f:
            yaml.safe_load(f)
        return True, None
    except yaml.YAMLError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Error reading file: {str(e)}"

def main():
    """Validate GitHub Actions workflow file."""
    workflow_file = ".github/workflows/deploy-pump-bot.yml"
    
    if not os.path.exists(workflow_file):
        print(f"❌ File not found: {workflow_file}")
        return 1
    
    print(f"🔍 Validating {workflow_file}...")
    
    is_valid, error = validate_yaml_file(workflow_file)
    
    if is_valid:
        print("✅ YAML syntax is valid!")
        
        # Additional GitHub Actions specific checks
        with open(workflow_file, 'r') as f:
            content = yaml.safe_load(f)
            
        # Check required fields
        required_fields = ['name', 'on', 'jobs']
        missing_fields = [field for field in required_fields if field not in content]
        
        if missing_fields:
            print(f"⚠️  Missing required fields: {missing_fields}")
        else:
            print("✅ All required GitHub Actions fields present")
            
        # Check if jobs have required structure
        if 'jobs' in content:
            for job_name, job_config in content['jobs'].items():
                if 'runs-on' not in job_config:
                    print(f"⚠️  Job '{job_name}' missing 'runs-on' field")
                if 'steps' not in job_config:
                    print(f"⚠️  Job '{job_name}' missing 'steps' field")
                    
        print("\n🎉 GitHub Actions workflow appears to be valid!")
        return 0
    else:
        print(f"❌ YAML syntax error: {error}")
        return 1

if __name__ == "__main__":
    sys.exit(main())