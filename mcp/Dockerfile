# Use Red Hat UBI with Node.js 18
FROM registry.access.redhat.com/ubi8/nodejs-18

# Labels for OpenShift
LABEL maintainer="you@example.com"
LABEL description="Elastic MCP Server for Elasticsearch"

# Set working directory
WORKDIR /opt/app-root/src

# Install MCP Server globally
RUN npm install -g @elastic/mcp-server-elasticsearch

# Set permissions for non-root user (1001)
RUN chown -R 1001:0 /opt/app-root && \
    chmod -R g=u /opt/app-root

# Set environment variables (can override in OpenShift)
ENV ES_URL=http://elasticsearch:9200
ENV ES_API_KEY=changeme
ENV OTEL_LOG_LEVEL=none
ENV ES_USERNAME=elastic
ENV ES_PASSWORD=changeme
# ENV OTEL_EXPORTER_OTLP_ENDPOINT=""
ENV OTEL_SDK_DISABLED=true


# Expose MCP port
EXPOSE 3000

# Run as non-root OpenShift user
USER 1001

# Start the MCP server
CMD ["mcp-server-elasticsearch"]

