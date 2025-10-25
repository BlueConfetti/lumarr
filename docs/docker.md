# Docker Guide

This guide covers running Lumarr in Docker, including Docker Compose setup and deployment strategies.

Official multi-architecture Docker images are available on Docker Hub at `blueconfetti/lumarr` for both linux/amd64 and linux/arm64 platforms.

## Quick Start

### Using Docker Compose (Recommended)

1. **Navigate to the docker directory:**
   ```bash
   cd docker
   ```

2. **Create required directories:**
   ```bash
   mkdir -p config data
   ```

3. **Copy and configure:**
   ```bash
   cp ../config.example.yaml config/config.yaml
   # Edit config/config.yaml with your settings
   ```

4. **Build and run:**
   ```bash
   docker-compose up -d
   ```

5. **Run a sync:**
   ```bash
   docker-compose run --rm lumarr sync -c /config/config.yaml
   ```

### Using Docker Directly

1. **Pull the official image:**
   ```bash
   docker pull blueconfetti/lumarr:latest
   ```

2. **Create directories:**
   ```bash
   mkdir -p docker/config docker/data
   ```

3. **Run the container:**
   ```bash
   docker run --rm \
     -v $(pwd)/docker/config:/config \
     -v $(pwd)/docker/data:/data \
     blueconfetti/lumarr sync -c /config/config.yaml
   ```

## Container Configuration

### Volume Mounts

The container expects two volume mounts:

- `/config` - Configuration files (config.yaml)
- `/data` - SQLite database and logs

**Example:**
```bash
docker run --rm \
  -v /path/to/config:/config \
  -v /path/to/data:/data \
  blueconfetti/lumarr sync -c /config/config.yaml
```

### Environment Variables

- `CONFIG_PATH` - Path to config.yaml (default: `/config/config.yaml`)
- `DB_PATH` - Path to SQLite database (default: `/data/lumarr.db`)
- `TZ` - Timezone (default: UTC)
- `PYTHONUNBUFFERED` - Set to 1 for real-time log output

**Example:**
```yaml
environment:
  - CONFIG_PATH=/config/config.yaml
  - DB_PATH=/data/lumarr.db
  - TZ=America/New_York
```

## Common Operations

### One-time Sync

```bash
docker run --rm \
  -v $(pwd)/config:/config \
  -v $(pwd)/data:/data \
  blueconfetti/lumarr sync -c /config/config.yaml
```

### Dry Run Mode

Preview changes without making them:

```bash
docker run --rm \
  -v $(pwd)/config:/config \
  -v $(pwd)/data:/data \
  blueconfetti/lumarr sync -c /config/config.yaml --dry-run
```

### Follow Mode (Continuous Monitoring)

Run Lumarr continuously to monitor for new watchlist items:

```bash
docker run --rm \
  -v $(pwd)/config:/config \
  -v $(pwd)/data:/data \
  blueconfetti/lumarr sync -c /config/config.yaml --follow
```

### View Status

```bash
docker run --rm \
  -v $(pwd)/config:/config \
  -v $(pwd)/data:/data \
  blueconfetti/lumarr status -c /config/config.yaml
```

### View History

```bash
docker run --rm \
  -v $(pwd)/config:/config \
  -v $(pwd)/data:/data \
  blueconfetti/lumarr history -c /config/config.yaml
```

### List Letterboxd Movies

```bash
docker run --rm \
  -v $(pwd)/config:/config \
  -v $(pwd)/data:/data \
  blueconfetti/lumarr lbox list -c /config/config.yaml
```

## Deployment Strategies

### Option 1: Docker Compose with Follow Mode (Recommended)

Modify `docker-compose.yml` to run in follow mode:

```yaml
services:
  lumarr:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    container_name: lumarr
    restart: unless-stopped

    volumes:
      - ./config:/config
      - ./data:/data

    environment:
      - CONFIG_PATH=/config/config.yaml
      - DB_PATH=/data/lumarr.db
      - TZ=America/Los_Angeles
      - PYTHONUNBUFFERED=1

    network_mode: bridge

    # Run in follow mode for continuous monitoring
    command: ["sync", "-c", "/config/config.yaml", "--follow"]
```

Then start the service:

```bash
docker-compose up -d
```

View logs:

```bash
docker-compose logs -f lumarr
```

### Option 2: Cron on Host

Add to your crontab to run syncs periodically:

```bash
# Edit crontab
crontab -e

# Add sync job (every 6 hours)
0 */6 * * * docker run --rm -v /path/to/config:/config -v /path/to/data:/data lumarr sync -c /config/config.yaml

# Daily at 2 AM
0 2 * * * docker run --rm -v /path/to/config:/config -v /path/to/data:/data lumarr sync -c /config/config.yaml
```

### Option 3: Docker Compose with Scheduled Loop

```yaml
command: ["sh", "-c", "while true; do lumarr sync -c /config/config.yaml; sleep 3600; done"]
```

**Note:** Follow mode is recommended over this approach as it provides better logging and graceful shutdown.

### Option 4: Kubernetes CronJob

Create a CronJob manifest for scheduled execution:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: lumarr-sync
spec:
  schedule: "0 */6 * * *"  # Every 6 hours
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: lumarr
            image: lumarr:latest
            args: ["sync", "-c", "/config/config.yaml"]
            volumeMounts:
            - name: config
              mountPath: /config
            - name: data
              mountPath: /data
          volumes:
          - name: config
            configMap:
              name: lumarr-config
          - name: data
            persistentVolumeClaim:
              claimName: lumarr-data
          restartPolicy: OnFailure
```

## Networking

### Accessing Local Services

If Sonarr/Radarr are running on the same host:

```bash
docker run --network host \
  -v $(pwd)/config:/config \
  -v $(pwd)/data:/data \
  blueconfetti/lumarr sync -c /config/config.yaml
```

Or in docker-compose.yml:

```yaml
network_mode: host
```

### Connecting to Other Containers

If Sonarr/Radarr are in other Docker containers, create a shared network:

```bash
# Create network
docker network create media

# Run lumarr on that network
docker run --network media \
  -v $(pwd)/config:/config \
  -v $(pwd)/data:/data \
  blueconfetti/lumarr sync -c /config/config.yaml
```

Or in docker-compose.yml:

```yaml
services:
  lumarr:
    # ... other config ...
    networks:
      - media

networks:
  media:
    external: true
```

## Security

### Non-Root User

The container runs as a non-root user (uid 1000) for security. Ensure your volume mount permissions match:

```bash
chown -R 1000:1000 config data
chmod -R 755 config data
```

### API Keys

Store API keys securely in config.yaml and ensure the file has appropriate permissions:

```bash
chmod 600 config/config.yaml
```

## Building

**Note:** Official multi-architecture images are automatically built and published to Docker Hub via CI/CD. Building from source is typically only needed for development or testing custom changes.

### Build from Source

```bash
# From project root
docker build -t lumarr:latest -f docker/Dockerfile .
```

### Multi-Architecture Builds

Build for different architectures using buildx:

```bash
# Build for ARM (e.g., Raspberry Pi)
docker buildx build --platform linux/arm64 -t lumarr:arm64 -f docker/Dockerfile .

# Build for multiple platforms (like official releases)
docker buildx build --platform linux/amd64,linux/arm64 -t lumarr:latest -f docker/Dockerfile .
```

Official images on Docker Hub (`blueconfetti/lumarr`) support both linux/amd64 and linux/arm64 platforms automatically.

## Troubleshooting

### Permission Errors

Ensure the config and data directories are writable by uid 1000:

```bash
chmod -R 755 config data
chown -R 1000:1000 config data
```

### Cannot Connect to Sonarr/Radarr

1. Check network mode - use `host` for local services or create a shared network
2. Verify URLs in config.yaml are accessible from within the container
3. Test connectivity:
   ```bash
   docker run --rm --network host alpine ping -c 3 sonarr
   ```

### Database Locked Errors

Ensure only one instance of Lumarr is running at a time:

```bash
# Check running containers
docker ps | grep lumarr

# Stop all lumarr containers
docker stop $(docker ps -q --filter ancestor=blueconfetti/lumarr)
```

### Container Exits Immediately

Check logs for errors:

```bash
docker logs lumarr
```

Common causes:
- Missing or invalid config.yaml
- Permission issues with volumes
- Invalid command arguments

### Follow Mode Not Working

Ensure the command is correct and logs are visible:

```bash
# Run with explicit log output
docker run --rm \
  -e PYTHONUNBUFFERED=1 \
  -v $(pwd)/config:/config \
  -v $(pwd)/data:/data \
  blueconfetti/lumarr sync -c /config/config.yaml --follow
```

## Monitoring

### Health Checks

The Dockerfile includes a basic health check. For more advanced monitoring, use Docker health checks:

```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import lumarr"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 5s
```

### Viewing Logs

```bash
# Docker Compose
docker-compose logs -f lumarr

# Docker run
docker logs -f lumarr

# Last 100 lines
docker logs --tail 100 lumarr
```

### Logging to File

Configure file logging in config.yaml:

```yaml
sync:
  log_file: "/data/lumarr.log"
  log_level: "INFO"
```

## Best Practices

1. **Use Follow Mode**: For production, use `--follow` for continuous monitoring
2. **Set Timezone**: Always set TZ environment variable to match your local time
3. **Volume Backups**: Regularly backup the `/data` volume (contains database)
4. **Network Isolation**: Use dedicated networks to isolate container communication
5. **Resource Limits**: Set memory and CPU limits in production:
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '0.5'
         memory: 256M
   ```
6. **Restart Policies**: Use `unless-stopped` or `always` for production deployments
7. **Update Regularly**: Pull new images and rebuild regularly for security updates
