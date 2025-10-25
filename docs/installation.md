# Installation Guide

This guide covers different methods for installing Lumarr.

## Prerequisites

- Python 3.9 or higher
- Plex account with authentication token
- Sonarr and/or Radarr instance
- Optional: TMDB API key for better ID resolution

## Installation Methods

### Method 1: Using pip (Recommended)

The simplest way to install Lumarr is via PyPI:

```bash
pip install lumarr
```

This installs the latest stable release and all dependencies.

**Benefits:**
- Simplest installation method
- Official releases from PyPI
- Automatic dependency management
- Available system-wide

### Method 2: Docker (Recommended for Production)

Docker provides an isolated environment and is recommended for production deployments. Official multi-architecture images are available on Docker Hub.

```bash
docker pull blueconfetti/lumarr:latest
```

**Supported architectures:**
- linux/amd64
- linux/arm64 (Raspberry Pi, Apple Silicon, etc.)

See [Docker Guide](docker.md) for detailed instructions.

### Method 3: Using uv (For Development)

[uv](https://github.com/astral-sh/uv) is a fast Python package installer and resolver written in Rust.

**Install uv (if not already installed):**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Install Lumarr:**

```bash
# Clone the repository
git clone https://github.com/yourusername/lumarr.git
cd lumarr

# Install using uv
uv pip install -e .
```

**Benefits:**
- Extremely fast dependency resolution
- Better dependency management
- Ideal for development

### Method 4: Using pip from Source

Standard Python package installation from source:

```bash
# Clone the repository
git clone https://github.com/yourusername/lumarr.git
cd lumarr

# Install with pip
pip install -e .
```

### Method 5: From Source (Development)

For development or customization:

```bash
# Clone the repository
git clone https://github.com/yourusername/lumarr.git
cd lumarr

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Or with uv
uv pip install -e .
```

## Verifying Installation

After installation, verify Lumarr is working:

```bash
# Check version
lumarr --version

# Show help
lumarr --help
```

## Next Steps

1. **Configure Lumarr**: Copy and edit the configuration file
   ```bash
   cp config.example.yaml config.yaml
   lumarr config  # Use interactive wizard
   ```

2. **Test connections**: Verify your services are accessible
   ```bash
   lumarr status
   ```

3. **Perform a dry run**: Preview what would be synced
   ```bash
   lumarr sync --dry-run
   ```

4. **Start syncing**: Begin syncing your watchlist
   ```bash
   lumarr sync
   ```

See the [Configuration Guide](configuration.md) for detailed setup instructions and the [CLI Reference](cli-reference.md) for all available commands.

## Updating Lumarr

### With pip (from PyPI):

```bash
pip install --upgrade lumarr
```

### With Docker:

```bash
docker pull blueconfetti/lumarr:latest
```

### From source (with uv):

```bash
cd lumarr
git pull
uv pip install -e .
```

### From source (with pip):

```bash
cd lumarr
git pull
pip install -e . --upgrade
```

## Uninstalling

### With uv or pip:

```bash
pip uninstall lumarr
```

### With Docker:

```bash
docker rmi blueconfetti/lumarr
```

## Troubleshooting Installation

### Python Version Issues

Ensure you're using Python 3.9 or higher:

```bash
python --version
```

If you have multiple Python versions, you may need to specify:

```bash
python3.9 -m pip install -e .
```

### Permission Issues

If you encounter permission errors, try:

```bash
# Using pip with user flag
pip install -e . --user

# Or use a virtual environment (recommended)
python -m venv venv
source venv/bin/activate
pip install -e .
```

### Dependency Conflicts

If you experience dependency conflicts:

1. Create a fresh virtual environment
2. Use uv instead of pip for better dependency resolution
3. Check for conflicting packages: `pip list`

### Installation Fails

If installation fails:

1. Ensure pip is up to date: `pip install --upgrade pip`
2. Install build tools: `pip install build wheel`
3. Check the error message for missing system dependencies

## Platform-Specific Notes

### Linux

Install system dependencies if needed:

```bash
# Debian/Ubuntu
sudo apt-get update
sudo apt-get install python3-dev python3-pip

# Fedora/RHEL
sudo dnf install python3-devel
```

### macOS

Python should be available via Homebrew:

```bash
brew install python@3.9
```

### Windows

Install Python from [python.org](https://www.python.org/downloads/) or use Windows Subsystem for Linux (WSL) for a Linux-like environment.
