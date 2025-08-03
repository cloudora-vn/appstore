#!/usr/bin/env python3
"""
Generate appstore.json from apps directory structure
"""

import json
import os
import yaml
import time
import hashlib
import re
from pathlib import Path
from typing import Dict, List, Any

class AppStoreGenerator:
    def __init__(self, github_repo: str = ""):
        # Get GitHub repo from environment or use default
        self.github_repo = github_repo or os.environ.get('GITHUB_REPOSITORY', 'yourusername/appstore')
        self.base_url = f"https://raw.githubusercontent.com/{self.github_repo}/main"
        self.apps_dir = Path("apps")
        self.output_file = Path("appstore.json")
        
    def get_file_info(self, file_path: Path) -> Dict[str, Any]:
        """Get file information including size and last modified time"""
        stat = file_path.stat()
        return {
            "name": file_path.name,
            "size": stat.st_size,
            "lastModified": time.strftime("%Y-%m-%dT%H:%M:%S.000+00:00", 
                                         time.gmtime(stat.st_mtime))
        }
    
    def parse_version(self, version_dir: str) -> str:
        """Convert directory name to version string (e.g., '1-26-0' to '1.26.0')"""
        # Handle various version formats
        if '-' in version_dir:
            return version_dir.replace('-', '.')
        elif '_' in version_dir:
            return version_dir.replace('_', '.')
        return version_dir
    
    def get_app_metadata(self, app_dir: Path) -> Dict[str, Any]:
        """Extract metadata from app directory"""
        metadata = {}
        
        # Check for metadata.yml or metadata.json
        metadata_yml = app_dir / "metadata.yml"
        metadata_json = app_dir / "metadata.json"
        
        if metadata_yml.exists():
            with open(metadata_yml, 'r', encoding='utf-8') as f:
                metadata = yaml.safe_load(f) or {}
        elif metadata_json.exists():
            with open(metadata_json, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        
        # Check for README.md
        readme_path = app_dir / "README.md"
        if readme_path.exists():
            with open(readme_path, 'r', encoding='utf-8') as f:
                metadata['readMe'] = f.read()
        
        # Check for logo/icon
        for icon_name in ['logo.png', 'icon.png', 'logo.svg', 'icon.svg']:
            icon_path = app_dir / icon_name
            if icon_path.exists():
                metadata['icon'] = f"{self.base_url}/apps/{app_dir.name}/{icon_name}"
                break
        
        return metadata
    
    def process_version(self, app_name: str, version_dir: Path) -> Dict[str, Any]:
        """Process a single version directory"""
        version_name = self.parse_version(version_dir.name)
        
        # Collect all files in the version directory
        files = []
        for file_path in version_dir.iterdir():
            if file_path.is_file() and not file_path.name.startswith('.'):
                files.append(self.get_file_info(file_path))
        
        # Sort files by name
        files.sort(key=lambda x: x['name'])
        
        version_data = {
            "valid": True,
            "violations": [],
            "id": version_dir.name,
            "readMe": None,
            "name": version_name,
            "lastModified": int(time.time()),
            "files": files,
            "downloadUrl": f"{self.base_url}/apps/{app_name}/{version_dir.name}",
            "downloadCallbackUrl": f"https://api.github.com/repos/{self.github_repo}/contents/apps/{app_name}/{version_dir.name}"
        }
        
        # Check for version-specific README
        version_readme = version_dir / "README.md"
        if version_readme.exists():
            with open(version_readme, 'r', encoding='utf-8') as f:
                version_data['readMe'] = f.read()
        
        return version_data
    
    def process_app(self, app_dir: Path) -> Dict[str, Any]:
        """Process a single app directory"""
        app_name = app_dir.name
        metadata = self.get_app_metadata(app_dir)
        
        # Default values
        app_data = {
            "valid": True,
            "violations": [],
            "id": app_name,
            "lastModified": int(time.time()),
            "icon": metadata.get('icon', f"{self.base_url}/apps/{app_name}/logo.png"),
            "readMe": metadata.get('readMe', f"# {app_name.title()}\n\nDescription for {app_name}..."),
            "description": metadata.get('description', f"Description for {app_name}"),
            "name": metadata.get('name', app_name.title()),
            "tags": metadata.get('tags', []),
            "title": metadata.get('title', app_name.title()),
            "additionalProperties": {
                "key": app_name,
                "name": metadata.get('name', app_name.title()),
                "tags": metadata.get('tags', []),
                "shortDescZh": metadata.get('shortDescZh', ''),
                "shortDescEn": metadata.get('shortDescEn', metadata.get('description', '')),
                "description": metadata.get('descriptions', {
                    "en": metadata.get('description', ''),
                    "zh": metadata.get('descriptionZh', '')
                }),
                "type": metadata.get('type', 'runtime'),
                "crossVersionUpdate": metadata.get('crossVersionUpdate', True),
                "limit": metadata.get('limit', 1),
                "recommend": metadata.get('recommend', 100),
                "website": metadata.get('website', ''),
                "github": metadata.get('github', ''),
                "document": metadata.get('document', ''),
                "architectures": metadata.get('architectures', ["amd64", "arm64"])
            },
            "versions": []
        }
        
        # Process version directories
        version_dirs = []
        for item in app_dir.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Check if it looks like a version directory
                if re.match(r'^v?\d+[-._]\d+', item.name) or item.name in ['latest', 'stable']:
                    version_dirs.append(item)
        
        # Sort versions
        version_dirs.sort(key=lambda x: x.name, reverse=True)
        
        # Process each version
        for version_dir in version_dirs:
            version_data = self.process_version(app_name, version_dir)
            app_data['versions'].append(version_data)
        
        return app_data
    
    def generate(self):
        """Generate the complete appstore.json"""
        store_data = {
            "valid": True,
            "violations": [],
            "id": "corapanel",
            "icon": "https://cdn-icons-png.flaticon.com/512/4187/4187336.png",
            "lastModified": int(time.time()),
            "name": "CoraPANEL",
            "title": "Official Appstore for CoraPANEL",
            "extra": {
                "version": "v1.0.0"
            },
            "apps": []
        }
        
        # Check if apps directory exists
        if not self.apps_dir.exists():
            print(f"Warning: {self.apps_dir} directory not found. Creating empty appstore.json")
            self.save(store_data)
            return
        
        # Process each app directory
        app_dirs = [d for d in self.apps_dir.iterdir() 
                   if d.is_dir() and not d.name.startswith('.')]
        app_dirs.sort(key=lambda x: x.name)
        
        for app_dir in app_dirs:
            try:
                print(f"Processing app: {app_dir.name}")
                app_data = self.process_app(app_dir)
                store_data['apps'].append(app_data)
            except Exception as e:
                print(f"Error processing {app_dir.name}: {e}")
                continue
        
        # Save the generated JSON
        self.save(store_data)
        print(f"Generated {self.output_file} with {len(store_data['apps'])} apps")
    
    def save(self, data: Dict[str, Any]):
        """Save the generated data to appstore.json"""
        with open(self.output_file, 'w', encoding='utf-8') as f:
            # Save with proper formatting first (for debugging if needed)
            json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    # GitHub repository is automatically available in GitHub Actions as GITHUB_REPOSITORY
    generator = AppStoreGenerator()
    generator.generate()

if __name__ == "__main__":
    main()