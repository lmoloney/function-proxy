#!/usr/bin/env python3
"""
Azure Functions Proxy Setup Script

This script sets up the development environment for the Azure Functions HTTP Proxy.
It creates the .secrets folder, generates template files, and validates the configuration.
"""

import os
import sys
import json
import argparse
from pathlib import Path

def create_secrets_folder():
    """Create the .secrets folder and its contents."""
    project_root = Path(__file__).parent.parent
    secrets_dir = project_root / ".secrets"
    
    # Create .secrets directory
    secrets_dir.mkdir(exist_ok=True)
    print(f"✓ Created .secrets folder at: {secrets_dir}")
    
    # Create README.md for secrets folder
    secrets_readme = """# Secrets Folder

This folder contains sensitive configuration files that should **NEVER** be committed to version control.

## Files in this folder:
- `local.settings.json` - Local development settings including Azure Storage connection strings, Application Insights keys, etc.
- `profile.publishsettings` - Azure deployment credentials downloaded from the Azure Portal

## Security Notes:
- This entire folder is excluded from git via `.gitignore`
- Never share these files or commit them to any repository
- Regenerate credentials if they've been exposed
- Use Azure Key Vault for production secrets

## Setup Instructions:
1. Download your publish profile from the Azure Portal
2. Configure your `local.settings.json` with your development settings
3. Place both files in this folder

## Production Deployment:
For production deployments, use:
- Azure Key Vault for secrets management
- Managed Identity for authentication
- Application Settings in the Azure Portal instead of local.settings.json
"""
    
    readme_path = secrets_dir / "README.md"
    readme_path.write_text(secrets_readme)
    print(f"✓ Created secrets README at: {readme_path}")
    
    return secrets_dir

def create_local_settings_template(secrets_dir, interactive=False):
    """Create a template local.settings.json file."""
    local_settings_path = secrets_dir / "local.settings.json"
    
    if local_settings_path.exists() and not interactive:
        print(f"! local.settings.json already exists at: {local_settings_path}")
        return
    
    template = {
        "IsEncrypted": False,
        "Values": {
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=YOUR_STORAGE_ACCOUNT;AccountKey=YOUR_STORAGE_KEY;EndpointSuffix=core.windows.net",
            "FUNCTIONS_WORKER_RUNTIME": "python",
            "APPLICATIONINSIGHTS_CONNECTION_STRING": "InstrumentationKey=YOUR_INSTRUMENTATION_KEY;IngestionEndpoint=https://YOUR_REGION.in.applicationinsights.azure.com/"
        }
    }
    
    if interactive:
        print("\n📝 Interactive setup for local.settings.json")
        storage_account = input("Enter your Azure Storage Account name (or press Enter to use template): ").strip()
        storage_key = input("Enter your Azure Storage Account key (or press Enter to use template): ").strip()
        app_insights = input("Enter your Application Insights connection string (or press Enter to skip): ").strip()
        
        if storage_account and storage_key:
            template["Values"]["AzureWebJobsStorage"] = f"DefaultEndpointsProtocol=https;AccountName={storage_account};AccountKey={storage_key};EndpointSuffix=core.windows.net"
        
        if app_insights:
            template["Values"]["APPLICATIONINSIGHTS_CONNECTION_STRING"] = app_insights
    
    with open(local_settings_path, 'w') as f:
        json.dump(template, f, indent=2)
    
    print(f"✓ Created local.settings.json template at: {local_settings_path}")
    
    if not interactive:
        print("  ⚠️  Remember to update the placeholder values with your actual Azure credentials!")

def copy_settings_for_runtime(secrets_dir):
    """Copy local.settings.json to project root for Azure Functions runtime."""
    project_root = secrets_dir.parent
    source = secrets_dir / "local.settings.json"
    dest = project_root / "local.settings.json"
    
    if not source.exists():
        print("! local.settings.json not found in .secrets folder")
        return
    
    try:
        import shutil
        shutil.copy2(source, dest)
        print(f"✓ Copied local.settings.json to project root for runtime")
    except Exception as e:
        print(f"! Failed to copy settings: {e}")

def validate_setup(secrets_dir):
    """Validate the setup and provide next steps."""
    project_root = secrets_dir.parent
    
    print("\n🔍 Validating setup...")
    
    checks = [
        (secrets_dir.exists(), f".secrets folder exists"),
        ((secrets_dir / "README.md").exists(), f"secrets README.md exists"),
        ((secrets_dir / "local.settings.json").exists(), f"local.settings.json template exists"),
        ((project_root / "local.settings.json").exists(), f"local.settings.json copied to project root"),
    ]
    
    for passed, description in checks:
        status = "✓" if passed else "✗"
        print(f"  {status} {description}")
    
    print("\n📋 Next steps:")
    print("1. Update .secrets/local.settings.json with your actual Azure Storage credentials")
    print("2. If deploying, download your publish profile from Azure Portal to .secrets/profile.publishsettings")
    print("3. Run 'func start' to test your local development environment")
    print("4. Test the proxy with: curl 'http://localhost:7071/api/proxy/jsonplaceholder.typicode.com/posts/1'")

def main():
    parser = argparse.ArgumentParser(description="Setup Azure Functions Proxy development environment")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive setup with prompts")
    parser.add_argument("--copy-settings", "-c", action="store_true", help="Copy settings to project root")
    parser.add_argument("--validate", "-v", action="store_true", help="Validate existing setup")
    
    args = parser.parse_args()
    
    print("🚀 Azure Functions HTTP Proxy Setup")
    print("=" * 40)
    
    # Create secrets folder and files
    secrets_dir = create_secrets_folder()
    
    if not args.validate:
        create_local_settings_template(secrets_dir, interactive=args.interactive)
    
    if args.copy_settings or args.interactive:
        copy_settings_for_runtime(secrets_dir)
    
    validate_setup(secrets_dir)
    
    print("\n✅ Setup complete! Your .secrets folder is ready for development.")

if __name__ == "__main__":
    main()
