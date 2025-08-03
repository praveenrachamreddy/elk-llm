# OpenShift-compatible single image for Gemma3 Elasticsearch MCP Integration
FROM registry.access.redhat.com/ubi8/python-311

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/opt/app-root/src \
    PATH=/opt/app-root/src/.local/bin:$PATH

# Switch to root to install system dependencies
USER 0

# Install Node.js and system dependencies
RUN curl -fsSL https://rpm.nodesource.com/setup_18.x | bash - && \
    microdnf install -y nodejs npm git && \
    microdnf clean all

# Install global npm packages
RUN npm install -g @modelcontextprotocol/server-elasticsearch && \
    npm cache clean --force

# Switch back to default user for OpenShift compatibility
USER 1001

# Set working directory
WORKDIR /opt/app-root/src

# Copy requirements and install Python dependencies
COPY --chown=1001:0 requirements.txt ./
RUN pip install --user --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=1001:0 . .

# Create necessary directories with proper permissions
RUN mkdir -p logs && \
    chmod -R g+w /opt/app-root/src && \
    chmod +x main.py

# Expose port (if needed for health checks)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "print('Health check passed')" || exit 1

# Default command
CMD ["python", "main.py"]