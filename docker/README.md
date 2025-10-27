# Docker Setup for Lumarr

This directory contains Docker configuration files for containerizing the lumarr application.

**Note:** Official multi-architecture images are available on Docker Hub at `blueconfetti/lumarr` for both linux/amd64 and linux/arm64 platforms.

## Contents

- `Dockerfile` - Multi-stage Docker build for lumarr
- `docker-compose.yml` - Docker Compose configuration example
- `README.md` - This file

## Quick Start

### Using Docker Compose (Recommended)

1. Navigate to the docker directory:
```bash
cd docker
```

2. Create the required directories:
```bash
mkdir -p config data
```

3. Copy your configuration file:
```bash
cp ../config.example.yaml config/config.yaml
# Edit config/config.yaml with your settings
```

4. Build and run:
```bash
docker-compose up -d
```

5. Run a sync:
```bash
docker-compose run --rm lumarr sync -c /config/config.yaml
```

### Using Docker Directly

1. Pull the official image:
```bash
docker pull blueconfetti/lumarr:latest
```

2. Create directories for config and data:
```bash
mkdir -p docker/config docker/data
```

3. Run the container:
```bash
docker run --rm \
  -v $(pwd)/docker/config:/config \
  -v $(pwd)/docker/data:/data \
  blueconfetti/lumarr sync -c /config/config.yaml
```

## Volume Mounts

The container expects two volume mounts:

- `/config` - Configuration files (config.yaml)
- `/data` - SQLite database and logs

## Environment Variables

- `CONFIG_PATH` - Path to config.yaml (default: `/config/config.yaml`)
- `DB_PATH` - Path to SQLite database (default: `/data/lumarr.db`)
- `TZ` - Timezone (default: UTC)

## Common Commands

### Sync Plex watchlist and Letterboxd (if configured)
```bash
docker run --rm \
  -v $(pwd)/config:/config \
  -v $(pwd)/data:/data \
  blueconfetti/lumarr sync -c /config/config.yaml
```

### Follow mode (continuous monitoring)
```bash
docker run --rm \
  -v $(pwd)/config:/config \
  -v $(pwd)/data:/data \
  blueconfetti/lumarr sync -c /config/config.yaml --follow
```

### List Letterboxd movies
```bash
docker run --rm \
  -v $(pwd)/config:/config \
  -v $(pwd)/data:/data \
  blueconfetti/lumarr list letterboxd -c /config/config.yaml
```

### Check status
```bash
docker run --rm \
  -v $(pwd)/config:/config \
  -v $(pwd)/data:/data \
  blueconfetti/lumarr status -c /config/config.yaml
```

### View history
```bash
docker run --rm \
  -v $(pwd)/config:/config \
  -v $(pwd)/data:/data \
  blueconfetti/lumarr history -c /config/config.yaml
```

### Dry run mode
```bash
docker run --rm \
  -v $(pwd)/config:/config \
  -v $(pwd)/data:/data \
  blueconfetti/lumarr sync -c /config/config.yaml --dry-run
```

## Scheduled Syncs

To run lumarr on a schedule, you have several options:

### Option 1: Follow mode (Recommended)
Use follow mode for continuous monitoring:
```yaml
# docker-compose.yml
command: ["sync", "-c", "/config/config.yaml", "--follow"]
```

Then start the service:
```bash
docker-compose up -d
```

This continuously checks your watchlist at configured intervals (default: Plex every 5s, Letterboxd every 30s).

### Option 2: Cron on host
Add to your crontab for periodic syncs:
```bash
0 */6 * * * docker run --rm -v /path/to/config:/config -v /path/to/data:/data blueconfetti/lumarr sync -c /config/config.yaml
```

### Option 3: Kubernetes CronJob
Create a CronJob manifest for scheduled execution in k8s.

## Networking

If Sonarr/Radarr are running on the same host:
```bash
docker run --network host ...
```

If they're in other Docker containers, create a shared network:
```bash
docker network create media
docker run --network media ...
```

## Security

The container runs as a non-root user (uid 1000) for security. Ensure your volume mount permissions match:
```bash
chown -R 1000:1000 config data
```

## Troubleshooting

### Permission errors
Ensure the config and data directories are writable by uid 1000:
```bash
chmod -R 755 config data
chown -R 1000:1000 config data
```

### Cannot connect to Sonarr/Radarr
Check network mode and ensure the URLs in config.yaml are accessible from within the container.

### Database locked errors
Ensure only one instance of lumarr is running at a time.

## Building for Different Architectures

To build for ARM (e.g., Raspberry Pi):
```bash
docker buildx build --platform linux/arm64 -t lumarr:arm64 -f docker/Dockerfile .
```
