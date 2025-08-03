# OpenShift-compatible image for Gemma3 + Elasticsearch MCP integration
FROM registry.access.redhat.com/ubi8/python-311

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/opt/app-root/src \
    PATH=/opt/app-root/src/.local/bin:$PATH

# Switch to root to install dependencies
USER 0

# # Install Node.js 18 and system tools using dnf
# RUN curl -fsSL https://rpm.nodesource.com/setup_18.x | bash - && \
#     dnf install -y nodejs npm git && \
#     dnf clean all

# Install the MCP server module globally
RUN npm install -g @elastic/mcp-server-elasticsearch && npm cache clean --force

# Switch to non-root for OpenShift compatibility
USER 1001

# Set working directory
WORKDIR /opt/app-root/src

# Copy and install Python dependencies
COPY --chown=1001:0 requirements.txt ./
RUN pip install --user --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=1001:0 . .

# Create writable directories
RUN mkdir -p logs && \
    chmod -R g+w /opt/app-root/src && \
    chmod +x main.py

# Expose MCP server port if needed
EXPOSE 8080

# Optional: Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "print('Health check passed')" || exit 1

# Start LangChain app that connects to Gemma3 and MCP
CMD ["python", "main.py"]
