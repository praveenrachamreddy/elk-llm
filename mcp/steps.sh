# 1. Create new build
oc new-build --name=elastic-mcp-server --binary --strategy=docker

# 2. Start build using your Dockerfile folder
oc start-build elastic-mcp-server --from-dir=. --follow

# 3. Deploy the app
oc new-app elastic-mcp-server

# 4. Set ES credentials
oc set env deployment/elastic-mcp-server \
  ES_URL=http://172.16.3.63:9200 \
  ES_USERNAME=elastic \
  ES_PASSWORD=-=CotQSoFIuQmv0fTkxL

# 5. Expose service internally or via Route
oc expose svc/elastic-mcp-server
